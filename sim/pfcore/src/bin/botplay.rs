//! bot-policy playouts: play every player with the bot policy from a save for some rounds, and print each
//! tribe's units / cities / stars / techs per seed, next to the same counts in the real later saves.
//!
//!   botplay <policy: data/bot_policy.json | v1 | random> <start save> <player to move> <rounds> <seeds> [temperature] -- <later saves...>
//!
//! One JSON line per seed ({"seed", "rounds": [{tribe: stats} after each round]}), then {"real": [...]}.
//! Used by tools/bot_policy.py play (distribution check).
use polyfish::botpolicy::{play_turn, Policy, Rng, Weights};
use polyfish::{api, Game};
use serde_json::{json, Value};

fn stats(g: &Game) -> Value {
    let mut m = serde_json::Map::new();
    for (id, t) in &g.state.tribes {
        m.insert(id.to_string(), json!({
            "units": t.units.len(), "cities": t.cities.len(), "stars": t.stars,
            "techs": t.tech_vanilla.iter().filter(|x| x.discovered).count(), "bot": t.bot, "kills": t.kills, "casualties": t.casualties,
        }));
    }
    Value::Object(m)
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    if a.len() < 6 { eprintln!("usage: botplay <policy> <save> <player> <rounds> <seeds> [temperature] -- <later saves>"); std::process::exit(2); }
    let pol = match a[1].as_str() {
        "v1" => Policy::V1,
        "random" => Policy::Random,
        p => Policy::V2(Weights::from_file(p).expect("policy file")),
    };
    let player: i32 = a[3].parse().unwrap();
    let rounds: i32 = a[4].parse().unwrap();
    let seeds: u64 = a[5].parse().unwrap();
    let temp: f64 = a.get(6).filter(|x| *x != "--").and_then(|x| x.parse().ok())
        .unwrap_or(match &pol { Policy::V2(w) => w.temperature, _ => 0.0 });
    let later: Vec<&String> = a.iter().skip_while(|x| *x != "--").skip(1).collect();
    let g0 = api::load_save_file(&a[2], "current", player).expect("load save");
    let t0 = g0.state.settings.turn;
    for seed in 0..seeds {
        let mut g = api::clone(&g0);
        let mut rng = Rng(0x9E3779B97F4A7C15 ^ (seed + 1).wrapping_mul(0x2545F4914F6CDD1D));
        let mut per_round = Vec::new();
        let mut moves = 0usize;
        let mut guard = 0;
        while per_round.len() < rounds as usize && !g.state.settings._game_over && guard < 10000 {
            guard += 1;
            moves += play_turn(&mut g, &pol, temp, &mut rng, 300).len();
            // a round ends when play comes back to the starting player
            if g.state.settings.current_player_turn_id == player { per_round.push(stats(&g)); }
        }
        println!("{}", json!({"seed": seed, "t0": t0, "moves": moves, "rounds": per_round}));
    }
    let real: Vec<Value> = later.iter().map(|p| api::load_save_file(p, "current", player).map(|g| stats(&g)).unwrap_or(Value::Null)).collect();
    println!("{}", json!({"real": real, "start": stats(&g0)}));
}
