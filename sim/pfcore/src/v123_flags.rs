//! Switches for v123 rules below L1 (one source, or a split in the ledger): all off by default.
//! Rules at L1 or above are plain code. `set_from("a,b")` turns switches on by name (pfreplay reads
//! the environment variable PF_FLAGS), so a below-L1 rule can be A/B tested against the saves.
use std::sync::atomic::{AtomicBool, Ordering};

/// Amphibious units onto ocean with no tech (AMPHIBIOUS-WATER ocean part: Jason 26 Oct 2026, one source). Off,
/// Marine Life (46) opens it, which every logged Aquarion ocean move had.
pub static AMPHIBIOUS_OCEAN_INNATE: AtomicBool = AtomicBool::new(false);

/// Sanctuary pays +1 a turn per adjacent wild animal in own territory (the v123 card, Jason 26 Oct, and upstream).
/// Off: no Sanctuary income, as the save measures (SANCTUARY-NO-INCOME L3, b2448ead t5->6) and the referee models.
pub static SANCTUARY_CARD_INCOME: AtomicBool = AtomicBool::new(false);

pub const ALL: &[(&str, &AtomicBool)] = &[
    ("sanctuary_card_income", &SANCTUARY_CARD_INCOME),
    ("amphibious_ocean_innate", &AMPHIBIOUS_OCEAN_INNATE),
];

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
