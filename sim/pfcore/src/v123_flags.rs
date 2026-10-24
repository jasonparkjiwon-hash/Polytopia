//! Switches for v123 rules below L1 (one source, or a split in the ledger): all off by default.
//! Rules at L1 or above are plain code. `set_from("a,b")` turns switches on by name (pfreplay reads
//! the environment variable PF_FLAGS), so a below-L1 rule can be A/B tested against the saves.
use std::sync::atomic::{AtomicBool, Ordering};

/// Aquarion tech slots (data/conflicts_and_gaps.md AQUARION-TECHS, inferred from prerequisites, one source
/// type): 47 replaces Fishing, 39 replaces Ramming, 46 Marine Life replaces Sailing (and opens ocean).
pub static AQUARION_TECH_SLOTS: AtomicBool = AtomicBool::new(false);

/// Clathrus income from adjacent Fungi (v123 card) instead of Algae (Polyfish); a split in ECON-MARKET-CLATHRUS,
/// untested by any save.
pub static CLATHRUS_FUNGI: AtomicBool = AtomicBool::new(false);

pub const ALL: &[(&str, &AtomicBool)] =
    &[("aquarion_tech_slots", &AQUARION_TECH_SLOTS), ("clathrus_fungi", &CLATHRUS_FUNGI)];

pub fn on(flag: &AtomicBool) -> bool {
    flag.load(Ordering::Relaxed)
}

/// Turn on the named switches (comma-separated); unknown names are returned.
pub fn set_from(list: &str) -> Vec<String> {
    let mut unknown = Vec::new();
    for name in list.split(',').map(str::trim).filter(|n| !n.is_empty()) {
        match ALL.iter().find(|(n, _)| *n == name) {
            Some((_, f)) => f.store(true, Ordering::Relaxed),
            None => unknown.push(name.to_string()),
        }
    }
    unknown
}
