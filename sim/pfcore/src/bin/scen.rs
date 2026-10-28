//! Scenario engine entry point: `scen <save.json> <job.json>` prints one JSON object (docs: src/scenario.rs, tools/scenario.py).
fn main() {
    let a: Vec<String> = std::env::args().collect();
    if a.len() < 3 { eprintln!("usage: scen <save.json> <job.json>"); std::process::exit(2) }
    let rd = |p: &str| -> serde_json::Value { serde_json::from_str(&std::fs::read_to_string(p).unwrap_or_else(|e| { eprintln!("{p}: {e}"); std::process::exit(2) })).unwrap_or_else(|e| { eprintln!("{p}: {e}"); std::process::exit(2) }) };
    match polyfish::scenario::run(&rd(&a[1]), &rd(&a[2])) {
        Ok(v) => println!("{v}"),
        Err(e) => { eprintln!("{e}"); std::process::exit(1) }
    }
}
