//! Play the bot policy (src/botpolicy.rs) forward from a real save and report what happened, per tribe.
//! usage: pfbot <policy.json> <jobs.json>      (jobs written by tools/bot_dist.py)
//! job: {"tag", "start": decoded save, "player": to move, "end_turns": n EndTurns to play, "runs": r, "seed": s, "sample": bool}
//!      or {"tag", "start", "player", "state_only": true}  -> just the summary of that save (the real outcome).
//! Prints one `PFBOT {json}` line per job: before/after summaries per tribe and the move counts per run.
use polyfish::api;
use polyfish::botpolicy2::{self, Policy};
use polyfish::game::Game;
use polyfish::moves::*;
use polyfish::types::*;
use serde_json::{json, Value};
use std::collections::BTreeMap;

fn summary(g: &Game) -> Value {
    let m: serde_json::Map<String, Value> = g.state.tribes.iter().map(|(id, t)| (id.to_string(), json!({
        "tribe": format!("{:?}", t.tribe_type), "bot": t.bot, "stars": t.stars, "cities": t.cities.len(), "units": t.units.len(),
        "pop": t.cities.iter().map(|c| c.population).sum::<i32>(), "kills": t.kills, "casualties": t.casualties, "techs": t.tech_vanilla.len(), "score": t.score,
    }))).collect();
    Value::Object(m)
}

fn run(job: &Value, pol: &Policy, run_i: u64) -> Result<Value, String> {
    let player = job["player"].as_i64().unwrap_or(1) as i32;
    let mut game = api::load_save_file(job["start"].as_str().ok_or("no start")?, "current", player)?;
    let before = summary(&game);
    if job["state_only"].as_bool() == Some(true) { return Ok(json!({"before": before})); }
    let sample = job["sample"].as_bool().unwrap_or(true);
    let mut rng: u64 = (job["seed"].as_u64().unwrap_or(1) * 1_000_003 + run_i * 7919) | 1;
    let mut dice = api::Dice::from_file("data/distributions.json", rng).ok();
    let random = job["random"].as_bool().unwrap_or(false);   // baseline: uniform random legal move, EndTurn with chance 1/8
    let end_turns = job["end_turns"].as_u64().unwrap_or(1);
    let mut done = 0u64;
    let mut counts: BTreeMap<String, BTreeMap<String, i64>> = BTreeMap::new();   // tribe -> "Group" / "Train:Unit" -> n
    let mut guard = 0;
    while done < end_turns && guard < 20_000 && !game.is_game_over() {
        guard += 1;
        let me = game.state.settings.current_player_turn_id;
        let legal = game.legal_moves();
        let i = if random { botpolicy2::choose_random(&legal, &mut rng) } else { botpolicy2::choose(&game, &legal, pol, &mut rng, sample) };
        let mv = legal[i].as_ref();
        let mut key = botpolicy2::group(mv);
        if mv.move_type() == MoveType::Summon && key == "Summon" { key = format!("Train:{}", botpolicy2::named(mv)); }
        let is_end = mv.move_type() == MoveType::EndTurn;
        *counts.entry(me.to_string()).or_default().entry(key).or_insert(0) += 1;
        if is_end {   // bot-model-3: stars left when the turn ends and whether a unit could still be trained
            let e = counts.entry(me.to_string()).or_default();
            *e.entry("EndStars".into()).or_insert(0) += game.state.tribes.get(&me).map_or(0, |t| t.stars) as i64;
            *e.entry("EndCanTrain".into()).or_insert(0) += legal.iter().any(|m| m.move_type() == MoveType::Summon) as i64;
        }
        if api::apply_with_dice(&mut game, mv, dice.as_mut()).is_none() { return Err(format!("refused: {}", api::label(&game.state, mv))); }
        if is_end { done += 1; }
    }
    Ok(json!({"before": before, "after": summary(&game), "counts": counts, "turn": game.state.settings.turn, "player": game.state.settings.current_player_turn_id, "moves": guard}))
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let pol = Policy::from_file(&a[1]).unwrap_or_else(|e| { eprintln!("{e}"); std::process::exit(2) });
    let jobs: Value = serde_json::from_str(&std::fs::read_to_string(&a[2]).expect("jobs file")).expect("jobs json");
    for job in jobs.as_array().expect("jobs list") {
        let runs = if job["state_only"].as_bool() == Some(true) { 1 } else { job["runs"].as_u64().unwrap_or(1) };
        let mut out = Vec::new();
        for r in 0..runs {
            let res = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| run(job, &pol, r)));
            out.push(match res { Ok(Ok(v)) => v, Ok(Err(e)) => json!({"error": e}), Err(_) => json!({"error": "panic"}) });
        }
        println!("PFBOT {}", json!({"tag": job["tag"], "runs": out}));
    }
}
