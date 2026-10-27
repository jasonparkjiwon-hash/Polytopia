//! What-if advisor entry point: `whatif <save.json> [--player N] [--truth] [--no-lookahead] [--dist data/distributions.json]`
//! prints one JSON object {situation, moves, threats_now}; tools/whatif.py renders it as text (docs: sim/README.md "What-if").
use polyfish::whatif::{analyze, Opts};

fn main() {
    let a: Vec<String> = std::env::args().collect();
    if let Ok(f) = std::env::var("PF_FLAGS") {
        for n in polyfish::v123_flags::set_from(&f) { eprintln!("PF_FLAGS: unknown switch {n}"); }
    }
    let Some(path) = a.get(1) else { eprintln!("usage: whatif <save.json> [--player N] [--truth] [--no-lookahead] [--dist file]"); std::process::exit(2) };
    let mut o = Opts { player: None, truth: false, lookahead: true, dist: None };
    let mut i = 2;
    while i < a.len() {
        match a[i].as_str() {
            "--player" => { i += 1; o.player = a.get(i).and_then(|s| s.parse().ok()); }
            "--truth" => o.truth = true,
            "--no-lookahead" => o.lookahead = false,
            "--dist" => { i += 1; o.dist = a.get(i).cloned(); }
            x => { eprintln!("unknown option {x}"); std::process::exit(2) }
        }
        i += 1;
    }
    let txt = std::fs::read_to_string(path).unwrap_or_else(|e| { eprintln!("{path}: {e}"); std::process::exit(2) });
    let save: serde_json::Value = serde_json::from_str(&txt).unwrap_or_else(|e| { eprintln!("{path}: {e}"); std::process::exit(2) });
    match analyze(&save, &o) {
        Ok(v) => println!("{v}"),
        Err(e) => { eprintln!("{e}"); std::process::exit(1) }
    }
}
