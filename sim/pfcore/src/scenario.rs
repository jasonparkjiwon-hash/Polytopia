//! Scenario comparison (what-if-2, capability 3). Given a save, a player and 1-5 candidate move sequences, play each
//! sequence EXACTLY (the engine's own `play_move`), then sample K bot turns forward with the fitted bot policy and report,
//! per option: the exact immediate result, the sampled replies of the other tribes (who is attacked, what is lost), and the
//! standing of every tribe after H rounds. Everything after the exact part is an estimate from the bot model
//! (.scratchpad/investigations/bot-model-3.md); the output says so. Adds no rules. Hypotheticals (`hypos`) edit the loaded
//! true state before anything is played: unit HP, stars, peace/war between two tribes.
//! The text is made by tools/scenario.py. Job (JSON): {player?, k, h, seed, policy, dist?, threads?, hypos: [..], options: [{name, moves: [label..]}]}
use crate::api;
use crate::botpolicy2::{self, Policy};
use crate::fog;
use crate::functions as f;
use crate::game::Game;
use crate::types::MoveType;
use crate::moves::Move;
use crate::settings::units::get_unit_setting;
use crate::states::*;
use serde_json::{json, Value};
use std::collections::{BTreeMap, HashMap};

pub const FEATS: [&str; 17] = ["alive", "cities", "pop", "level", "units", "unit_cost", "unit_hp_cost", "stars", "income", "techs", "kills", "casualties", "score", "connected", "threat", "pressure", "water"];
const FI_CITIES: usize = 1;
const FI_UNITS: usize = 4;
const FI_VALUE: usize = 6;
const FI_STARS: usize = 7;
const FI_KILLS: usize = 10;
const FI_SCORE: usize = 12;
/// Features reported per tribe and round (name, index).
const SHOWN: [(&str, usize); 6] = [("cities", FI_CITIES), ("units", FI_UNITS), ("unit_value", FI_VALUE), ("stars", FI_STARS), ("score", FI_SCORE), ("kills", FI_KILLS)];

fn xy(sz: i32, idx: i32) -> (i32, i32) { (idx % sz, idx / sz) }

fn tribe_name(s: &GameState, id: i32) -> String { s.tribes.get(&id).map_or("?".into(), |t| format!("{:?}", t.tribe_type)) }

/// Same feature vector as pfwin (kept in the same order so tools/winpct_lib.py can read it).
pub fn feats(g: &Game, id: i32) -> Vec<f64> {
    let t = &g.state.tribes[&id];
    // threat / pressure / water: as in bin/pfwin.rs (win-pct-3)
    let size = g.state.settings.size;
    let armed = |u: &&UnitState| get_unit_setting(u.unit_type).attack > 0.0;
    let foe_units: Vec<i32> = g.state.tribes.iter().filter(|(k, _)| **k != id).flat_map(|(_, o)| o.units.iter().filter(armed).map(|u| u.coords.idx)).collect();
    let my_units: Vec<i32> = t.units.iter().filter(armed).map(|u| u.coords.idx).collect();
    let near = |c: i32, set: &[i32]| set.iter().any(|&u| f::get_chebyshev_distance(c, u, size) <= 3);
    let threat = t.cities.iter().filter(|c| near(c.idx, &foe_units)).count() as f64;
    let pressure = g.state.tribes.iter().filter(|(k, _)| **k != id).flat_map(|(_, o)| o.cities.iter()).filter(|c| near(c.idx, &my_units)).count() as f64;
    let water = g.state.tiles.values().filter(|tl| tl.is_water_terrain()).count() as f64 / (g.state.tiles.len().max(1) as f64);
    let cost = |u: &UnitState| get_unit_setting(u.unit_type).cost as f64 + u.passenger_type.map(|p| get_unit_setting(p).cost as f64).unwrap_or(0.0);
    vec![
        (t.killed_turn <= 0 && t.resigned_turn <= 0 && !t.cities.is_empty()) as i32 as f64,
        t.cities.len() as f64,
        t.cities.iter().map(|c| c.population as f64).sum(),
        t.cities.iter().map(|c| c.level as f64).sum(),
        t.units.len() as f64,
        t.units.iter().map(cost).sum(),
        t.units.iter().map(|u| cost(u) * (u.health / f::get_unit_max_health(u).max(1.0)).clamp(0.0, 1.0) as f64).sum(),
        t.stars as f64,
        (f::get_total_production(&g.state, &t.cities) + f::get_bot_bonus(&g.state, t)) as f64,
        t.tech_vanilla.len() as f64,
        t.kills as f64,
        t.casualties as f64,
        t.score as f64,
        t.cities.iter().filter(|c| c.connected_to_capital).count() as f64,
        threat, pressure, water,
    ]
}

