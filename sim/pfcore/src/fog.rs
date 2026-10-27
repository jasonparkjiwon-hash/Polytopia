//! Player view checks (fog-inference, Phase 4 item 1): is `Game::clone_for_mcts(pov)` / `obscure_fog` exactly what
//! the fog rules say pov can see, and does the engine's vision rule (`update_exploration`) agree with the saves?
//! The fog rule (ledger FOG-STALE, L3): a tile once explored stays explored, and everything on an explored tile
//! is shown live; units and cities are hidden only under never-explored tiles. A save's `PlayerVisibility`
//! (the players who explored the tile) is therefore exactly what a player sees.
use crate::actions::update_exploration;
use crate::game::Game;
use crate::types::*;
use serde_json::Value;
use std::collections::{BTreeMap, HashSet};
use std::fmt;

/// Tiles `pov` has explored in the raw save (`currentTiles[y][x].PlayerVisibility`), by tile index.
pub fn saved_explored(save: &Value, pov: i32) -> HashSet<i32> {
    let mut out = HashSet::new();
    let rows = save.get("currentTiles").and_then(|v| v.as_array());
    let size = save.get("mapWidth").and_then(|v| v.as_i64()).unwrap_or(0) as i32;
    for (y, row) in rows.into_iter().flatten().enumerate() {
        for (x, tv) in row.as_array().into_iter().flatten().enumerate() {
            let seen = tv.get("PlayerVisibility").and_then(|v| v.as_array()).map_or(false, |a| a.iter().any(|e| e.as_i64() == Some(pov as i64)));
            if seen {
                out.insert(y as i32 * size + x as i32);
            }
        }
    }
    out
}

/// `api::load_save` but with every tribe's explored set exactly the save's `PlayerVisibility`. `Game::post_load` runs the
/// engine's vision rule on the loaded state and so adds tiles the save does not hold (see `check_vision_rule`).
pub fn load_exact(save: &Value, which: &str, player: i32) -> Result<Game, String> {
    let mut g = crate::api::load_save(save, which, player)?;
    let ids: Vec<i32> = g.state.tribes.keys().copied().collect();
    let sz = g.state.settings.size;
    for t in g.state.tiles.values_mut() {
        t.explorers.clear();
    }
    for (y, row) in save.get(format!("{which}Tiles")).and_then(|v| v.as_array()).into_iter().flatten().enumerate() {
        for (x, tv) in row.as_array().into_iter().flatten().enumerate() {
            if let Some(t) = g.state.tiles.get_mut(&(y as i32 * sz + x as i32)) {
                for e in tv.get("PlayerVisibility").and_then(|v| v.as_array()).into_iter().flatten() {
                    if let Some(k) = e.as_i64() { if ids.contains(&(k as i32)) { t.explorers.insert(k as i32); } }
                }
            }
        }
    }
    Ok(g)
}

/// Why the engine's vision rule reveals `idx` for `pov`: the cities and units whose range covers it.
pub fn sources_of(g: &Game, pov: i32, idx: i32) -> String {
    let sz = g.state.settings.size;
    let (x, y) = (idx % sz, idx / sz);
    let mut out = vec![];
    let Some(t) = g.state.tribes.get(&pov) else { return String::new() };
    for c in &t.cities {
        let cap = g.state.tiles.get(&c.idx).map_or(0, |t| t.capital_of) > 0;
        let r = if cap { 2 } else { c.border_size };
        if (c.idx % sz - x).abs() <= r && (c.idx / sz - y).abs() <= r {
            out.push(format!("city({},{}) border {} cap {}", c.idx % sz, c.idx / sz, c.border_size, cap));
        }
    }
    for u in &t.units {
        let mtn = g.state.tiles.get(&u.coords.idx).map_or(false, |t| t.terrain_type == TerrainType::Mountain);
        let r = if crate::functions::has_skill(u, SkillType::Scout) || mtn { 2 } else { 1 };
        if (u.coords.idx % sz - x).abs() <= r && (u.coords.idx / sz - y).abs() <= r {
            out.push(format!("{:?}({},{}) r{}", u.unit_type, u.coords.idx % sz, u.coords.idx / sz, r));
        }
    }
    out.join("; ")
}

/// Tiles `pov` has explored in the engine state (the fog rule: `explorers` contains pov).
pub fn explored(g: &Game, pov: i32) -> HashSet<i32> {
    g.state.tiles.iter().filter(|(_, t)| t.explorers.contains(&pov)).map(|(i, _)| *i).collect()
}

