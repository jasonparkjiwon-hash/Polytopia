//! Forward-model entry point (fm-accept; library calls in src/api.rs, docs in sim/README.md).
//! usage:
//!   pfapi moves <save.json> <player>             legal moves for <player> at the end of the save: one JSON line each {key, label}
//!   pfapi serve                                  JSON-lines session on stdin/stdout (tools/pf_api.py drives it)
//!   pfapi bench <save.json> <player> [secs]      speed: move generation, apply+undo, clone, random playouts
//!   pfapi dice <distributions.json> <save.json> <player> [n]   sample n ruin rewards; frequencies vs the table
use polyfish::actions::UndoCallback;
use polyfish::api;
use polyfish::game::Game;
use polyfish::types::*;
use serde_json::{json, Value};
use std::io::{BufRead, Write};
use std::time::Instant;

fn load(a: &[String], k: usize) -> Game {
    let player: i32 = a.get(k + 1).and_then(|s| s.parse().ok()).unwrap_or(1);
    api::load_save_file(&a[k], "current", player).unwrap_or_else(|e| { eprintln!("{e}"); std::process::exit(2) })
}

/// Per-tribe summary: stars, cities, units [type, x, y, hp].
fn summary(g: &Game) -> Value {
    let n = g.state.settings.size;
    let tribes: serde_json::Map<String, Value> = g.state.tribes.iter().map(|(id, t)| (id.to_string(), json!({
        "stars": t.stars, "cities": t.cities.len(),
        "units": t.units.iter().map(|u| json!([format!("{:?}", u.unit_type), u.coords.idx % n, u.coords.idx / n, u.health])).collect::<Vec<_>>(),
    }))).collect();
    json!({"turn": g.state.settings.turn, "player": g.state.settings.current_player_turn_id, "over": g.is_game_over(),
           "fingerprint": api::fingerprint(&g.state).to_string(), "tribes": tribes})
}

fn serve() {
    // a stack of positions: each entry is the game plus the undos played on it since it was pushed
    let mut stack: Vec<(Game, Vec<UndoCallback>)> = Vec::new();
    let mut dice: Option<api::Dice> = None;
    let stdin = std::io::stdin();
    let mut out = std::io::stdout();
    for line in stdin.lock().lines() {
        let Ok(line) = line else { break };
        let r = (|| -> Result<Value, String> {
            let c: Value = serde_json::from_str(&line).map_err(|e| e.to_string())?;
            let cmd = c["cmd"].as_str().unwrap_or("");
            if cmd == "load" {
                let g = api::load_save_file(c["path"].as_str().ok_or("path")?, c["which"].as_str().unwrap_or("current"), c["player"].as_i64().unwrap_or(1) as i32)?;
                stack = vec![(g, Vec::new())];
                return Ok(summary(&stack[0].0));
            }
            if cmd == "dice" {
                dice = Some(api::Dice::from_file(c["path"].as_str().ok_or("path")?, c["seed"].as_u64().unwrap_or(1))?);
                return Ok(json!({"ok": true}));
            }
            let (g, undos) = stack.last_mut().ok_or("load first")?;
            match cmd {
                "moves" => Ok(json!(api::legal(g).iter().map(|m| json!({"key": m.key, "label": m.label})).collect::<Vec<_>>())),
                "play" => {
                    let mv = api::find(g, &c["key"]).ok_or("not legal now")?;
                    let u = api::apply_with_dice(g, mv.as_ref(), dice.as_mut()).ok_or("refused")?;
                    undos.push(u);
                    Ok(summary(g))
                }
                "end" => { let u = api::end_turn(g).ok_or("no end turn")?; undos.push(u); Ok(summary(g)) }
                "undo" => { let u = undos.pop().ok_or("nothing to undo")?; api::undo(g, u); Ok(summary(g)) }
                "state" => Ok(summary(g)),
                "push" => { let c2 = api::clone(g); stack.push((c2, Vec::new())); Ok(json!({"depth": stack.len()})) }
                "pop" => { if stack.len() > 1 { stack.pop(); } Ok(json!({"depth": stack.len()})) }
                _ => Err(format!("unknown cmd {cmd}")),
            }
        })();
        let v = match r { Ok(v) => json!({"ok": v}), Err(e) => json!({"error": e}) };
        let _ = writeln!(out, "{v}");
        let _ = out.flush();
    }
}

