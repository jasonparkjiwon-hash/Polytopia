//! Win-percentage playouts (win-pct, Phase 5): play the bot policy v2 for every tribe forward from a real save with
//! `Game::search_move` (no fog memory, no reveals) and report each tribe's standing at a horizon. Seeded, reproducible.
//! usage: pfwin <policy.json> <belief_model.json> <jobs.json>
//! job: {"tag", "start": decoded save, "player": to move, "playouts": n, "horizon": rounds, "seed": s,
//!       "belief_pov": p (optional)}   belief_pov: draw the hidden map from tribe p's view for each playout (tools/pf_belief.py's
//!       sampler); without it the playouts use the FULL information in the save (cheating, fine for calibration on saves)
//!      or {"tag", "start", "player", "state_only": true} -> just the feature vectors of that save.
//! optional "snap_hs": [rounds to keep] (default 1..=horizon).
//! Prints one `PFWIN {json}` line per job: {tag, names, tribes: {id: {tribe, bot}}, start: {id: feats}, hs: [h..], playouts: [[{id: feats} per h in hs]],
//!   final_turn: [..], secs, moves_per_s, rounds_per_s}. Feature order is `FEATS`; `eval` in tools/winpct.py turns them into a standing.
use polyfish::api;
use polyfish::belief::{self, Mode, Model};
use polyfish::botpolicy2::{self, Policy};
use polyfish::fog;
use polyfish::functions::{get_bot_bonus, get_total_production, get_unit_max_health};
use polyfish::game::Game;
use polyfish::unseen::{self, Bank};
use polyfish::settings::units::get_unit_setting;
use serde_json::{json, Value};
use std::time::Instant;

thread_local! { static PROF: std::cell::RefCell<[f64; 4]> = std::cell::RefCell::new([0.0; 4]); }
const FEATS: [&str; 17] = ["alive", "cities", "pop", "level", "units", "unit_cost", "unit_hp_cost", "stars", "income", "techs", "kills", "casualties", "score", "connected", "threat", "pressure", "water"];

fn feats(g: &Game, id: i32) -> Vec<f64> {
    let t = &g.state.tribes[&id];
    // threat: own cities with a foreign attacking unit within 3 (Chebyshev); pressure: foreign cities with an own attacking unit within 3; water: share of water tiles
    let size = g.state.settings.size;
    let armed = |u: &&polyfish::states::UnitState| get_unit_setting(u.unit_type).attack > 0.0;
    let foe_units: Vec<i32> = g.state.tribes.iter().filter(|(k, _)| **k != id).flat_map(|(_, o)| o.units.iter().filter(armed).map(|u| u.coords.idx)).collect();
    let my_units: Vec<i32> = t.units.iter().filter(armed).map(|u| u.coords.idx).collect();
    let near = |c: i32, set: &[i32]| set.iter().any(|&u| polyfish::functions::get_chebyshev_distance(c, u, size) <= 3);
    let threat = t.cities.iter().filter(|c| near(c.idx, &foe_units)).count() as f64;
    let pressure = g.state.tribes.iter().filter(|(k, _)| **k != id).flat_map(|(_, o)| o.cities.iter()).filter(|c| near(c.idx, &my_units)).count() as f64;
    let water = g.state.tiles.values().filter(|tl| tl.is_water_terrain()).count() as f64 / (g.state.tiles.len().max(1) as f64);
    let cost = |u: &polyfish::states::UnitState| get_unit_setting(u.unit_type).cost as f64 + u.passenger_type.map(|p| get_unit_setting(p).cost as f64).unwrap_or(0.0);
    vec![
        (t.killed_turn <= 0 && t.resigned_turn <= 0 && !t.cities.is_empty()) as i32 as f64,
        t.cities.len() as f64,
        t.cities.iter().map(|c| c.population as f64).sum(),
        t.cities.iter().map(|c| c.level as f64).sum(),
        t.units.len() as f64,
        t.units.iter().map(cost).sum(),
        t.units.iter().map(|u| cost(u) * (u.health / get_unit_max_health(u).max(1.0)).clamp(0.0, 1.0) as f64).sum(),
        t.stars as f64,
        (get_total_production(&g.state, &t.cities) + get_bot_bonus(&g.state, t)) as f64,
        t.tech_vanilla.len() as f64,
        t.kills as f64,
        t.casualties as f64,
        t.score as f64,
        t.cities.iter().filter(|c| c.connected_to_capital).count() as f64,
        threat, pressure, water,
    ]
}

