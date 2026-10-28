//! Fog inference tools (fog-inference session; library code in src/fog.rs and src/belief.rs, notes in
//! .scratchpad/investigations/fog-inference.md).
//! usage:
//!   pffog info <save.json>                       header, size, players, tribes, explored counts per player
//!   pffog view <save.json> [pov|0]               player-view check: obscure_fog vs the fog rule vs the save's PlayerVisibility
//!   pffog explore <save.json> [pov|0]            the engine's vision rule (update_exploration) vs the save's explored set
use polyfish::api;
use polyfish::belief::{self, MapView, Mode, Model};
use polyfish::fog;
use serde_json::Value;

fn load_json(path: &str) -> Value {
    let txt = std::fs::read_to_string(path).unwrap_or_else(|e| { eprintln!("{path}: {e}"); std::process::exit(2) });
    serde_json::from_str(&txt).unwrap_or_else(|e| { eprintln!("{path}: {e}"); std::process::exit(2) })
}


fn game_id(path: &str) -> String {
    path.rsplit('/').next().unwrap_or(path).chars().take(8).collect()
}
fn turn_of(path: &str) -> i32 {
    path.rsplit("_t").next().and_then(|s| s.trim_end_matches(".json").parse().ok()).unwrap_or(-1)
}

#[derive(Default)]
struct Acc {
    pairs: usize,
    tiles: usize,
    ll: [f64; 5],        // terrain, resource, village, ruin (sum of ln p of the truth)
    acc: usize,          // terrain mode correct
    viol: usize,         // observed tiles changed by the sampler
    vil: Vec<(f64, f64, f64, f64)>, // truth, mean, p5, p95 hidden free-village counts
    ruin: Vec<(f64, f64, f64, f64)>,
    own: Vec<(f64, f64, f64, f64)>, // hidden owned tiles (borders of capitals and sampled cities)
    caps: usize,
    cap_k: [f64; 3],     // fraction of samples with a sampled hidden capital within 2, 4, 6 of a true hidden capital
    cap_d: f64,
    calib: Vec<(f64, bool)>, // village probability vs truth
    by_dist: [(f64, usize); 3], // terrain ln p by distance to the explored region: 1-2, 3-5, 6+
}