struct Rng(u64);
impl Rng {
    fn next(&mut self) -> u64 { self.0 ^= self.0 << 13; self.0 ^= self.0 >> 7; self.0 ^= self.0 << 17; self.0 }
    fn below(&mut self, n: usize) -> usize { (self.next() % n.max(1) as u64) as usize }
}

/// Random playout policy: end the turn with chance 1/8 (or when it's the only move), else a random other move.
fn random_turn(g: &mut Game, rng: &mut Rng, moves: &mut u64) {
    for _ in 0..200 {
        if g.is_game_over() { return; }
        let ms = g.legal_moves();
        *moves += 1;
        let others: Vec<_> = ms.iter().filter(|m| m.move_type() != MoveType::EndTurn).collect();
        if others.is_empty() || rng.below(8) == 0 { break; }
        g.play_move(others[rng.below(others.len())].as_ref());
    }
    api::end_turn(g);
}

fn bench(a: &[String]) {
    let mut g0 = load(a, 2);
    if a.get(3).map(|s| s.as_str()) == Some("0") {
        // player 0: the tribe with the most units moves (the busiest move list)
        let p = g0.state.tribes.iter().max_by_key(|(_, t)| t.units.len()).map(|(k, _)| *k).unwrap_or(1);
        g0 = api::load_save_file(&a[2], "current", p).unwrap();
    }
    let secs: f64 = a.get(4).and_then(|s| s.parse().ok()).unwrap_or(2.0);
    let n_tribes = g0.state.tribes.len();
    let n_units: usize = g0.state.tribes.values().map(|t| t.units.len()).sum();
    // 1. move generation
    let (t, mut calls, mut listed) = (Instant::now(), 0u64, 0u64);
    while t.elapsed().as_secs_f64() < secs / 4.0 { listed += g0.legal_moves().len() as u64; calls += 1; }
    let gen_s = calls as f64 / t.elapsed().as_secs_f64();
    let listed_s = listed as f64 / t.elapsed().as_secs_f64();
    // 2. apply + undo every non-EndTurn legal move in turn
    let mut g = g0.clone();
    let ms: Vec<_> = g.legal_moves().into_iter().filter(|m| m.move_type() != MoveType::EndTurn).collect();
    let (t, mut applied) = (Instant::now(), 0u64);
    while t.elapsed().as_secs_f64() < secs / 4.0 && !ms.is_empty() {
        for m in &ms { if let Some(u) = g.play_move(m.as_ref()) { u(&mut g.state); applied += 1; } }
    }
    let apply_s = applied as f64 / t.elapsed().as_secs_f64();
    // 2b. the same through simulate_move (Polyfish's MCTS path: no reveals) and the pieces of play_move
    let (t, mut sim) = (Instant::now(), 0u64);
    while t.elapsed().as_secs_f64() < secs / 8.0 && !ms.is_empty() {
        for m in &ms { if let Some(u) = g.simulate_move(m.as_ref()) { u(&mut g.state); sim += 1; } }
    }
    let sim_s = sim as f64 / t.elapsed().as_secs_f64();
    let (t, mut obs) = (Instant::now(), 0u64);
    while t.elapsed().as_secs_f64() < secs / 16.0 { let u = polyfish::memory::observe_all(&mut g.state); u(&mut g.state); obs += 1; }
    let observe_s = obs as f64 / t.elapsed().as_secs_f64();
    // 3. clone
    let (t, mut clones) = (Instant::now(), 0u64);
    while t.elapsed().as_secs_f64() < secs / 8.0 { std::hint::black_box(g0.clone()); clones += 1; }
    let clone_s = clones as f64 / t.elapsed().as_secs_f64();
    // 4. random playouts: clone, then whole rounds (every tribe plays a random turn) until time runs out
    let mut rng = Rng(0x9E3779B97F4A7C15);
    let (t, mut turns, mut gens, mut playouts) = (Instant::now(), 0u64, 0u64, 0u64);
    while t.elapsed().as_secs_f64() < secs * 3.0 / 8.0 {
        let mut p = g0.clone();
        playouts += 1;
        for _ in 0..(3 * n_tribes) { if p.is_game_over() { break; } random_turn(&mut p, &mut rng, &mut gens); turns += 1; }
    }
    let el = t.elapsed().as_secs_f64();
    println!("{}", json!({"turn": g0.state.settings.turn, "player": g0.state.settings.current_player_turn_id, "tribes": n_tribes, "units": n_units, "legal_now": ms.len() + 1,
        "movegen_per_s": gen_s.round(), "moves_listed_per_s": listed_s.round(), "apply_undo_per_s": apply_s.round(), "simulate_undo_per_s": sim_s.round(), "fog_memory_observe_per_s": observe_s.round(),
        "clone_per_s": clone_s.round(), "playout_player_turns_per_s": (turns as f64 / el * 10.0).round() / 10.0,
        "playout_rounds_per_s": (turns as f64 / el / n_tribes as f64 * 100.0).round() / 100.0,
        "playout_movegens_per_s": (gens as f64 / el).round(), "playouts": playouts}));
}