fn all_feats(g: &Game) -> BTreeMap<i32, Vec<f64>> { g.state.tribes.keys().map(|id| (*id, feats(g, *id))).collect() }

// ---------------------------------------------------------------------------------------------------------------------
// hypotheticals

pub const HYPO_HELP: &str = "supported edits: unit HP (\"enemy unit at x,y has N more HP\", \"... N less HP\", \"... has N HP\", also \"my unit at x,y ...\"), \
stars (\"I have N more stars\", \"I have N fewer stars\", \"tribe T has N more stars\"), peace (\"peace with tribe T\") and war (\"war with tribe T\"). \
Anything else (new units, new cities, techs, terrain, other tribes' relations) is refused.";

fn tribe_arg(g: &Game, v: &Value) -> Result<i32, String> {
    if let Some(n) = v.as_i64() { return if g.state.tribes.contains_key(&(n as i32)) { Ok(n as i32) } else { Err(format!("no player {n} in this save")) }; }
    let name = v.as_str().unwrap_or("").to_lowercase();
    let hits: Vec<i32> = g.state.tribes.iter().filter(|(_, t)| format!("{:?}", t.tribe_type).to_lowercase() == name).map(|(id, _)| *id).collect();
    match hits.len() { 1 => Ok(hits[0]), 0 => Err(format!("no tribe called {name} in this save")), _ => Err(format!("{name} is ambiguous (players {hits:?}); name the player number")) }
}

/// Apply one structured edit to the loaded TRUE state; returns the sentence describing what was done.
fn apply_hypo(g: &mut Game, pov: i32, h: &Value) -> Result<String, String> {
    let sz = g.state.settings.size;
    match h["op"].as_str().unwrap_or("") {
        "unit_hp" => {
            let (x, y) = (h["x"].as_i64().ok_or("no x")? as i32, h["y"].as_i64().ok_or("no y")? as i32);
            if x < 0 || y < 0 || x >= sz || y >= sz { return Err(format!("({x},{y}) is off the map (size {sz})")); }
            let idx = y * sz + x;
            if !g.state.tiles.get(&idx).map_or(false, |t| t.explorers.contains(&pov)) { return Err(format!("you have not explored ({x},{y}); a what-if cannot be asked about a tile you cannot see")); }
            let want_mine = h["mine"].as_bool().unwrap_or(false);
            let u = f::get_unit_at(&g.state, idx).ok_or(format!("no unit at ({x},{y})"))?;
            if (u.owner == pov) != want_mine { return Err(format!("the unit at ({x},{y}) is {} (you wrote {})", if u.owner == pov { "yours" } else { "an enemy's" }, if want_mine { "my unit" } else { "enemy unit" })); }
            let (owner, ty, old, max) = (u.owner, u.unit_type, u.health, f::get_unit_max_health(u));
            let new = if let Some(a) = h["set"].as_f64() { a as f32 } else { old + h["delta"].as_f64().ok_or("no delta")? as f32 }.clamp(1.0, max);
            f::get_unit_at_mut(&mut g.state, idx).ok_or("unit vanished")?.health = new;
            Ok(format!("{} {:?} at ({x},{y}) (player {owner}) has HP {new} instead of {old} (max {max}{})", if owner == pov { "your" } else { "the enemy" }, ty, if (old + h["delta"].as_f64().unwrap_or(0.0) as f32) > max { ", capped at the maximum" } else { "" }))
        }
        "stars" => {
            let id = if h["tribe"].is_null() || h["tribe"] == "me" { pov } else { tribe_arg(g, &h["tribe"])? };
            let d = h["delta"].as_i64().ok_or("no delta")? as i32;
            let t = g.state.tribes.get_mut(&id).ok_or("no such tribe")?;
            let new = (t.stars + d).max(0);
            let was = t.stars; t.stars = new;
            Ok(if id == pov { format!("you have {new} stars instead of {was}") } else { format!("player {id} ({}) has {new} stars instead of {was}", tribe_name(&g.state, id)) })
        }
        op @ ("peace" | "war") => {
            let other = tribe_arg(g, &h["tribe"])?;
            if other == pov { return Err("that is you".into()); }
            let peace = op == "peace";
            for (a, b) in [(pov, other), (other, pov)] {
                let t = g.state.tribes.get_mut(&a).ok_or("no such tribe")?;
                let r = t.relations.entry(b).or_default();
                r.state = if peace { 1 } else { 0 };
                r.has_offered_peace = false;
            }
            if let Some(t) = g.state.tribes.get_mut(&pov) { if !t.known_players.contains(&other) { t.known_players.insert(other); } }
            Ok(format!("{} with {} (player {other})", if peace { "peace" } else { "war" }, tribe_name(&g.state, other)))
        }
        o => Err(format!("cannot apply edit '{o}'. {HYPO_HELP}")),
    }
}

