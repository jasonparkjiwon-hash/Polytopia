//! Fog inference tools (fog-inference session; library code in src/fog.rs and src/belief.rs, notes in
//! .scratchpad/investigations/fog-inference.md).
//! usage:
//!   pffog info <save.json>                       header, size, players, tribes, explored counts per player
//!   pffog view <save.json> [pov|0]               player-view check: obscure_fog vs the fog rule vs the save's PlayerVisibility
//!   pffog explore <save.json> [pov|0]            the engine's vision rule (update_exploration) vs the save's explored set
use polyfish::api;
use polyfish::fog;
use serde_json::Value;

fn load_json(path: &str) -> Value {
    let txt = std::fs::read_to_string(path).unwrap_or_else(|e| { eprintln!("{path}: {e}"); std::process::exit(2) });
    serde_json::from_str(&txt).unwrap_or_else(|e| { eprintln!("{path}: {e}"); std::process::exit(2) })
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let cmd = a.get(1).map(String::as_str).unwrap_or("");
    match cmd {
        "info" => {
            let v = load_json(&a[2]);
            let hdr = v.pointer("/header/MapHeaderInput").cloned().unwrap_or(Value::Null);
            println!("header {}", hdr);
            let g = fog::load_exact(&v, "current", 1).unwrap();
            println!("size {} turn {} players {}", g.state.settings.size, g.state.settings.turn, g.state.tribes.len());
            for (id, t) in &g.state.tribes {
                let ex = g.state.tiles.values().filter(|x| x.explorers.contains(id)).count();
                println!("p{id} {:?} bot={} cities={} units={} explored={ex} met={:?}", t.tribe_type, t.bot, t.cities.len(), t.units.len(), t.known_players);
            }
        }
        "view" | "explore" => {
            let v = load_json(&a[2]);
            let g = fog::load_exact(&v, "current", 1).unwrap();
            let pov: i32 = a.get(3).and_then(|s| s.parse().ok()).unwrap_or(0);
            let povs: Vec<i32> = if pov == 0 { g.state.tribes.keys().copied().collect() } else { vec![pov] };
            for p in povs {
                if cmd == "view" {
                    println!("raw   {}", fog::check_view(&v, &g, p, false));
                    println!("scrub {}", fog::check_view(&v, &g, p, true));
                } else {
                    println!("{}", fog::check_vision_rule(&g, p));
                }
            }
        }
        "jsondiff" => {
            let v = load_json(&a[2]);
            let g = fog::load_exact(&v, "current", 1).unwrap();
            let p: i32 = a[3].parse().unwrap();
            let (j, e) = (fog::saved_explored(&v, p), fog::explored(&g, p));
            let n = g.state.settings.size;
            let f = |s: &std::collections::HashSet<i32>, o: &std::collections::HashSet<i32>| { let mut d: Vec<_> = s.difference(o).map(|i| (i % n, i / n)).collect(); d.sort(); d };
            let g = api::load_save(&v, "current", 1).unwrap();
            let (j, e) = (fog::saved_explored(&v, p), fog::explored(&g, p));
            println!("in save only {:?}; in loaded only {:?}", f(&j, &e), f(&e, &j));
        }
        "sweep" => {
            // every save given, every player: view agreement and vision-rule agreement, totals plus any disagreeing lines
            let (mut n, mut bad, mut known, mut tiles, mut uvis, mut ulost, mut uleak, mut cvis, mut clost, mut cleak) = (0, 0, 0, 0, 0, 0, 0, 0, 0, 0);
            let (mut rn, mut radd, mut rbad, mut rtiles) = (0, 0, 0, 0);
            let mut raw_leaks = 0;
            for path in &a[2..] {
                let v = load_json(path);
                let Ok(g) = fog::load_exact(&v, "current", 1) else { continue };
                for p in g.state.tribes.keys().copied() {
                    let r = fog::check_view(&v, &g, p, true);
                    n += 1;
                    known += r.known; tiles += r.tiles;
                    uvis += r.enemy_units_visible; ulost += r.enemy_units_lost; uleak += r.enemy_units_leaked;
                    cvis += r.enemy_cities_visible; clost += r.enemy_cities_lost; cleak += r.enemy_cities_leaked;
                    if !r.ok() { bad += 1; if bad <= 8 { println!("{path} {r}"); } }
                    if fog::check_view(&v, &g, p, false).leaks.values().sum::<usize>() > 0 { raw_leaks += 1; }
                    let (b, add) = fog::vision_rule_adds(&g, p);
                    rn += 1; rtiles += b; radd += add.len();
                    if !add.is_empty() { rbad += 1; if rbad <= 8 { println!("{path} {}", fog::check_vision_rule(&g, p)); } }
                }
            }
            println!("VIEW   povs {n} (save,player) tiles known {known}/{tiles}: enemy units visible {uvis} lost {ulost} leaked {uleak}; enemy cities visible {cvis} lost {clost} leaked {cleak}; povs with a diff {bad}; povs where raw obscure_fog leaves hidden-tile info {raw_leaks}");
            println!("VISION povs {rn}: saved explored tiles {rtiles}, engine rule would add {radd} tiles in {rbad} povs");
        }
        _ => eprintln!("usage: pffog info|view|explore <save.json> [pov]"),
    }
}