fn dice(a: &[String]) {
    let mut d = api::Dice::from_file(&a[2], 7).unwrap_or_else(|e| { eprintln!("{e}"); std::process::exit(2) });
    let g = load(a, 3);
    let n: usize = a.get(5).and_then(|s| s.parse().ok()).unwrap_or(20000);
    let mut out = serde_json::Map::new();
    // one land tile and one water tile of the map, each sampled n times
    for water in [false, true] {
        let Some((&k, _)) = g.state.tiles.iter().find(|(_, t)| t.is_water_terrain() == water) else { continue };
        let w = d.ruin_weights(&g.state, k);
        let tot: f64 = w.iter().map(|x| x.1).sum();
        let mut c = std::collections::BTreeMap::new();
        for _ in 0..n { *c.entry(format!("{:?}", d.sample_ruin(&g.state, k))).or_insert(0usize) += 1; }
        let tvd: f64 = w.iter().map(|(r, x)| (x / tot - *c.get(&format!("{r:?}")).unwrap_or(&0) as f64 / n as f64).abs()).sum::<f64>() / 2.0;
        // play it: an Examine Ruins with each eligible reward must execute
        let mut played = 0;
        for (r, _) in &w {
            let mut g2 = g.clone();
            let st0 = g2.state.tribes.values().map(|t| (t.stars, t.units.len(), t.tech_vanilla.len())).collect::<Vec<_>>();
            let ok = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                let _u = polyfish::actions::structure::capture_ruin(&mut g2.state, k, Some(*r), None, None);
            })).is_ok();
            let st1 = g2.state.tribes.values().map(|t| (t.stars, t.units.len(), t.tech_vanilla.len())).collect::<Vec<_>>();
            // stars, a unit or a tech must show up (population and explorer change cities and tiles instead)
            let visible = matches!(r, RuinsRewardType::PopGrowth | RuinsRewardType::Explorer) || st0 != st1;
            if ok && visible { played += 1; }
        }
        out.insert(if water { "water" } else { "land" }.into(), json!({"table": w.iter().map(|(r, x)| (format!("{r:?}"), x / tot)).collect::<Vec<_>>(),
            "sampled": c, "tvd": (tvd * 1000.0).round() / 1000.0, "rewards_executed": played, "rewards": w.len()}));
    }
    let events: Vec<Value> = api::RANDOM_EVENTS.iter().map(|(e, w, c)| json!({"event": e, "where": w, "covered": c})).collect();
    println!("{}", json!({"ruin": out, "events": events}));
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    if let Ok(f) = std::env::var("PF_FLAGS") {
        for n in polyfish::v123_flags::set_from(&f) { eprintln!("PF_FLAGS: unknown switch {n}"); }
    }
    match a.get(1).map(|s| s.as_str()) {
        Some("moves") => {
            let g = load(&a, 2);
            for m in api::legal(&g) { println!("{}", json!({"key": m.key, "label": m.label})); }
        }
        Some("serve") => serve(),
        Some("bench") => bench(&a),
        Some("dice") => dice(&a),
        _ => eprintln!("usage: pfapi moves|serve|bench|dice ... (see the header of src/bin/pfapi.rs)"),
    }
}
