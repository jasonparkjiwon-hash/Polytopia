//! Forward-model API for search (fm-accept): load a save, list legal moves with a readable label, apply, undo,
//! end a turn, clone, fingerprint a state, and sample the random parts from data/distributions.json.
//! Adds no rules: every call goes through `Game::legal_moves` / `Game::play_move`. See sim/README.md "Forward-model API".
use crate::actions::UndoCallback;
use crate::game::Game;
use crate::moves::*;
use crate::save_loader;
use crate::states::GameState;
use crate::types::*;
use serde_json::Value;
use std::hash::{Hash, Hasher};

/// One legal move: its key (Polyfish's serialized move, stable across clones), a readable label, and the move.
pub struct LegalMove {
    pub key: Value,
    pub label: String,
    pub mv: Box<dyn Move>,
}

/// Load a decoded save (`saves/<id>_t<n>.json`) as a Game, `player` to move. `which` is "current" (the
/// state at the end of the save) or "initial".
pub fn load_save(save: &Value, which: &str, player: i32) -> Result<Game, String> {
    save_loader::load(save, which, player).map(|(g, _)| g)
}

pub fn load_save_file(path: &str, which: &str, player: i32) -> Result<Game, String> {
    let txt = std::fs::read_to_string(path).map_err(|e| format!("{path}: {e}"))?;
    let v: Value = serde_json::from_str(&txt).map_err(|e| format!("{path}: {e}"))?;
    load_save(&v, which, player)
}

fn xy(state: &GameState, idx: i64) -> String {
    let n = state.settings.size as i64;
    format!("({},{})", idx % n, idx / n)
}

/// "Step Warrior (3,4)->(4,5)", "Build Farm (3,4)", "Research Fishing", "EndTurn": verb from the move struct,
/// the acting unit, the named type, tiles as (x,y).
pub fn label(state: &GameState, mv: &dyn Move) -> String {
    let dbg = format!("{mv:?}");
    let verb = dbg.split(|c: char| !c.is_alphanumeric()).next().unwrap_or("").trim_end_matches("Move").to_string();
    let k = mv.serialize();
    let mut s = verb.clone();
    let src = k.get("src").and_then(|v| v.as_i64());
    let tgt = k.get("target").and_then(|v| v.as_i64());
    if let Some(u) = src.and_then(|i| crate::functions::get_unit_at(state, i as i32)) {
        s += &format!(" {:?}", u.unit_type);
    }
    let named = mv.structure_type().map(|t| format!("{t:?}"))
        .or_else(|_| mv.tech_type().map(|t| format!("{t:?}")))
        .or_else(|_| mv.unit_type().map(|t| format!("{t:?}")))
        .or_else(|_| mv.ability_type().map(|t| format!("{t:?}")))
        .or_else(|_| mv.reward_type().map(|t| format!("{t:?}")));
    if let Ok(n) = named { if n != verb { s += &format!(" {n}"); } }
    match (src, tgt) {
        (Some(a), Some(b)) => s += &format!(" {}->{}", xy(state, a), xy(state, b)),
        (Some(a), None) | (None, Some(a)) => s += &format!(" {}", xy(state, a)),
        _ => {}
    }
    s
}

/// The rule family a move belongs to, the key of data/pf_rule_levels.json "kinds": the move type, an ability's
/// name ("Explode", "BreakIce", ...), or "Upgrade" for a Summon on a unit.
pub fn kind(mv: &dyn Move) -> String {
    match mv.move_type() {
        MoveType::Ability => mv.ability_type().map(|a| format!("{a:?}")).unwrap_or_else(|_| {
            format!("{mv:?}").split(|c: char| !c.is_alphanumeric()).next().unwrap_or("").trim_end_matches("Move").to_string()
        }),
        MoveType::Summon if format!("{mv:?}").starts_with("Upgrade") => "Upgrade".into(),
        t => format!("{t:?}"),
    }
}

/// Every legal move for the player to move, labelled.
pub fn legal(g: &Game) -> Vec<LegalMove> {
    g.legal_moves().into_iter().map(|mv| LegalMove { key: mv.serialize(), label: label(&g.state, mv.as_ref()), mv }).collect()
}

/// The legal move with this key (from `legal`), if it is legal now.
pub fn find(g: &Game, key: &Value) -> Option<Box<dyn Move>> {
    g.legal_moves().into_iter().find(|m| &m.serialize() == key)
}