fn all_feats(g: &Game) -> Value {
    let m: serde_json::Map<String, Value> = g.state.tribes.keys().map(|id| (id.to_string(), json!(feats(g, *id).iter().map(|x| (x * 100.0).round() / 100.0).collect::<Vec<f64>>()))).collect();
    Value::Object(m)
}

/// One playout. Returns the feature vectors of every tribe at the start of each round h = 1..=horizon (the moment the turn counter
/// reaches start + h with the starting player to move again), the final turn and the number of moves applied.
fn playout(base: &Game, pol: &Policy, model: &Model, pov: Option<i32>, unseen: Option<(&Bank, &unseen::Opts)>, horizon: i32, keep: &[i32], seed: u64) -> (Vec<Value>, i32, u64) {
    let mut game = match pov {
        Some(p) => {
            let mut g = belief::sample_belief(base, p, model, Mode::Full, seed);
            if let Some((bank, o)) = unseen { unseen::complete(&mut g, base, p, bank, o, &mut belief::Rng(seed ^ 0x51EE_D00D_F00D_BEEF)); }
            g
        }
        None => api::clone(base),
    };
    let (t0, sp) = (game.state.settings.turn, game.state.settings.current_player_turn_id);
    let mut rng = (seed.wrapping_mul(1_000_003) ^ 0x9E37_79B9_7F4A_7C15) | 1;
    let (mut guard, mut applied, mut h) = (0u64, 0u64, 1);
    let mut snaps = Vec::new();
    while h <= horizon && guard < 40_000 {
        let (turn, cur) = (game.state.settings.turn, game.state.settings.current_player_turn_id);
        if turn >= t0 + h && (cur == sp || turn > t0 + h) { if keep.contains(&h) { snaps.push(all_feats(&game)); } h += 1; continue; }
        if game.is_game_over() { break; }
        guard += 1;
        let t1 = Instant::now();
        let legal = game.legal_moves();
        let t2 = Instant::now();
        let i = botpolicy2::choose(&game, &legal, pol, &mut rng, true);
        let t3 = Instant::now();
        let ok = api::apply_search(&mut game, legal[i].as_ref()).is_none();
        PROF.with(|p| { let mut p = p.borrow_mut(); p[0] += (t2 - t1).as_secs_f64(); p[1] += (t3 - t2).as_secs_f64(); p[2] += t3.elapsed().as_secs_f64(); p[3] += legal.len() as f64; });
        if ok { break; }
        applied += 1;
    }
    while h <= horizon { if keep.contains(&h) { snaps.push(all_feats(&game)); } h += 1; }   // game over: the final state stands
    (snaps, game.state.settings.turn, applied)
}