// ---------------------------------------------------------------------------------------------------------------------
// playing a move sequence exactly

fn norm(s: &str) -> String { s.to_lowercase().split_whitespace().collect::<Vec<_>>().join(" ") }

/// Play the labelled moves for `pov` (labels as printed by tools/whatif.py --all, e.g. "Attack Polytaur (5,16)->(4,16)").
/// Returns the per-move event diffs. Err(text) names the first label that is not legal at that point.
fn play_sequence(g: &mut Game, pov: i32, moves: &[String], dice: &mut Option<api::Dice>) -> Result<Vec<Value>, String> {
    let mut out = Vec::new();
    for (n, want) in moves.iter().enumerate() {
        if norm(want) == "endturn" || norm(want) == "end turn" { continue; }
        let legal = api::legal(g);
        let w = norm(want);
        let hit = legal.iter().find(|m| norm(&m.label) == w);
        let Some(m) = hit else {
            let near: Vec<&str> = legal.iter().map(|m| m.label.as_str()).filter(|l| {
                let l = norm(l); let words: Vec<&str> = w.split(' ').collect();
                words.len() >= 2 && l.starts_with(&format!("{} {}", words[0], words[1])) || (words.len() >= 1 && l.contains(words.last().unwrap()))
            }).take(6).collect();
            return Err(format!("move {} of the sequence, \"{want}\", is not legal at that point{}", n + 1,
                if near.is_empty() { String::new() } else { format!(" (similar legal moves: {})", near.join(" | ")) }));
        };
        let before = g.state.clone();
        let label = m.label.clone();
        if api::apply_with_dice(g, m.mv.as_ref(), dice.as_mut()).is_none() { return Err(format!("the engine refused \"{label}\"")); }
        let mut d = crate::whatif::diff(&before, &g.state, pov);
        d["label"] = json!(label);
        out.push(d);
    }
    Ok(out)
}

// ---------------------------------------------------------------------------------------------------------------------
// sampled turns

#[derive(Default, Clone)]
pub struct UnitHit { attacks: u32, killed: bool, dmg: f32, by: Vec<(i32, String)> }

#[derive(Default)]
pub struct Sample {
    unit_hits: HashMap<i32, UnitHit>,        // my unit's tile -> what happened to it in the first enemy round
    city_attacked: HashMap<i32, u32>,        // my city tile -> attacks on the unit standing in it
    city_captured: Vec<i32>,
    attacks: Vec<(i32, String, i32)>,        // (enemy player, attacker unit type, target tile) of every attack on my units
    snaps: Vec<BTreeMap<i32, Vec<f64>>>,     // features of every tribe at the end of round 1..=H
}