/// Result of `check_view`: counts only, `Display` is one line.
#[derive(Default, Debug)]
pub struct ViewCheck {
    pub pov: i32,
    pub tribe: String,
    pub tiles: usize,
    pub known: usize,
    /// save PlayerVisibility vs the loaded explorers (loader fidelity)
    pub json_vs_loaded: usize,
    /// hidden tiles that still carry information in the obscured state, by kind
    pub leaks: BTreeMap<&'static str, usize>,
    /// explored tiles whose content changed in the obscured state
    pub altered: usize,
    pub enemy_units_visible: usize,
    pub enemy_units_kept: usize,
    pub enemy_units_leaked: usize,
    pub enemy_units_lost: usize,
    pub enemy_cities_visible: usize,
    pub enemy_cities_leaked: usize,
    pub enemy_cities_lost: usize,
    pub own_units_lost: usize,
    pub own_cities_lost: usize,
}

impl ViewCheck {
    pub fn ok(&self) -> bool {
        self.json_vs_loaded == 0 && self.leaks.values().all(|&n| n == 0) && self.altered == 0 && self.enemy_units_leaked == 0
            && self.enemy_units_lost == 0 && self.enemy_cities_leaked == 0 && self.enemy_cities_lost == 0 && self.own_units_lost == 0 && self.own_cities_lost == 0
    }
}

impl fmt::Display for ViewCheck {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "p{} {} known {}/{} json_diff {} leaks {:?} altered {} enemy_units vis {} kept {} leaked {} lost {} enemy_cities vis {} leaked {} lost {} own_lost u{}/c{} {}",
            self.pov, self.tribe, self.known, self.tiles, self.json_vs_loaded, self.leaks, self.altered, self.enemy_units_visible, self.enemy_units_kept,
            self.enemy_units_leaked, self.enemy_units_lost, self.enemy_cities_visible, self.enemy_cities_leaked, self.enemy_cities_lost, self.own_units_lost,
            self.own_cities_lost, if self.ok() { "OK" } else { "DIFF" }
        )
    }
}

/// The game as `pov` sees it: `clone_for_mcts(pov)` plus a scrub of what `obscure_fog` leaves on hidden tiles
/// (`capital_of` and `ruling_city_coords` give away every capital's position and the territory shape of tribes
/// pov has not met). Own/explored tiles, units and cities are untouched. Other tribes' stars and techs stay in
/// (a belief sampler or the search must treat them as unknown, see fog-inference.md).
pub fn player_view(g: &Game, pov: i32) -> Game {
    let mut v = g.clone_for_mcts(pov);
    if v.state.settings._fow {
        for t in v.state.tiles.values_mut() {
            if !t.explorers.contains(&pov) {
                t.capital_of = 0;
                t.ruling_city_coords = None;
            }
        }
    }
    v
}