fn unseen_profile(g: &Game, id: i32, gid: &str) -> unseen::Profile { unseen::profile_of(g, id, gid) }

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let pol = Policy::from_file(&a[1]).unwrap_or_else(|e| { eprintln!("{e}"); std::process::exit(2) });
    let model: Model = serde_json::from_str(&std::fs::read_to_string(&a[2]).expect("belief model")).expect("belief model json");
    let jobs: Value = serde_json::from_str(&std::fs::read_to_string(&a[3]).expect("jobs file")).expect("jobs json");
    let bank = a.get(4).map(|p| Bank::from_file(p).unwrap_or_else(|e| { eprintln!("{e}"); std::process::exit(2) })).unwrap_or_default();
    for job in jobs.as_array().expect("jobs list") {
        let player = job["player"].as_i64().unwrap_or(1) as i32;
        let path = job["start"].as_str().unwrap_or("");
        let loaded = std::fs::read_to_string(path).map_err(|e| e.to_string()).and_then(|t| serde_json::from_str::<Value>(&t).map_err(|e| e.to_string()))
            .and_then(|v| fog::load_exact(&v, "current", player));
        let base = match loaded { Ok(g) => g, Err(e) => { println!("PFWIN {}", json!({"tag": job["tag"], "error": e})); continue; } };
        let tribes: serde_json::Map<String, Value> = base.state.tribes.iter().map(|(id, t)| (id.to_string(), json!({"tribe": format!("{:?}", t.tribe_type), "bot": t.bot}))).collect();
        let start = all_feats(&base);
        if job["state_only"].as_bool() == Some(true) {
            let profiles: Value = match job["game"].as_str() {
                Some(gid) => json!(base.state.tribes.keys().map(|id| serde_json::to_value(unseen_profile(&base, *id, gid)).unwrap()).collect::<Vec<_>>()),
                None => Value::Null,
            };
            // fog features of the mover's view (win-pct-3): per tribe [cities on explored tiles, met by pov (known_players or a city seen)], and the explored share of the map
            let ex = fog::explored(&base, player);
            let known = base.state.tribes.get(&player).map(|t| t.known_players.clone()).unwrap_or_default();
            let fogf: serde_json::Map<String, Value> = base.state.tribes.iter().map(|(id, t)| {
                let vc = t.cities.iter().filter(|c| ex.contains(&c.idx)).count();
                (id.to_string(), json!([vc, (*id == player || known.contains(id) || vc > 0) as i32]))
            }).collect();
            let exs = ex.len() as f64 / (base.state.tiles.len().max(1) as f64);
            println!("PFWIN {}", json!({"tag": job["tag"], "names": FEATS, "turn": base.state.settings.turn, "tribes": tribes, "start": start, "profiles": profiles, "fog": fogf, "explored": exs}));
            continue;
        }
        let n = job["playouts"].as_u64().unwrap_or(20);
        let horizon = job["horizon"].as_i64().unwrap_or(5) as i32;
        let seed = job["seed"].as_u64().unwrap_or(1);
        let keep: Vec<i32> = job["snap_hs"].as_array().map(|v| v.iter().filter_map(|x| x.as_i64()).map(|x| x as i32).collect()).unwrap_or_else(|| (1..=horizon).collect());
        let pov = job["belief_pov"].as_i64().map(|p| p as i32);
        // "unseen": "none" | "noscore" | "score" | "oracle_cities" | "oracle_all": complete the hidden opponents from the profile bank (a[4])
        let umode = job["unseen"].as_str().unwrap_or("none").to_string();
        let uopts = unseen::Opts { use_score: umode != "noscore", score_all: umode == "scoreall", oracle_cities: umode.starts_with("oracle"), oracle_units: umode == "oracle_all",
            exclude: job["bank_exclude"].as_array().map(|v| v.iter().filter_map(|x| x.as_str().map(String::from)).collect()).unwrap_or_default() };
        let useen = if umode != "none" && pov.is_some() { Some((&bank, &uopts)) } else { None };
        let t0 = Instant::now();
        let (mut outs, mut rounds, mut moves, mut err) = (Vec::new(), Vec::new(), 0u64, 0);
        for k in 0..n {
            let r = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| playout(&base, &pol, &model, pov, useen, horizon, &keep, seed * 1_000_003 + k)));
            match r { Ok((f, turn, m)) => { outs.push(json!(f)); rounds.push(turn); moves += m; } Err(_) => err += 1 }
        }
        let secs = t0.elapsed().as_secs_f64();
        let played: i64 = rounds.iter().map(|t| (*t - base.state.settings.turn).max(0) as i64).sum();
        println!("PFWIN {}", json!({"tag": job["tag"], "names": FEATS, "turn": base.state.settings.turn, "tribes": tribes, "start": start, "hs": keep, "playouts": outs,
            "prof_legal_choose_apply_nlegal": PROF.with(|p| *p.borrow()), "final_turn": rounds, "panics": err, "secs": secs, "moves_per_s": moves as f64 / secs, "rounds_per_s": played as f64 / secs}));
    }
}