fn one_sample(post: &Game, pov: i32, h_max: i32, pol: &Policy, seed: u64) -> Sample {
    let mut game = api::clone(post);
    let mut s = Sample::default();
    let (t0, sp) = (game.state.settings.turn, pov);
    let mut rng = (seed.wrapping_mul(1_000_003) ^ 0x9E37_79B9_7F4A_7C15) | 1;
    // my turn ends; from here the bot policy plays everybody (me too, in rounds 2..H)
    if let Some(m) = game.legal_moves().into_iter().find(|m| m.move_type() == MoveType::EndTurn) { api::apply_search(&mut game, m.as_ref()); }
    let (mut guard, mut h) = (0u64, 1);
    while h <= h_max && guard < 60_000 {
        let (turn, cur) = (game.state.settings.turn, game.state.settings.current_player_turn_id);
        if turn >= t0 + h && (cur == sp || turn > t0 + h) { s.snaps.push(all_feats(&game)); h += 1; continue; }
        if game.is_game_over() { break; }
        guard += 1;
        let legal = game.legal_moves();
        let i = botpolicy2::choose(&game, &legal, pol, &mut rng, true);
        let mv = legal[i].as_ref();
        let first_round = h == 1 && cur != pov;
        let mut watch: Option<(String, i32, i32, f32, i32, String)> = None;   // (kind, target, ..)
        if first_round {
            let kind = api::kind(mv);
            if kind == "Attack" || kind == "Convert" {
                if let (Ok(src), Ok(tgt)) = (mv.source_idx(), mv.target_idx()) {
                    let (src, tgt) = (src as i32, tgt as i32);
                    if let Some(u) = f::get_unit_at(&game.state, tgt).filter(|u| u.owner == pov) {
                        let att = f::get_unit_at(&game.state, src).map(|a| format!("{:?}", a.unit_type)).unwrap_or_default();
                        watch = Some((kind, tgt, cur, u.health, src, att));
                    }
                }
            } else if kind == "Capture" {
                if let Ok(src) = mv.source_idx() { if f::get_city_at(&game.state, src as i32).map_or(false, |c| c.owner == pov) { s.city_captured.push(src as i32); } }
            }
        }
        if api::apply_search(&mut game, mv).is_none() { break; }
        if let Some((_, tgt, who, hp0, _src, att)) = watch {
            let now = f::get_unit_at(&game.state, tgt).filter(|u| u.owner == pov);
            let e = s.unit_hits.entry(tgt).or_default();
            e.attacks += 1;
            e.by.push((who, att.clone()));
            match now { Some(u) => e.dmg += (hp0 - u.health).max(0.0), None => { e.killed = true; e.dmg += hp0; } }
            s.attacks.push((who, att, tgt));
            if f::get_city_at(&game.state, tgt).map_or(false, |c| c.owner == pov) || f::get_city_at(&post.state, tgt).map_or(false, |c| c.owner == pov) { *s.city_attacked.entry(tgt).or_default() += 1; }
        }
    }
    while h <= h_max { s.snaps.push(all_feats(&game)); h += 1; }   // game over: the final state stands
    s
}

fn pct(sorted: &[f64], p: f64) -> f64 {
    if sorted.is_empty() { return 0.0; }
    let r = p * (sorted.len() - 1) as f64; let (lo, hi) = (r.floor() as usize, r.ceil() as usize);
    sorted[lo] + (sorted[hi] - sorted[lo]) * (r - lo as f64)
}

/// [mean, p10, p90, standard error of the mean] rounded to 2 places.
fn spread(v: &[f64]) -> Value {
    if v.is_empty() { return json!([0, 0, 0, 0]); }
    let n = v.len() as f64; let m = v.iter().sum::<f64>() / n;
    let var = if v.len() > 1 { v.iter().map(|x| (x - m).powi(2)).sum::<f64>() / (n - 1.0) } else { 0.0 };
    let mut s = v.to_vec(); s.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let r = |x: f64| (x * 100.0).round() / 100.0;
    json!([r(m), r(pct(&s, 0.1)), r(pct(&s, 0.9)), r((var / n).sqrt())])
}

fn unit_value(u: &UnitState) -> f64 { get_unit_setting(u.unit_type).cost as f64 }

/// Tribes with a unit or city within `reach` tiles of one of pov's cities or units, on tiles pov has explored. Most units first.
fn nearby_tribes(g: &Game, pov: i32, reach: i32) -> Vec<(i32, usize)> {
    let sz = g.state.settings.size;
    let me = &g.state.tribes[&pov];
    let mine: Vec<i32> = me.units.iter().map(|u| u.coords.idx).chain(me.cities.iter().map(|c| c.idx)).collect();
    let mut out = Vec::new();
    for (id, t) in g.state.tribes.iter().filter(|(id, _)| **id != pov) {
        let seen = |i: i32| g.state.tiles.get(&i).map_or(false, |x| x.explorers.contains(&pov));
        let n = t.units.iter().map(|u| u.coords.idx).chain(t.cities.iter().map(|c| c.idx)).filter(|&i| seen(i) && mine.iter().any(|&m| f::get_chebyshev_distance(m, i, sz) <= reach)).count();
        if n > 0 { out.push((*id, n)); }
    }
    out.sort_by_key(|x| std::cmp::Reverse(x.1));
    out
}

/// K sampled futures of `post` (the position after the player's moves, the player still to move): the turn ends, the bot policy plays on
/// for `h_max` rounds. Threads share nothing but the starting state; sample i always uses seed `seed*7919 + i`.
pub fn draw(post: &Game, pov: i32, h_max: i32, k: usize, pol: &Policy, seed: u64, threads: usize) -> Vec<Sample> {
    let next = std::sync::atomic::AtomicUsize::new(0);
    let mut all: Vec<(usize, Sample)> = Vec::new();
    std::thread::scope(|sc| {
        let hs: Vec<_> = (0..threads.max(1)).map(|_| sc.spawn(|| {
            let mut mine = Vec::new();
            loop {
                let i = next.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
                if i >= k { break; }
                let r = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| one_sample(post, pov, h_max, pol, seed * 7919 + i as u64)));
                if let Ok(s) = r { mine.push((i, s)); }
            }
            mine
        })).collect();
        for h in hs { if let Ok(v) = h.join() { all.extend(v); } }
    });
    all.sort_by_key(|x| x.0);
    all.into_iter().map(|x| x.1).collect()
}