fn score_pair(truth: &MapView, pov: i32, samples: &[MapView], a: &mut Acc) {
    let obs = &truth.explored[&pov];
    let nn = obs.len();
    let ns = samples.len() as f64;
    let al = 0.5;
    a.pairs += 1;
    for i in 0..nn {
        if obs[i] {
            for s in samples { if s.cls[i] != truth.cls[i] || s.res[i] != truth.res[i] { a.viol += 1; } }
            continue;
        }
        a.tiles += 1;
        let cnt = |f: &dyn Fn(&MapView) -> bool| samples.iter().filter(|s| f(s)).count() as f64;
        let mut cc = [0.0; belief::NC];
        for s in samples { cc[s.cls[i] as usize] += 1.0; }
        let lp = ((cc[truth.cls[i] as usize] + al) / (ns + al * belief::NC as f64)).ln();
        a.ll[0] += lp;
        let n0 = truth.n;
        let dmin = (0..nn).filter(|&j| obs[j]).map(|j| (((i as i32 % n0) - (j as i32 % n0)).abs()).max(((i as i32 / n0) - (j as i32 / n0)).abs())).min().unwrap_or(9);
        let b = if dmin <= 2 { 0 } else if dmin <= 5 { 1 } else { 2 };
        a.by_dist[b].0 += lp; a.by_dist[b].1 += 1;
        let best = (0..belief::NC).max_by(|&x, &y| cc[x].partial_cmp(&cc[y]).unwrap()).unwrap();
        if best == truth.cls[i] as usize { a.acc += 1; }
        let rt = truth.res[i];
        a.ll[1] += ((cnt(&|s| s.res[i] == rt) + al) / (ns + al * belief::NR as f64)).ln();
        let pv = (cnt(&|s| s.village[i]) + al) / (ns + 2.0 * al);
        a.ll[2] += if truth.village[i] { pv.ln() } else { (1.0 - pv).ln() };
        a.calib.push((pv, truth.village[i]));
        let pr = (cnt(&|s| s.ruin[i]) + al) / (ns + 2.0 * al);
        a.ll[3] += if truth.ruin[i] { pr.ln() } else { (1.0 - pr).ln() };
        let po = (cnt(&|s| s.owned[i]) + al) / (ns + 2.0 * al);
        a.ll[4] += if truth.owned[i] { po.ln() } else { (1.0 - po).ln() };
    }
    let count = |m: &MapView, f: &dyn Fn(&MapView, usize) -> bool| (0..nn).filter(|&i| !obs[i] && f(m, i)).count() as f64;
    for (which, out) in [(0, &mut a.vil), (1, &mut a.ruin), (2, &mut a.own)] {
        let f = |m: &MapView, i: usize| match which { 0 => m.village[i], 1 => m.ruin[i], _ => m.owned[i] };
        let mut c: Vec<f64> = samples.iter().map(|s| count(s, &f)).collect();
        c.sort_by(|x, y| x.partial_cmp(y).unwrap());
        let q = |p: f64| c[((p * (c.len() - 1) as f64).round() as usize).min(c.len() - 1)];
        out.push((count(truth, &f), c.iter().sum::<f64>() / ns, q(0.05), q(0.95)));
    }
    let n = truth.n;
    let tcaps: Vec<usize> = (0..nn).filter(|&i| !obs[i] && truth.cap[i] > 0 && truth.cap[i] != pov).collect();
    for &t in &tcaps {
        a.caps += 1;
        for s in samples {
            let d = (0..nn).filter(|&i| !obs[i] && s.cap[i] > 0).map(|i| (((i as i32 % n) - (t as i32 % n)).abs()).max(((i as i32 / n) - (t as i32 / n)).abs())).min().unwrap_or(99) as f64;
            for (k, lim) in [2.0, 4.0, 6.0].iter().enumerate() { if d <= *lim { a.cap_k[k] += 1.0 / ns; } }
            a.cap_d += d / ns;
        }
    }
}

fn report(name: &str, a: &Acc) {
    let t = a.tiles.max(1) as f64;
    let cov = |v: &Vec<(f64, f64, f64, f64)>| v.iter().filter(|x| x.0 >= x.2 && x.0 <= x.3).count() as f64 / v.len().max(1) as f64;
    let mae = |v: &Vec<(f64, f64, f64, f64)>| v.iter().map(|x| (x.0 - x.1).abs()).sum::<f64>() / v.len().max(1) as f64;
    let bias = |v: &Vec<(f64, f64, f64, f64)>| v.iter().map(|x| x.1 - x.0).sum::<f64>() / v.len().max(1) as f64;
    let c = a.caps.max(1) as f64;
    println!("{name:10} terrain ln p by distance to explored region 1-2/3-5/6+: {:.3} ({}) / {:.3} ({}) / {:.3} ({})", a.by_dist[0].0 / a.by_dist[0].1.max(1) as f64, a.by_dist[0].1, a.by_dist[1].0 / a.by_dist[1].1.max(1) as f64, a.by_dist[1].1, a.by_dist[2].0 / a.by_dist[2].1.max(1) as f64, a.by_dist[2].1);
    println!("{name:10} pairs {} hidden tiles {} | mean ln p(truth): terrain {:.3} (acc {:.3}) resource {:.3} village {:.4} ruin {:.4} | free villages hidden: MAE {:.1} bias {:+.1} 90%-interval covers {:.2} | ruins: MAE {:.1} bias {:+.1} covers {:.2} | owned ln p {:.4}, hidden owned tiles MAE {:.1} bias {:+.1} covers {:.2} | hidden capitals {}: within 2/4/6 tiles {:.2}/{:.2}/{:.2}, mean dist {:.1} | observed-fact violations {}",
        a.pairs, a.tiles, a.ll[0] / t, a.acc as f64 / t, a.ll[1] / t, a.ll[2] / t, a.ll[3] / t, mae(&a.vil), bias(&a.vil), cov(&a.vil), mae(&a.ruin), bias(&a.ruin), cov(&a.ruin), a.ll[4] / t, mae(&a.own), bias(&a.own), cov(&a.own), a.caps, a.cap_k[0] / c, a.cap_k[1] / c, a.cap_k[2] / c, a.cap_d / c, a.viol);
}