/// Compare `clone_for_mcts(pov)` (`scrub` false) or `player_view(pov)` (`scrub` true) with the fog rule on this game.
/// `save` is the raw decoded save the game came from.
pub fn check_view(save: &Value, g: &Game, pov: i32, scrub: bool) -> ViewCheck {
    let mut r = ViewCheck { pov, tiles: g.state.tiles.len(), ..Default::default() };
    r.tribe = g.state.tribes.get(&pov).map_or(String::new(), |t| format!("{:?}", t.tribe_type));
    let rule = explored(g, pov);
    r.known = rule.len();
    let json = saved_explored(save, pov);
    r.json_vs_loaded = json.symmetric_difference(&rule).count();

    let ob = if scrub { player_view(g, pov) } else { g.clone_for_mcts(pov) };
    let sz = g.state.settings.size;
    for (idx, t0) in g.state.tiles.iter() {
        let Some(t1) = ob.state.tiles.get(idx) else { continue };
        let res0 = g.state.resources.get(idx).and_then(|x| x.as_ref()).map(|x| x.resource_type);
        let res1 = ob.state.resources.get(idx).and_then(|x| x.as_ref()).map(|x| x.resource_type);
        let st0 = g.state.structures.get(idx).and_then(|x| x.as_ref()).map(|x| (x.structure_type, x.level));
        let st1 = ob.state.structures.get(idx).and_then(|x| x.as_ref()).map(|x| (x.structure_type, x.level));
        if rule.contains(idx) {
            let same = t0.terrain_type == t1.terrain_type && t0.owner == t1.owner && t0.has_road == t1.has_road && t0.has_route == t1.has_route
                && t0.effects == t1.effects && t0.capital_of == t1.capital_of && res0 == res1 && st0 == st1;
            if !same {
                r.altered += 1;
            }
        } else {
            let mut leak = |k: &'static str, b: bool| {
                if b {
                    *r.leaks.entry(k).or_default() += 1;
                }
            };
            leak("owner", t1.owner != 0);
            leak("road", t1.has_road || t1.has_route);
            leak("effects", !t1.effects.is_empty());
            leak("resource", res1.is_some());
            leak("structure", st1.is_some());
            leak("capital_of", t1.capital_of != 0);
            leak("ruling_city", t1.ruling_city_coords.is_some());
            let _ = sz;
        }
    }
    for (id, t0) in g.state.tribes.iter() {
        let t1 = ob.state.tribes.get(id);
        let u0: Vec<(UnitType, i32)> = t0.units.iter().map(|u| (u.unit_type, u.coords.idx)).collect();
        let u1: Vec<(UnitType, i32)> = t1.map_or(vec![], |t| t.units.iter().map(|u| (u.unit_type, u.coords.idx)).collect());
        let c0: Vec<i32> = t0.cities.iter().map(|c| c.idx).collect();
        let c1: Vec<i32> = t1.map_or(vec![], |t| t.cities.iter().map(|c| c.idx).collect());
        if *id == pov {
            r.own_units_lost += u0.iter().filter(|u| !u1.contains(u)).count();
            r.own_cities_lost += c0.iter().filter(|c| !c1.contains(c)).count();
            continue;
        }
        let vis_u: Vec<_> = u0.iter().filter(|(_, i)| rule.contains(i)).collect();
        r.enemy_units_visible += vis_u.len();
        r.enemy_units_kept += u1.len();
        r.enemy_units_lost += vis_u.iter().filter(|u| !u1.contains(u)).count();
        r.enemy_units_leaked += u1.iter().filter(|(_, i)| !rule.contains(i)).count();
        let vis_c = c0.iter().filter(|i| rule.contains(i)).count();
        r.enemy_cities_visible += vis_c;
        r.enemy_cities_lost += c0.iter().filter(|i| rule.contains(i) && !c1.contains(i)).count();
        r.enemy_cities_leaked += c1.iter().filter(|i| !rule.contains(i)).count();
    }
    r
}

/// The engine's own vision rule (`update_exploration`: cities see their border, capitals 2; units see 1, scouts and
/// mountains 2) run on the saved state: (tiles the save holds explored, tiles the rule would add). In agreement it adds nothing.
pub fn vision_rule_adds(g: &Game, pov: i32) -> (usize, Vec<i32>) {
    let mut c = g.clone();
    c.state.settings._are_you_sure = true;
    let before = explored(&c, pov);
    let _ = update_exploration(&mut c.state, pov);
    let after = explored(&c, pov);
    let mut added: Vec<i32> = after.difference(&before).copied().collect();
    added.sort();
    (before.len(), added)
}

pub fn check_vision_rule(g: &Game, pov: i32) -> String {
    let (n, added) = vision_rule_adds(g, pov);
    let sz = g.state.settings.size;
    let ex: Vec<String> = added.iter().take(6).map(|i| format!("({},{})", i % sz, i / sz)).collect();
    let why: Vec<String> = added.iter().take(2).map(|&i| format!("[{}]", sources_of(g, pov, i))).collect();
    format!("p{} saved_explored {} rule_adds {} {} {}", pov, n, added.len(), ex.join(" "), why.join(" "))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Skipped when the decoded saves are not restored (`sh scripts/restore_saves.sh`).
    #[test]
    fn view_and_vision_rule_agree_with_saves() {
        for name in ["ed6cb932-c741-4ba8-9fd3-66f5c3f6bad7_t5", "e15f392c-e542-4777-a16f-64a63932d141_t11", "af181c8f-32ad-4e53-b0f7-ded76d6ba2bc_t12"] {
            let path = format!("{}/../../saves/{name}.json", env!("CARGO_MANIFEST_DIR"));
            let Ok(txt) = std::fs::read_to_string(&path) else { continue };
            let v: Value = serde_json::from_str(&txt).unwrap();
            let g = load_exact(&v, "current", 1).unwrap();
            for p in g.state.tribes.keys().copied() {
                let r = check_view(&v, &g, p, true);
                assert!(r.ok(), "{name}: {r}");
                assert_eq!(vision_rule_adds(&g, p).1.len(), 0, "{name} p{p}: the vision rule adds tiles the save lacks");
            }
        }
    }
}