fn option_run(g: &Game, pov: i32, opt: &Value, k: usize, h_max: i32, pol: &Policy, seed: u64, threads: usize, dist: Option<&str>, want_feats: bool) -> Value {
    let name = opt["name"].as_str().unwrap_or("?").to_string();
    let moves: Vec<String> = opt["moves"].as_array().map(|a| a.iter().filter_map(|x| x.as_str().map(String::from)).collect()).unwrap_or_default();
    let mut post = api::clone(g);
    let mut dice = dist.and_then(|p| api::Dice::from_file(p, seed).ok());
    let steps = match play_sequence(&mut post, pov, &moves, &mut dice) { Ok(s) => s, Err(e) => return json!({"name": name, "moves": moves, "error": e}) };
    let sz = post.state.settings.size;
    let random_step = steps.iter().any(|s| s["events"].as_array().map_or(false, |e| e.iter().any(|x| x.to_string().contains("Ruin"))));

    // --- the exact position after the sequence
    let view = fog::player_view(&post, pov);
    let danger = crate::whatif::reply_json(&view, pov);
    let near = nearby_tribes(&post, pov, 5);
    let start = all_feats(&post);
    let me = &post.state.tribes[&pov];
    let my_units: Vec<(i32, UnitState)> = me.units.iter().map(|u| (u.coords.idx, u.clone())).collect();
    let my_cities: Vec<(i32, String)> = me.cities.iter().map(|c| (c.idx, c.name.clone())).collect();

    // --- K sampled futures (threads; the game state is cloned per sample)
    let samples = draw(&post, pov, h_max, k, pol, seed, threads);
    let n = samples.len();
    if n == 0 { return json!({"name": name, "moves": moves, "error": "every sampled turn failed"}); }
    let nf = n as f64;

    // --- the first enemy round: who is attacked
    let mut units_out = Vec::new();
    for (idx, u) in &my_units {
        let hits: Vec<&UnitHit> = samples.iter().filter_map(|s| s.unit_hits.get(idx)).collect();
        let (x, y) = xy(sz, *idx);
        let mut by: BTreeMap<String, u32> = BTreeMap::new();
        for h in &hits { for (who, ty) in &h.by { *by.entry(format!("{} {}", tribe_name(&post.state, *who), ty)).or_default() += 1; } }
        let mut by: Vec<(String, u32)> = by.into_iter().collect(); by.sort_by_key(|x| std::cmp::Reverse(x.1));
        units_out.push(json!({"x": x, "y": y, "type": format!("{:?}", u.unit_type), "hp": u.health, "max": f::get_unit_max_health(u), "cost": unit_value(u),
            "p_attacked": hits.len() as f64 / nf, "p_killed": hits.iter().filter(|h| h.killed).count() as f64 / nf,
            "mean_damage": hits.iter().map(|h| h.dmg as f64).sum::<f64>() / nf,
            "attackers": by.iter().take(3).map(|(k, c)| json!({"who": k, "share": *c as f64 / hits.len().max(1) as f64})).collect::<Vec<_>>()}));
    }
    let cities_out: Vec<Value> = my_cities.iter().map(|(idx, nm)| {
        let (x, y) = xy(sz, *idx);
        json!({"x": x, "y": y, "name": nm, "p_unit_in_it_attacked": samples.iter().filter(|s| s.city_attacked.contains_key(idx)).count() as f64 / nf,
               "p_captured": samples.iter().filter(|s| s.city_captured.contains(idx)).count() as f64 / nf})
    }).collect();
    let lost_units: Vec<f64> = samples.iter().map(|s| s.unit_hits.values().filter(|h| h.killed).count() as f64).collect();
    let lost_value: Vec<f64> = samples.iter().map(|s| my_units.iter().filter(|(i, _)| s.unit_hits.get(i).map_or(false, |h| h.killed)).map(|(_, u)| unit_value(u)).sum()).collect();
    let lost_cities: Vec<f64> = samples.iter().map(|s| s.city_captured.len() as f64).collect();
    let mut pairs: BTreeMap<(i32, String, i32), usize> = BTreeMap::new();
    for s in &samples {
        let mut seen = std::collections::HashSet::new();
        for a in &s.attacks { if seen.insert(a.clone()) { *pairs.entry(a.clone()).or_default() += 1; } }
    }
    let mut pairs: Vec<_> = pairs.into_iter().collect(); pairs.sort_by_key(|x| std::cmp::Reverse(x.1));
    let top_attacks: Vec<Value> = pairs.iter().take(5).map(|((who, ty, tgt), c)| {
        let (x, y) = xy(sz, *tgt);
        let tgt_ty = my_units.iter().find(|(i, _)| i == tgt).map(|(_, u)| format!("{:?}", u.unit_type)).unwrap_or_default();
        json!({"enemy": format!("{} {}", tribe_name(&post.state, *who), ty), "player": who, "target": format!("{tgt_ty} at ({x},{y})"), "chance": *c as f64 / nf})
    }).collect();

    // --- standing of the tribes at each horizon
    let mut shown: Vec<i32> = vec![pov];
    shown.extend(near.iter().take(3).map(|x| x.0));
    let mut tribes = serde_json::Map::new();
    for id in &shown {
        let mut per_h = Vec::new();
        for hi in 0..h_max as usize {
            let mut o = serde_json::Map::new();
            for (nm, fi) in SHOWN { let v: Vec<f64> = samples.iter().filter_map(|s| s.snaps.get(hi)).map(|m| m[id][fi]).collect(); o.insert(nm.into(), spread(&v)); }
            let alive: f64 = samples.iter().filter_map(|s| s.snaps.get(hi)).map(|m| m[id][0]).sum::<f64>() / nf;
            o.insert("alive".into(), json!((alive * 1000.0).round() / 1000.0));
            per_h.push(Value::Object(o));
        }
        let s0 = &start[id];
        tribes.insert(id.to_string(), json!({"tribe": tribe_name(&post.state, *id), "bot": post.state.tribes[id].bot, "start": SHOWN.iter().map(|(nm, fi)| (nm.to_string(), json!(s0[*fi]))).collect::<serde_json::Map<_, _>>(), "rounds": per_h}));
    }
    // other tribes' score at the last horizon, for the "who leads" estimate
    let feats_h: Value = if want_feats {
        json!(samples.iter().map(|s| { let m = s.snaps.last().cloned().unwrap_or_default(); m.iter().map(|(id, v)| (id.to_string(), json!(v.iter().map(|x| (x * 100.0).round() / 100.0).collect::<Vec<_>>()))).collect::<serde_json::Map<_, _>>() }).collect::<Vec<_>>())
    } else { Value::Null };
    let start_json: serde_json::Map<String, Value> = start.iter().map(|(id, v)| (id.to_string(), json!(v.iter().map(|x| (x * 100.0).round() / 100.0).collect::<Vec<_>>()))).collect();

    json!({
        "name": name, "moves": moves,
        "exact": {"steps": steps, "random": random_step, "stars": me.stars,
                  "my_units": my_units.iter().map(|(i, u)| { let (x, y) = xy(sz, *i); json!({"x": x, "y": y, "type": format!("{:?}", u.unit_type), "hp": u.health}) }).collect::<Vec<_>>(),
                  "danger": danger},
        "estimate": {"k": n, "h": h_max,
            "reply": {"units": units_out, "cities": cities_out, "lost_units": spread(&lost_units), "lost_value": spread(&lost_value), "lost_cities": spread(&lost_cities),
                      "p_any_unit_lost": lost_units.iter().filter(|x| **x > 0.0).count() as f64 / nf,
                      "p_any_city_lost": lost_cities.iter().filter(|x| **x > 0.0).count() as f64 / nf, "top_attacks": top_attacks},
            "tribes": tribes, "near": near.iter().take(3).map(|x| json!({"id": x.0, "tribe": tribe_name(&post.state, x.0), "near_objects": x.1})).collect::<Vec<_>>()},
        "start_feats": start_json, "feats_h": feats_h,
        "tribe_names": post.state.tribes.iter().map(|(id, t)| (id.to_string(), json!(format!("{:?}", t.tribe_type)))).collect::<serde_json::Map<_, _>>(),
    })
}