/// Apply a move; returns the undo (None if Polyfish refused it or the game is over).
pub fn apply(g: &mut Game, mv: &dyn Move) -> Option<UndoCallback> {
    g.play_move(mv)
}

/// Apply a move for search (`Game::search_move`): like `apply` but no tile reveals, no fog memory, no history
/// entry, and `EndTurn` passes control to the next player. The undo is exact.
pub fn apply_search(g: &mut Game, mv: &dyn Move) -> Option<UndoCallback> {
    g.search_move(mv)
}

/// Undo a move applied with `apply` (undos must be run newest first).
pub fn undo(g: &mut Game, u: UndoCallback) {
    u(&mut g.state);
}

/// End the current player's turn (next player starts: income, healing, spawns).
pub fn end_turn(g: &mut Game) -> Option<UndoCallback> {
    let m = g.legal_moves().into_iter().find(|m| m.move_type() == MoveType::EndTurn)?;
    g.play_move(m.as_ref())
}

/// Independent copy (direct struct clone, ~no cost beyond the allocation).
pub fn clone(g: &Game) -> Game {
    g.clone()
}

/// Hash of the whole state as Polyfish serializes it (units, HP, stars, tiles, cities, techs, fog, settings,
/// history), minus the verbose message log. Two states with the same fingerprint are the same game.
pub fn fingerprint(state: &GameState) -> u64 {
    fingerprint_with(state, false)
}

/// `fingerprint`, optionally ignoring which tribes have explored each tile: `Game::play_move` reveals tiles for
/// good (its undo keeps them revealed), so an undo is exact only up to exploration.
pub fn fingerprint_with(state: &GameState, ignore_explored: bool) -> u64 {
    let mut v = serde_json::to_value(state).unwrap_or(Value::Null);
    if let Some(o) = v.as_object_mut() { o.remove("_messages"); }
    if ignore_explored {
        if let Some(t) = v.get_mut("tiles").and_then(|t| t.as_object_mut()) {
            for tile in t.values_mut() { if let Some(o) = tile.as_object_mut() { o.remove("explorers"); } }
        }
    }
    let mut h = std::collections::hash_map::DefaultHasher::new();
    v.to_string().hash(&mut h);
    h.finish()
}

/// Top-level parts of two states that differ (for a fingerprint mismatch report).
pub fn diff_parts(a: &GameState, b: &GameState) -> Vec<String> {
    let (va, vb) = (serde_json::to_value(a).unwrap_or(Value::Null), serde_json::to_value(b).unwrap_or(Value::Null));
    let mut out = Vec::new();
    if let (Some(oa), Some(ob)) = (va.as_object(), vb.as_object()) {
        for (k, x) in oa {
            if k == "_messages" { continue; }
            if ob.get(k) != Some(x) {
                if let (Some(xa), Some(xb)) = (x.as_object(), ob.get(k).and_then(|y| y.as_object())) {
                    for (k2, y) in xa {
                        let z = xb.get(k2);
                        if z == Some(y) { continue; }
                        match (y.as_object(), z.and_then(|z| z.as_object())) {
                            (Some(ya), Some(za)) => for (k3, w) in ya { if za.get(k3) != Some(w) { out.push(format!("{k}.{k2}.{k3}")); } },
                            _ => out.push(format!("{k}.{k2}")),
                        }
                    }
                } else { out.push(k.clone()); }
            }
        }
    }
    out.truncate(6);
    out
}

/// The random events Polyfish rolls, and whether `Dice` can sample them from data/distributions.json.
/// (event, where in Polyfish, covered by)
pub const RANDOM_EVENTS: &[(&str, &str, &str)] = &[
    ("ruin reward type", "actions/structure.rs examine_ruins (xxhash on settings.seed, uniform over eligible)", "Dice: ruin_reward resolved_land / resolved_water (DIST-RUIN-REWARD)"),
    ("ruin free tech pick", "actions/structure.rs (xxhash, uniform over researchable)", "none: uniform kept (distributions.json has no per-tech counts)"),
    ("ruin explorer path", "actions/discovery.rs (xxhash on seed and tile)", "none: path not measured"),
    ("Sanctuary animal spawn tile", "actions/mod.rs (DotNetRandom on seed, turn, tile)", "own-territory forest next to it, westmost, every 2 turns (SANCTUARY-SPAWN)"),
    ("city level-up reward (bot choice)", "choice in the move list, not dice", "data/distributions.json city_reward_choice (bot model, Phase 6)"),
    ("combat damage", "deterministic formula, no dice", "-"),
];