fn main2(a: &[String]) -> bool {
    match a.get(1).map(String::as_str).unwrap_or("") {
        "train" => {
            // pffog train <out.json> <saves...>: fit on all given saves
            let maps: Vec<MapView> = a[3..].iter().filter_map(|p| fog::load_exact(&load_json(p), "current", 1).ok()).map(|g| MapView::from_game(&g)).collect();
            let m = belief::train(&maps, 1);
            std::fs::write(&a[2], serde_json::to_string(&m).unwrap()).unwrap();
            println!("{}", m.notes);
            true
        }
        "eval" => {
            // pffog eval <n> <seed> <game:turn,game:turn,...> <saves...>: train without the test games, score the test saves
            let (n, seed): (usize, u64) = (a[2].parse().unwrap(), a[3].parse().unwrap());
            let tests: Vec<(String, i32)> = a[4].split(',').map(|x| { let (g, t) = x.split_once(':').unwrap(); (g.to_string(), t.parse().unwrap()) }).collect();
            let test_ids: Vec<&String> = tests.iter().map(|t| &t.0).collect();
            let train_maps: Vec<MapView> = a[5..].iter().filter(|p| !test_ids.contains(&&game_id(p))).filter_map(|p| fog::load_exact(&load_json(p), "current", 1).ok()).map(|g| MapView::from_game(&g)).collect();
            let mut model = belief::train(&train_maps, 1);
            if let Ok(t) = std::env::var("TAU") { model.tau = t.parse().unwrap(); }
            println!("tau {}", model.tau);
            println!("trained without {:?}: {}", test_ids, model.notes);
            let mut accs = [Acc::default(), Acc::default(), Acc::default()];
            for p in a[5..].iter().filter(|p| tests.iter().any(|(g, t)| game_id(p) == *g && turn_of(p) == *t)) {
                let g = fog::load_exact(&load_json(p), "current", 1).unwrap();
                let truth = MapView::from_game(&g);
                {
                    let (mut x, mut y, mut c) = (0.0, 0.0, 0usize);
                    for pov in g.state.tribes.keys().copied() { let (a, b, k) = belief::diag(&model, &truth, pov); x += a; y += b; c += k; }
                    println!("model one-tile ln p(truth) given true neighbours {:.3}, without neighbour features {:.3} ({} tiles)", x / c as f64, y / c as f64, c);
                }
                for pov in g.state.tribes.keys().copied() {
                    for (mi, mode) in [Mode::Full, Mode::GlobalFreq, Mode::Uniform].iter().enumerate() {
                        let samples: Vec<MapView> = (0..n).map(|k| MapView::from_game(&belief::sample_belief(&g, pov, &model, *mode, seed * 1000 + k as u64 + pov as u64 * 7919))).collect();
                        score_pair(&truth, pov, &samples, &mut accs[mi]);
                    }
                }
            }
            for (name, acc) in ["sampler", "globalfreq", "uniform"].iter().zip(accs.iter()) { report(name, acc); }
            // calibration of the sampler's village probability
            let mut bins = vec![(0.0, 0.0, 0usize); 8];
            for (p, t) in &accs[0].calib { let b = ((p * 40.0) as usize).min(7); bins[b].0 += p; bins[b].1 += *t as u8 as f64; bins[b].2 += 1; }
            println!("village calibration (bin of predicted p, n, mean p, observed freq): {}", bins.iter().enumerate().filter(|b| b.1.2 > 0).map(|(i, b)| format!("[{:.3}-{:.3}) n={} p={:.3} f={:.3}", i as f64 / 40.0, (i + 1) as f64 / 40.0, b.2, b.0 / b.2 as f64, b.1 / b.2 as f64)).collect::<Vec<_>>().join("; "));
            true
        }
        "sample" => {
            // pffog sample <save> <pov> <n> <seed> <model.json> <outdir>: write n sampled states (Game JSON) and print one summary line each
            let g = fog::load_exact(&load_json(&a[2]), "current", 1).unwrap();
            let model: Model = serde_json::from_str(&std::fs::read_to_string(&a[6]).unwrap()).unwrap();
            let pov: i32 = a[3].parse().unwrap();
            for k in 0..a[4].parse::<usize>().unwrap() {
                let s = belief::sample_belief(&g, pov, &model, Mode::Full, a[5].parse::<u64>().unwrap() * 1000 + k as u64);
                let path = format!("{}/belief_{k}.json", a[7]);
                std::fs::write(&path, s.to_json().unwrap()).unwrap();
                let mv = MapView::from_game(&s);
                let obs = &mv.explored[&pov];
                let hid = |f: &dyn Fn(usize) -> bool| (0..obs.len()).filter(|&i| !obs[i] && f(i)).count();
                println!("{}", serde_json::json!({"sample": k, "path": path, "hidden_tiles": hid(&|_| true), "hidden_villages": hid(&|i| mv.village[i]), "hidden_ruins": hid(&|i| mv.ruin[i]), "hidden_capitals": (0..obs.len()).filter(|&i| !obs[i] && mv.cap[i] > 0).map(|i| [i as i32 % mv.n, i as i32 / mv.n]).collect::<Vec<_>>()}));
            }
            true
        }
        _ => false,
    }
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    if main2(&a) { return; }
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
        "maps" => {
            // one line per save: size, players, turn, terrain shares, settlements, capitals' nearest distance
            for path in &a[2..] {
                let v = load_json(path);
                let Ok(g) = api::load_save(&v, "current", 1) else { continue };
                let st = &g.state;
                let n = st.settings.size;
                let mut tc = std::collections::BTreeMap::new();
                for t in st.tiles.values() { *tc.entry(format!("{:?}", t.terrain_type)).or_insert(0) += 1; }
                let vil = st.structures.values().filter(|s| s.as_ref().map_or(false, |s| s.structure_type == polyfish::types::StructureType::Village)).count();
                let ruin = st.structures.values().filter(|s| s.as_ref().map_or(false, |s| s.structure_type == polyfish::types::StructureType::Ruin)).count();
                let caps: Vec<i32> = st.tiles.iter().filter(|(_, t)| t.capital_of > 0).map(|(i, _)| *i).collect();
                let cities: usize = st.tribes.values().map(|t| t.cities.len()).sum();
                let mut md = 99;
                for (k, &i) in caps.iter().enumerate() { for &j in &caps[k + 1..] { md = md.min(((i % n - j % n).abs()).max((i / n - j / n).abs())); } }
                let name = path.rsplit('/').next().unwrap_or(path);
                let cl: Vec<String> = caps.iter().map(|i| format!("{},{}", i % n, i / n)).collect();
                println!("CAPS {} {}", &path.rsplit('/').next().unwrap_or(path)[..8], cl.join(" "));
                println!("{} n{} t{} P{} {:?} vil {} ruin {} caps {} cities {} mincapdist {}", &name[..name.len().min(20)], n, st.settings.turn, st.tribes.len(), tc, vil, ruin, caps.len(), cities, md);
            }
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