pub fn run(save: &Value, job: &Value) -> Result<Value, String> {
    let g0 = fog::load_exact(save, "current", 1)?;
    let humans: Vec<i32> = g0.state.tribes.iter().filter(|(_, t)| !t.bot).map(|(k, _)| *k).collect();
    let pov = job["player"].as_i64().map(|x| x as i32).or_else(|| humans.first().copied()).ok_or("no human player; pass --player")?;
    if !g0.state.tribes.contains_key(&pov) { return Err(format!("no player {pov} in this save")); }
    let mut g = fog::load_exact(save, "current", pov)?;
    g.state.settings.current_player_turn_id = pov;
    let mut applied = Vec::new();
    for h in job["hypos"].as_array().cloned().unwrap_or_default() { applied.push(apply_hypo(&mut g, pov, &h)?); }
    let pol = Policy::from_file(job["policy"].as_str().ok_or("no policy file")?)?;
    let k = job["k"].as_u64().unwrap_or(20) as usize;
    let h = job["h"].as_i64().unwrap_or(1).clamp(1, 4) as i32;
    let seed = job["seed"].as_u64().unwrap_or(1);
    let threads = job["threads"].as_u64().unwrap_or(4) as usize;
    let dist = job["dist"].as_str();
    let want_feats = job["feats"].as_bool().unwrap_or(false);
    let opts = job["options"].as_array().ok_or("no options")?;
    let t0 = std::time::Instant::now();
    let results: Vec<Value> = opts.iter().map(|o| option_run(&g, pov, o, k, h, &pol, seed, threads, dist, want_feats)).collect();
    let me = &g.state.tribes[&pov];
    Ok(json!({"player": pov, "tribe": format!("{:?}", me.tribe_type), "turn": g.state.settings.turn, "stars": me.stars, "hypos": applied,
              "k": k, "h": h, "secs": t0.elapsed().as_secs_f64(), "options": results}))
}