/// Samples the random events from the measured distributions instead of Polyfish's seeded hash.
pub struct Dice {
    land: Vec<(RuinsRewardType, f64)>,
    water: Vec<(RuinsRewardType, f64)>,
    rng: u64,
    pub sampled: u64,
}

fn ruin_kind(name: &str) -> Option<RuinsRewardType> {
    Some(match name {
        "stars" => RuinsRewardType::Resources,
        "pop" => RuinsRewardType::PopGrowth,
        "explorer" => RuinsRewardType::Explorer,
        "tech" => RuinsRewardType::FreeTech,
        "unit" => RuinsRewardType::Swordsman,
        _ => return None,
    })
}

impl Dice {
    /// From the parsed data/distributions.json; `seed` makes a run reproducible.
    pub fn new(dist: &Value, seed: u64) -> Result<Self, String> {
        let rr = dist.get("ruin_reward").ok_or("distributions.json has no ruin_reward")?;
        let read = |k: &str| -> Result<Vec<(RuinsRewardType, f64)>, String> {
            let o = rr.get(k).and_then(|x| x.get("outcomes")).and_then(|x| x.as_object()).ok_or(format!("no ruin_reward.{k}"))?;
            Ok(o.iter().filter_map(|(n, v)| Some((ruin_kind(n)?, v.get("count")?.as_f64()?))).collect())
        };
        Ok(Dice { land: read("resolved_land")?, water: read("resolved_water")?, rng: seed | 1, sampled: 0 })
    }

    pub fn from_file(path: &str, seed: u64) -> Result<Self, String> {
        let v: Value = serde_json::from_str(&std::fs::read_to_string(path).map_err(|e| format!("{path}: {e}"))?).map_err(|e| e.to_string())?;
        Self::new(&v, seed)
    }

    fn uniform(&mut self) -> f64 {
        self.rng ^= self.rng << 13; self.rng ^= self.rng >> 7; self.rng ^= self.rng << 17;
        (self.rng >> 11) as f64 / (1u64 << 53) as f64
    }

    /// Weights for a ruin on this tile: the water or land table, with FreeTech dropped when nothing is researchable.
    pub fn ruin_weights(&self, state: &GameState, tile: i32) -> Vec<(RuinsRewardType, f64)> {
        let water = state.tiles.get(&tile).is_some_and(|t| t.is_water_terrain());
        let me = state.settings.current_player_turn_id;
        let can_tech = state.tribes.get(&me).is_some_and(|tr| !crate::settings::technology::get_researchable_techs(&tr.tech_vanilla, tr.tribe_type).is_empty());
        let t = if water { &self.water } else { &self.land };
        t.iter().filter(|(k, w)| *w > 0.0 && (can_tech || *k != RuinsRewardType::FreeTech)).cloned().collect()
    }

    pub fn sample_ruin(&mut self, state: &GameState, tile: i32) -> RuinsRewardType {
        let w = self.ruin_weights(state, tile);
        let total: f64 = w.iter().map(|x| x.1).sum();
        let mut r = self.uniform() * total;
        self.sampled += 1;
        for (k, x) in &w { if r < *x { return *k; } r -= x; }
        w.last().map_or(RuinsRewardType::Resources, |x| x.0)
    }

    /// The move to play for `mv`: an Examine Ruins gets a reward sampled from the distributions; anything else as is.
    pub fn roll(&mut self, state: &GameState, mv: &dyn Move) -> Option<Box<dyn Move>> {
        if mv.move_type() != MoveType::Capture { return None; }
        let src = mv.source_idx().ok()? as i32;
        let is_ruin = crate::functions::get_structure_at(state, src).is_some_and(|s| s.structure_type == StructureType::Ruin);
        if !is_ruin { return None; }
        Some(Box::new(CaptureMove::with_reward(src, self.sample_ruin(state, src))))
    }
}

/// Play `mv`, rolling its dice from `dice` when given (else Polyfish's own seeded hash).
pub fn apply_with_dice(g: &mut Game, mv: &dyn Move, dice: Option<&mut Dice>) -> Option<UndoCallback> {
    if let Some(d) = dice {
        if let Some(m) = d.roll(&g.state, mv) { return g.play_move(m.as_ref()); }
    }
    g.play_move(mv)
}