// ---------------------------------------------------------------------------------------------------------------------
// validation probe: predicted reply vs the real reply (pfreplay hook, env PF_REPLY=k; tools/scenario_validate.py)

struct Active {
    turn: i32,
    units: Vec<(i32, String, f32)>,             // my units when I ended the turn: tile, type, hp
    pred_att: HashMap<i32, f64>, pred_kill: HashMap<i32, f64>,
    pred_lost: Vec<f64>,                        // units lost per sample
    pred_pairs: HashMap<(i32, i32), f64>,       // (enemy player, my tile) -> chance of at least one attack
    pred_city_cap: HashMap<i32, f64>,
    k: usize,
    real: HashMap<i32, (bool, f32)>,            // tile -> (killed, damage taken) of my units attacked in the real reply
    real_pairs: std::collections::BTreeSet<(i32, i32)>,
    real_city_cap: Vec<i32>,
    prev_hp: HashMap<i32, f32>, prev_cities: Vec<i32>,
}

pub struct ReplyProbe { k: usize, pol: Policy, pov: i32, active: Option<Active>, pub results: Vec<Value> }

impl ReplyProbe {
    pub fn from_env() -> Option<Self> {
        let k: usize = std::env::var("PF_REPLY").ok()?.parse().ok()?;
        let path = std::env::var("PF_REPLY_POLICY").unwrap_or_else(|_| "data/bot_policy_v3.json".into());
        Some(ReplyProbe { k, pol: Policy::from_file(&path).ok()?, pov: 0, active: None, results: Vec::new() })
    }

    fn my_state(g: &Game, pov: i32) -> (HashMap<i32, f32>, Vec<i32>) {
        let t = &g.state.tribes[&pov];
        (t.units.iter().map(|u| (u.coords.idx, u.health)).collect(), t.cities.iter().map(|c| c.idx).collect())
    }

    /// Call before a logged action (`t` = its type, `p` = its first byte, the acting player) is applied.
    pub fn before(&mut self, g: &Game, t: i64, p: i64) {
        if self.pov == 0 { self.pov = g.state.tribes.iter().find(|(_, t)| !t.bot).map_or(-1, |(k, _)| *k); }
        if self.pov < 0 { return; }
        let pov = self.pov;
        if p == pov as i64 && !matches!(t, 20 | 21) && self.active.is_some() { self.finish(); }
        if t == 15 && p == pov as i64 && self.active.is_none() { self.start(g); }
    }

    fn start(&mut self, g: &Game) {
        let pov = self.pov;
        let mut g2 = api::clone(g);
        g2.state.settings.current_player_turn_id = pov;
        if !g2.legal_moves().iter().any(|m| m.move_type() == MoveType::EndTurn) { return; }
        let samples = draw(&g2, pov, 1, self.k, &self.pol, 17 + g.state.settings.turn as u64, 2);
        if samples.is_empty() { return; }
        let n = samples.len() as f64;
        let t = &g.state.tribes[&pov];
        let units: Vec<(i32, String, f32)> = t.units.iter().map(|u| (u.coords.idx, format!("{:?}", u.unit_type), u.health)).collect();
        let mut a = Active { turn: g.state.settings.turn, pred_att: HashMap::new(), pred_kill: HashMap::new(), pred_lost: Vec::new(), pred_pairs: HashMap::new(), pred_city_cap: HashMap::new(),
            k: samples.len(), real: HashMap::new(), real_pairs: Default::default(), real_city_cap: Vec::new(), units, prev_hp: HashMap::new(), prev_cities: Vec::new() };
        for s in &samples {
            for (tile, h) in &s.unit_hits {
                if h.attacks > 0 { *a.pred_att.entry(*tile).or_default() += 1.0 / n; }
                if h.killed { *a.pred_kill.entry(*tile).or_default() += 1.0 / n; }
            }
            a.pred_lost.push(s.unit_hits.values().filter(|h| h.killed).count() as f64);
            let mut seen = std::collections::HashSet::new();
            for (who, _, tgt) in &s.attacks { if seen.insert((*who, *tgt)) { *a.pred_pairs.entry((*who, *tgt)).or_default() += 1.0 / n; } }
            for c in &s.city_captured { *a.pred_city_cap.entry(*c).or_default() += 1.0 / n; }
        }
        let (hp, cities) = Self::my_state(g, pov);
        a.prev_hp = hp; a.prev_cities = cities;
        self.active = Some(a);
    }

    /// Call after the logged action was applied.
    pub fn after(&mut self, g: &Game, p: i64) {
        let pov = self.pov;
        let Some(a) = self.active.as_mut() else { return };
        let (now, cities) = Self::my_state(g, pov);
        if p != pov as i64 && p != 255 {
            for (tile, hp0) in a.prev_hp.clone() {
                match now.get(&tile) {
                    None => { let e = a.real.entry(tile).or_insert((false, 0.0)); e.0 = true; e.1 += hp0; a.real_pairs.insert((p as i32, tile)); }
                    Some(h) if *h < hp0 - 0.01 => { let e = a.real.entry(tile).or_insert((false, 0.0)); e.1 += hp0 - h; a.real_pairs.insert((p as i32, tile)); }
                    _ => {}
                }
            }
            for c in &a.prev_cities { if !cities.contains(c) { a.real_city_cap.push(*c); } }
        }
        a.prev_hp = now; a.prev_cities = cities;
    }

    /// Close the open window (also call once after the last action).
    pub fn finish(&mut self) {
        let Some(a) = self.active.take() else { return };
        let n = a.pred_lost.len() as f64;
        let units: Vec<Value> = a.units.iter().map(|(tile, ty, hp)| json!({"tile": tile, "type": ty, "hp": hp,
            "p_att": a.pred_att.get(tile).copied().unwrap_or(0.0), "p_kill": a.pred_kill.get(tile).copied().unwrap_or(0.0),
            "real_att": a.real.contains_key(tile), "real_kill": a.real.get(tile).map_or(false, |x| x.0), "real_dmg": a.real.get(tile).map_or(0.0, |x| x.1)})).collect();
        let real_lost = a.real.values().filter(|x| x.0).count() as f64;
        let mut pairs: Vec<((i32, i32), f64)> = a.pred_pairs.iter().map(|(k, v)| (*k, *v)).collect();
        pairs.sort_by(|x, y| y.1.partial_cmp(&x.1).unwrap().then(x.0.cmp(&y.0)));
        self.results.push(json!({"turn": a.turn, "k": a.k, "units": units, "real_lost": real_lost,
            "pred_lost_le": a.pred_lost.iter().filter(|x| **x <= real_lost).count() as f64 / n, "pred_lost_eq": a.pred_lost.iter().filter(|x| **x == real_lost).count() as f64 / n,
            "pred_lost_mean": a.pred_lost.iter().sum::<f64>() / n,
            "pairs": pairs.iter().take(8).map(|(k, v)| json!({"who": k.0, "tile": k.1, "p": v})).collect::<Vec<_>>(),
            "pairs_all": pairs.len(),
            "real_pairs": a.real_pairs.iter().map(|k| json!({"who": k.0, "tile": k.1, "p": a.pred_pairs.get(k).copied().unwrap_or(0.0)})).collect::<Vec<_>>(),
            "cities": {"pred_capture": a.pred_city_cap.iter().map(|(k, v)| json!([k, v])).collect::<Vec<_>>(), "real_capture": a.real_city_cap}}));
    }
}
