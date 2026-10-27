//! What-if advisor (Phase 2, capability 1: "know possible moves and outcomes"). Given a save and a player it returns, as
//! JSON, (a) the player's situation as that player sees it (fog-correct: `fog::player_view`), (b) every legal move with the
//! exact outcome the forward model predicts (the move is played on a clone and the two states are diffed), and (c) for the
//! moves worth a second look, the worst-case reply of every visible enemy. `tools/whatif.py` turns this into plain text.
//! No rules live here: moves come from `Game::legal_moves`, outcomes from `Game::play_move`, replies from the same engine
//! with the enemy as the mover.
use crate::api;
use crate::fog;
use crate::functions as f;
use crate::game::Game;
use crate::moves::*;
use crate::settings::units::get_unit_setting;
use crate::states::*;
use crate::types::*;
use serde_json::{json, Value};
use std::collections::{BTreeMap, HashMap, HashSet};

pub struct Opts {
    /// Player to advise; None = the human (non-bot) tribe of the save.
    pub player: Option<i32>,
    /// Play the move list on the true map instead of the player's view (validation only: leaks hidden information).
    pub truth: bool,
    /// Worst-case reply lookahead for the shortlisted moves.
    pub lookahead: bool,
    /// `data/distributions.json` (ruin reward table); None = no random-outcome tables.
    pub dist: Option<String>,
}

fn xy(sz: i32, idx: i32) -> (i32, i32) {
    (idx % sz, idx / sz)
}

fn tribe_name(s: &GameState, id: i32) -> String {
    s.tribes.get(&id).map_or("?".into(), |t| format!("{:?}", t.tribe_type))
}

fn unit_json(s: &GameState, u: &UnitState) -> Value {
    let (x, y) = xy(s.settings.size, u.coords.idx);
    json!({
        "owner": u.owner, "tribe": tribe_name(s, u.owner), "type": format!("{:?}", u.unit_type), "x": x, "y": y,
        "hp": u.health, "max": f::get_unit_max_health(u), "vet": u.veteran, "moved": u.moved, "attacked": u.attacked,
        "kills": u.kills, "cost": get_unit_setting(u.unit_type).cost,
        "effects": u.effects.iter().map(|e| format!("{e:?}")).collect::<Vec<_>>(),
        "passenger": u.passenger_type.map(|p| format!("{p:?}")),
    })
}

fn city_json(s: &GameState, c: &CityState) -> Value {
    let (x, y) = xy(s.settings.size, c.idx);
    let cap = s.tiles.get(&c.idx).map_or(0, |t| t.capital_of);
    json!({
        "owner": c.owner, "tribe": tribe_name(s, c.owner), "name": c.name, "x": x, "y": y, "level": c.level, "pop": c.progress,
        "pop_needed": c.level + 1, "capital": cap == c.owner && cap != 0, "connected": c.connected_to_capital,
        "walls": c.has_walls(), "workshop": c.has_workshop(), "park": c.has_park(), "income": f::get_city_production(s, c),
        "besieged": f::is_under_siege(s, c.idx),
    })
}

/// Unit owner at a tile, if any.
fn unit_at(s: &GameState, idx: i32) -> Option<&UnitState> {
    s.tribes.values().flat_map(|t| t.units.iter()).find(|u| u.coords.idx == idx)
}

#[derive(Clone)]
struct Hit {
    enemy_type: String,
    enemy_owner: i32,
    from: (i32, i32),
    via: Option<(i32, i32)>,
    target: (i32, i32),
    target_type: String,
    dmg: f32,
    kills: bool,
    retaliation: f32,
}

fn hit_json(h: &Hit) -> Value {
    json!({"enemy": h.enemy_type, "owner": h.enemy_owner, "from": [h.from.0, h.from.1], "via": h.via.map(|v| [v.0, v.1]),
           "target": [h.target.0, h.target.1], "target_type": h.target_type, "dmg": h.dmg, "kills": h.kills, "retaliation": h.retaliation})
}

fn unit_hp_at(s: &GameState, owner: i32, idx: i32) -> Option<f32> {
    s.tribes.get(&owner)?.units.iter().find(|u| u.coords.idx == idx).map(|u| u.health)
}

/// Every attack a visible enemy could make on `pov`'s units next (each enemy unit alone, from where it stands or after one
/// step; fresh turn: all its units untired). Exact per attack; the set is the worst case, not a prediction of what the bot does.
/// Also the enemy captures of `pov`'s cities (`captures`).
fn enemy_hits(g: &Game, pov: i32) -> (Vec<Hit>, Vec<(i32, i32, String)>) {
    let sz = g.state.settings.size;
    let mine: HashSet<i32> = g.state.tribes.get(&pov).map(|t| t.units.iter().map(|u| u.coords.idx).chain(t.cities.iter().map(|c| c.idx)).collect()).unwrap_or_default();
    let my_cities: HashSet<i32> = g.state.tribes.get(&pov).map(|t| t.cities.iter().map(|c| c.idx).collect()).unwrap_or_default();
    let mut hits = Vec::new();
    let mut caps = Vec::new();
    let enemies: Vec<i32> = g.state.tribes.iter().filter(|(id, t)| **id != pov && t.killed_turn <= 0 && t.resigned_turn <= 0 && !t.units.is_empty()).map(|(id, _)| *id).collect();
    for e in enemies {
        let mut base = g.clone();
        base.state.settings.current_player_turn_id = e;
        if let Some(t) = base.state.tribes.get_mut(&e) {
            for u in t.units.iter_mut() { u.moved = false; u.attacked = false; }
        }
        let ms = base.legal_moves();
        // a unit is worth a look only when one of my tiles lies within (movement + range + 1) of it
        let near = |from: i32, reach: i32| mine.iter().any(|m| f::get_chebyshev_distance(from, *m, sz) <= reach);
        let mut work: Vec<(Option<i32>, Option<i32>, Box<dyn Move>)> = Vec::new(); // (step target, attacker idx, attack move)
        for m in ms.iter() {
            match m.move_type() {
                MoveType::Attack => {
                    let (Ok(s), Ok(t)) = (m.source_idx(), m.target_idx()) else { continue };
                    if mine.contains(&(t as i32)) { work.push((None, Some(s as i32), dyn_clone::clone_box(&**m))); }
                }
                _ => {}
            }
        }
        for (_, atk, m) in work {
            let (s, t) = (atk.unwrap(), m.target_idx().unwrap() as i32);
            if let Some(h) = eval_attack(&base, pov, e, s, t, None, m.as_ref()) { hits.push(h); }
        }
        // one step, then attack (and enemy units that can walk into one of my cities: a capture threat)
        let enemy_units: Vec<(i32, i32, UnitType)> = base.state.tribes.get(&e).map(|t| t.units.iter().map(|u| (u.coords.idx, 0, u.unit_type)).collect()).unwrap_or_default();
        for (uidx, _, _) in enemy_units {
            let Some(u) = f::get_unit_at(&base.state, uidx) else { continue };
            let reach = f::get_unit_movement(&base.state, u) + get_unit_setting(u.unit_type).range + 1;
            if !near(uidx, reach) { continue; }
            for sm in ms.iter().filter(|m| m.move_type() == MoveType::Step && m.source_idx().ok() == Some(uidx as usize)) {
                let dest = sm.target_idx().unwrap() as i32;
                let mut g2 = base.clone();
                if g2.search_move(sm.as_ref()).is_none() { continue; }
                for am in g2.legal_moves() {
                    match am.move_type() {
                        MoveType::Attack if am.source_idx().ok() == Some(dest as usize) => {
                            let t = am.target_idx().unwrap() as i32;
                            if mine.contains(&t) {
                                if let Some(h) = eval_attack(&g2, pov, e, dest, t, Some(xy(sz, uidx)), am.as_ref()) { hits.push(h); }
                            }
                        }
                        MoveType::Capture if am.source_idx().ok() == Some(dest as usize) => {}
                        _ => {}
                    }
                }
                // a step onto one of my (empty) cities is a capture threat when a Capture move appears there
                if my_cities.contains(&dest) && g2.legal_moves().iter().any(|m| m.move_type() == MoveType::Capture && m.source_idx().ok() == Some(dest as usize)) {
                    caps.push((xy(sz, dest).0, xy(sz, dest).1, format!("{:?}", u.unit_type)));
                }
            }
        }
    }
    (hits, caps)
}

fn eval_attack(base: &Game, pov: i32, e: i32, from_idx: i32, t: i32, via: Option<(i32, i32)>, m: &dyn Move) -> Option<Hit> {
    let sz = base.state.settings.size;
    let attacker = f::get_unit_at(&base.state, from_idx)?;
    let a_hp = attacker.health;
    let a_type = format!("{:?}", attacker.unit_type);
    let tgt_hp = unit_hp_at(&base.state, pov, t);
    let tgt_type = f::get_unit_at(&base.state, t).map_or("City".to_string(), |u| format!("{:?}", u.unit_type));
    let mut g2 = base.clone();
    let _ = g2.search_move(m)?;
    let after = unit_hp_at(&g2.state, pov, t);
    let (dmg, kills) = match (tgt_hp, after) {
        (Some(b), Some(a)) => (b - a, false),
        (Some(b), None) => (b, true),
        _ => return None, // not a unit of mine (a city attack with no unit inside)
    };
    let ret = unit_hp_at(&g2.state, e, from_idx).or_else(|| unit_hp_at(&g2.state, e, t)).map_or(a_hp, |h| a_hp - h);
    let _ = via;
    Some(Hit { enemy_type: a_type, enemy_owner: e, from: via.unwrap_or(xy(sz, from_idx)), via: via.map(|_| xy(sz, from_idx)), target: xy(sz, t), target_type: tgt_type, dmg, kills, retaliation: ret.max(0.0) })
}

/// Summary of the worst case for `pov`'s units: per unit, the attacks it can take and whether the enemies together can kill it.
fn reply_json(g: &Game, pov: i32) -> Value {
    let (hits, caps) = enemy_hits(g, pov);
    let sz = g.state.settings.size;
    let mut per: BTreeMap<(i32, i32), Vec<&Hit>> = BTreeMap::new();
    for h in &hits { per.entry(h.target).or_default().push(h); }
    let mut units = Vec::new();
    for (tgt, hs) in per {
        let idx = tgt.1 * sz + tgt.0;
        let hp = unit_hp_at(&g.state, pov, idx).unwrap_or(0.0);
        // one best attack per enemy unit (its position + type), summed: exact because a unit's damage does not depend on how hurt its target is
        let mut best: HashMap<(i32, i32, i32), f32> = HashMap::new();
        for h in &hs {
            let key = (h.enemy_owner, h.from.0, h.from.1);
            let e = best.entry(key).or_insert(0.0);
            if h.dmg > *e { *e = h.dmg; }
        }
        let total: f32 = best.values().sum();
        let single = hs.iter().any(|h| h.kills);
        units.push(json!({"x": tgt.0, "y": tgt.1, "type": hs[0].target_type, "hp": hp, "attackers": best.len(),
            "total_dmg": total, "single_kill": single, "can_die": single || total >= hp,
            "hits": hs.iter().take(6).map(|h| hit_json(h)).collect::<Vec<_>>()}));
    }
    json!({"units": units, "captures": caps.iter().map(|c| json!({"x": c.0, "y": c.1, "by": c.2})).collect::<Vec<_>>()})
}

// ---------------------------------------------------------------------------------------------------------------------
// outcome diff

fn unit_key(u: &UnitState) -> (i32, i32, String, i32) {
    (u.owner, u.coords.idx, format!("{:?}", u.unit_type), (u.health * 10.0) as i32)
}

/// What a move did, as events (hp changes, kills, units moved/created, cities, structures, resources, techs, stars).
pub fn diff(before: &GameState, after: &GameState, pov: i32) -> Value {
    let sz = before.settings.size;
    let mut ev: Vec<Value> = Vec::new();
    // units: match identical, then same tile/type with different hp, then moved (same owner/type), then the rest
    let flat = |s: &GameState| -> Vec<UnitState> { s.tribes.values().flat_map(|t| t.units.iter().cloned()).collect() };
    let out_now: HashSet<i32> = after.tribes.iter().filter(|(id, t)| t.killed_turn > 0 && before.tribes.get(&**id).map_or(false, |o| o.killed_turn <= 0)).map(|(id, _)| *id).collect();
    for id in &out_now { ev.push(json!({"ev": "tribe_out", "owner": id, "tribe": tribe_name(before, *id)})); }
    let mut b: Vec<UnitState> = flat(before).into_iter().filter(|u| !out_now.contains(&u.owner)).collect();
    let mut a: Vec<UnitState> = flat(after).into_iter().filter(|u| !out_now.contains(&u.owner)).collect();
    let mut i = 0;
    while i < b.len() {
        let k = unit_key(&b[i]);
        if let Some(j) = a.iter().position(|u| unit_key(u) == k) { b.remove(i); a.remove(j); } else { i += 1; }
    }
    let mut i = 0;
    while i < b.len() {
        if let Some(j) = a.iter().position(|u| u.owner == b[i].owner && u.coords.idx == b[i].coords.idx && u.unit_type == b[i].unit_type) {
            let (ub, ua) = (b.remove(i), a.remove(j));
            let (x, y) = xy(sz, ub.coords.idx);
            ev.push(json!({"ev": "hp", "owner": ub.owner, "tribe": tribe_name(before, ub.owner), "type": format!("{:?}", ub.unit_type), "x": x, "y": y, "from": ub.health, "to": ua.health, "max": f::get_unit_max_health(&ua)}));
        } else { i += 1; }
    }
    let mut i = 0;
    while i < b.len() {
        // moved: same owner and type, not otherwise explained (prefer the nearest)
        let cand: Vec<usize> = (0..a.len()).filter(|&j| a[j].owner == b[i].owner && a[j].unit_type == b[i].unit_type).collect();
        if let Some(&j) = cand.iter().min_by_key(|&&j| f::get_chebyshev_distance(a[j].coords.idx, b[i].coords.idx, sz)) {
            let (ub, ua) = (b.remove(i), a.remove(j));
            let (x0, y0) = xy(sz, ub.coords.idx);
            let (x1, y1) = xy(sz, ua.coords.idx);
            ev.push(json!({"ev": "moved", "owner": ub.owner, "tribe": tribe_name(before, ub.owner), "type": format!("{:?}", ub.unit_type), "from": [x0, y0], "to": [x1, y1], "hp_from": ub.health, "hp_to": ua.health, "max": f::get_unit_max_health(&ua)}));
        } else { i += 1; }
    }
    for ub in &b {
        let (x, y) = xy(sz, ub.coords.idx);
        // same tile, other type: upgraded / boarded / converted
        if let Some(j) = a.iter().position(|u| u.coords.idx == ub.coords.idx) {
            let ua = &a[j];
            ev.push(json!({"ev": "became", "owner": ub.owner, "new_owner": ua.owner, "type": format!("{:?}", ub.unit_type), "to_type": format!("{:?}", ua.unit_type), "x": x, "y": y, "hp_from": ub.health, "hp_to": ua.health}));
        } else {
            ev.push(json!({"ev": "gone", "owner": ub.owner, "tribe": tribe_name(before, ub.owner), "type": format!("{:?}", ub.unit_type), "x": x, "y": y, "hp": ub.health}));
        }
    }
    for ua in &a {
        if b.iter().any(|u| u.coords.idx == ua.coords.idx) { continue; }
        let (x, y) = xy(sz, ua.coords.idx);
        let became = ev.iter().any(|e| e["ev"] == "became" && e["x"] == x && e["y"] == y);
        if became { continue; }
        ev.push(json!({"ev": "new", "owner": ua.owner, "tribe": tribe_name(after, ua.owner), "type": format!("{:?}", ua.unit_type), "x": x, "y": y, "hp": ua.health}));
    }
    // cities
    let cities = |s: &GameState| -> BTreeMap<i32, (i32, i32, i32, String)> { s.tribes.values().flat_map(|t| t.cities.iter()).map(|c| (c.idx, (c.owner, c.level, c.progress, c.name.clone()))).collect() };
    let (cb, ca) = (cities(before), cities(after));
    for (idx, v) in &ca {
        let (x, y) = xy(sz, *idx);
        match cb.get(idx) {
            None => ev.push(json!({"ev": "city_new", "x": x, "y": y, "name": v.3, "owner": v.0, "level": v.1})),
            Some(o) if o != v => ev.push(json!({"ev": "city", "x": x, "y": y, "name": v.3, "owner_from": o.0, "owner_to": v.0, "level_from": o.1, "level_to": v.1, "pop_from": o.2, "pop_to": v.2})),
            _ => {}
        }
    }
    for (idx, v) in &cb {
        if !ca.contains_key(idx) { let (x, y) = xy(sz, *idx); ev.push(json!({"ev": "city_gone", "x": x, "y": y, "name": v.3})); }
    }
    // structures, resources, terrain, territory, exploration
    let seen = |i: &i32| before.tiles.get(i).map_or(false, |t| t.explorers.contains(&pov));
    let st = |s: &GameState, i: &i32| s.structures.get(i).and_then(|x| x.as_ref()).map(|x| format!("{:?}", x.structure_type));
    let mut sc = 0;
    for i in before.structures.keys().filter(|i| seen(i)) {
        let (x0, x1) = (st(before, i), st(after, i));
        let (l0, l1) = (before.structures.get(i).and_then(|x| x.as_ref()).map(|x| x.level), after.structures.get(i).and_then(|x| x.as_ref()).map(|x| x.level));
        if x0 != x1 || (x0.is_some() && l0 != l1 && cb.get(i).is_none()) {
            sc += 1;
            if sc <= 6 { let (x, y) = xy(sz, *i); ev.push(json!({"ev": "structure", "x": x, "y": y, "from": x0, "to": x1, "level_from": l0, "level_to": l1})); }
        }
    }
    for i in before.resources.keys().filter(|i| seen(i)) {
        let r0 = before.resources.get(i).and_then(|x| x.as_ref()).map(|x| format!("{:?}", x.resource_type));
        let r1 = after.resources.get(i).and_then(|x| x.as_ref()).map(|x| format!("{:?}", x.resource_type));
        if r0 != r1 { let (x, y) = xy(sz, *i); ev.push(json!({"ev": "resource", "x": x, "y": y, "from": r0, "to": r1})); }
    }
    let (mut terr, mut own_gain, mut own_lose, mut explored) = (Vec::new(), 0, 0, 0);
    for (i, t0) in before.tiles.iter() {
        let Some(t1) = after.tiles.get(i) else { continue };
        let vis = t0.explorers.contains(&pov);
        if t1.explorers.contains(&pov) && !vis { explored += 1; }
        if !vis { continue; }
        if t0.terrain_type != t1.terrain_type || t0.is_flooded() != t1.is_flooded() { terr.push((*i, format!("{:?}", t0.terrain_type), format!("{:?}", t1.terrain_type))); }
        if t0.owner != t1.owner { if t1.owner == pov { own_gain += 1; } else if t0.owner == pov { own_lose += 1; } }
    }
    if !terr.is_empty() {
        let (x, y) = xy(sz, terr[0].0);
        ev.push(json!({"ev": "terrain", "n": terr.len(), "x": x, "y": y, "from": terr[0].1, "to": terr[0].2}));
    }
    // techs and relations
    let techs = |s: &GameState| -> HashSet<String> { s.tribes.get(&pov).map(|t| t.tech_vanilla.iter().filter(|x| x.discovered).map(|x| format!("{:?}", x.tech_type)).collect()).unwrap_or_default() };
    let (tb, ta) = (techs(before), techs(after));
    let mut newt: Vec<&String> = ta.difference(&tb).collect();
    newt.sort();
    for t in newt { ev.push(json!({"ev": "tech", "tech": t})); }
    if let (Some(tb), Some(ta)) = (before.tribes.get(&pov), after.tribes.get(&pov)) {
        for (o, r1) in ta.relations.iter() {
            let r0 = tb.relations.get(o);
            if r0.map(|r| (r.state, r.embassy_level, r.has_offered_peace)) != Some((r1.state, r1.embassy_level, r1.has_offered_peace)) {
                ev.push(json!({"ev": "relation", "with": o, "tribe": tribe_name(after, *o), "state_to": r1.state, "embassy_to": r1.embassy_level, "offered_to": r1.has_offered_peace}));
            }
        }
    }
    let stars = |s: &GameState| s.tribes.get(&pov).map_or(0, |t| t.stars);
    json!({"stars": [stars(before), stars(after)], "events": ev, "territory": [own_gain, own_lose], "explored": explored})
}

// ---------------------------------------------------------------------------------------------------------------------
// moves

/// A free tech is picked at random among the researchable ones: say "one of N" instead of the engine's seeded pick.
fn tech_any(evs: &Value, s: &GameState, pov: i32) -> Value {
    let n = s.tribes.get(&pov).map_or(0, |t| crate::settings::technology::get_researchable_techs(&t.tech_vanilla, t.tribe_type).len());
    json!(evs.as_array().into_iter().flatten().map(|e| if e["ev"] == "tech" { json!({"ev": "tech_any", "n": n}) } else { e.clone() }).collect::<Vec<_>>())
}

fn group_of(mv: &dyn Move) -> &'static str {
    match mv.move_type() {
        MoveType::Step => "move",
        MoveType::Attack => "attack",
        MoveType::Summon => if api::kind(mv) == "Upgrade" { "upgrade" } else { "train" },
        MoveType::Build => "build",
        MoveType::Research => "research",
        MoveType::Capture => "capture",
        MoveType::Harvest => "harvest",
        MoveType::Reward => "reward",
        MoveType::Ability => match api::kind(mv).as_str() {
            "PeaceTreaty" | "PeaceRequestResponse" | "BreakPeace" | "EstablishEmbassy" | "DestroyEmbassy" => "diplomacy",
            "Recover" | "Disband" => "unit_order",
            _ => "ability",
        },
        _ => "other",
    }
}

fn named(mv: &dyn Move) -> Option<String> {
    mv.structure_type().map(|t| format!("{t:?}"))
        .or_else(|_| mv.tech_type().map(|t| format!("{t:?}")))
        .or_else(|_| mv.unit_type().map(|t| format!("{t:?}")))
        .or_else(|_| mv.ability_type().map(|t| format!("{t:?}")))
        .or_else(|_| mv.reward_type().map(|t| format!("{t:?}")))
        .ok()
}

/// Names (verb + type, no coordinates) of the moves in a list, counted: used to say what a move unlocks.
fn move_names(g: &Game) -> BTreeMap<String, usize> {
    let mut m = BTreeMap::new();
    for mv in g.legal_moves() {
        if matches!(mv.move_type(), MoveType::Step | MoveType::Attack | MoveType::EndTurn) { continue; }
        let n = format!("{} {}", api::kind(mv.as_ref()), named(mv.as_ref()).unwrap_or_default());
        *m.entry(n.trim().to_string()).or_insert(0) += 1;
    }
    m
}

struct Ctx<'a> {
    base: &'a Game,
    pov: i32,
    dice: Option<api::Dice>,
}

fn attack_json(before: &GameState, after: &GameState, src: i32, tgt: i32) -> Option<Value> {
    let sz = before.settings.size;
    let a0 = f::get_unit_at(before, src)?;
    let d0 = f::get_unit_at(before, tgt);
    let (ax, ay) = xy(sz, src);
    let (tx, ty) = xy(sz, tgt);
    // attacker afterwards: still at src, or moved onto the target after a kill; defender: still at the target and not the attacker
    let a1 = f::get_unit_at(after, src).filter(|u| u.owner == a0.owner && u.unit_type == a0.unit_type)
        .or_else(|| f::get_unit_at(after, tgt).filter(|u| u.owner == a0.owner && u.unit_type == a0.unit_type));
    let d1 = f::get_unit_at(after, tgt).filter(|u| d0.map_or(false, |d| u.owner == d.owner));
    let city = f::get_city_at(before, tgt).map(|c| city_json(before, c));
    Some(json!({
        "attacker": {"type": format!("{:?}", a0.unit_type), "cost": get_unit_setting(a0.unit_type).cost, "x": ax, "y": ay, "hp": a0.health, "max": f::get_unit_max_health(a0), "hp_after": a1.map(|u| u.health), "died": a1.is_none(), "moved_in": a1.map_or(false, |u| u.coords.idx == tgt)},
        "defender": d0.map(|d| json!({"type": format!("{:?}", d.unit_type), "cost": get_unit_setting(d.unit_type).cost, "owner": d.owner, "tribe": tribe_name(before, d.owner), "x": tx, "y": ty, "hp": d.health, "max": f::get_unit_max_health(d), "hp_after": d1.map(|u| u.health), "killed": d1.is_none(), "in_city": city.is_some()})),
        "dmg_dealt": d0.map(|d| d.health - d1.map_or(0.0, |u| u.health)),
        "dmg_taken": a1.map_or(a0.health, |u| a0.health - u.health),
    }))
}

fn describe_move(cx: &mut Ctx, mv: &dyn Move) -> Value {
    let g = cx.base;
    let pov = cx.pov;
    let sz = g.state.settings.size;
    let key = mv.serialize();
    let label = api::label(&g.state, mv);
    let group = group_of(mv);
    let diplo = group == "diplomacy";
    let src = if diplo { None } else { mv.source_idx().ok().map(|i| i as i32) };
    let tgt = if diplo { None } else { mv.target_idx().ok().map(|i| i as i32) };
    let actor = src.and_then(|i| f::get_unit_at(&g.state, i)).filter(|u| u.owner == pov).map(|u| unit_json(&g.state, u));
    let explored = |i: i32| g.state.tiles.get(&i).map_or(false, |t| t.explorers.contains(&pov));
    let mut v = json!({
        "label": label, "key": key, "kind": api::kind(mv), "group": group, "named": named(mv),
        "src": src.map(|i| { let p = xy(sz, i); [p.0, p.1] }), "target": tgt.map(|i| { let p = xy(sz, i); [p.0, p.1] }),
        "actor": actor,
        "other": if diplo { key["src"].as_i64().map(|o| json!({"id": o, "tribe": tribe_name(&g.state, o as i32)})) } else { None },
        "fog": tgt.map_or(false, |i| !explored(i)) || (mv.move_type() == MoveType::Reward && named(mv).as_deref() == Some("Explorer")),
    });
    // random outcome: a ruin is examined with a table of rewards, not one exact result
    let ruin = mv.move_type() == MoveType::Capture && src.map_or(false, |i| f::get_structure_at(&g.state, i).map_or(false, |s| s.structure_type == StructureType::Ruin));
    if ruin {
        if let Some(d) = cx.dice.as_ref() {
            let i = src.unwrap();
            let w = d.ruin_weights(&g.state, i);
            let tot: f64 = w.iter().map(|x| x.1).sum();
            let mut outs = Vec::new();
            for (r, p) in w {
                let mut g2 = api::clone(g);
                let m2 = CaptureMove::with_reward(i, r);
                if g2.play_move(&m2).is_some() {
                    let mut o = diff(&g.state, &g2.state, pov);
                    if r == RuinsRewardType::FreeTech { o["events"] = tech_any(&o["events"], &g.state, pov); }
                    o["reward"] = json!(format!("{r:?}"));
                    o["p"] = json!(p / tot);
                    outs.push(o);
                }
            }
            v["random"] = json!({"what": "ruin reward (land or water table from data/distributions.json)", "outcomes": outs});
            return v;
        }
    }
    let mut g2 = api::clone(g);
    match api::apply(&mut g2, mv) {
        None => { v["error"] = json!("refused"); }
        Some(_) => {
            let mut o = diff(&g.state, &g2.state, pov);
            let cost = o["stars"][0].as_i64().unwrap_or(0) - o["stars"][1].as_i64().unwrap_or(0);
            v["stars"] = o["stars"].take();
            v["cost"] = json!(cost);
            v["events"] = o["events"].take();
            v["territory"] = o["territory"].take();
            v["explored_new"] = o["explored"].take();
            if group == "attack" {
                if let (Some(s), Some(t)) = (src, tgt) { v["attack"] = attack_json(&g.state, &g2.state, s, t).unwrap_or(Value::Null); v["score"] = json!(attack_score(&v)); }
            }
            // what the acting unit can attack from where it ends up
            if group == "move" || group == "attack" || group == "ability" {
                let at = match group { "move" => tgt, _ => src };
                // after a kill the attacker may have moved in; follow it by its type and owner
                let at = if group == "attack" { v["attack"]["attacker"]["moved_in"].as_bool().and_then(|m| if m { tgt } else { src }) } else { at };
                if let Some(at) = at {
                    let mut targets = Vec::new();
                    if f::get_unit_at(&g2.state, at).map_or(false, |u| u.owner == pov) {
                        for m in g2.legal_moves() {
                            if m.move_type() == MoveType::Attack && m.source_idx().ok() == Some(at as usize) {
                                let t = m.target_idx().unwrap() as i32;
                                if let Some(d) = f::get_unit_at(&g2.state, t) {
                                    let mut g3 = api::clone(&g2);
                                    if g3.search_move(m.as_ref()).is_some() {
                                        let ad = attack_json(&g2.state, &g3.state, at, t);
                                        targets.push(json!({"type": format!("{:?}", d.unit_type), "x": xy(sz, t).0, "y": xy(sz, t).1, "hp": d.health,
                                            "dmg": ad.as_ref().map(|a| a["dmg_dealt"].clone()), "kill": ad.as_ref().map(|a| a["defender"]["killed"].clone()), "taken": ad.as_ref().map(|a| a["dmg_taken"].clone())}));
                                    }
                                }
                            }
                        }
                    }
                    v["then_attack"] = json!(targets);
                }
            }
            if matches!(group, "research" | "build" | "upgrade" | "reward") {
                let (n0, n1) = (move_names(g), move_names(&g2));
                let mut un = Vec::new();
                for (k, c) in &n1 { let c0 = n0.get(k).copied().unwrap_or(0); if *c > c0 { un.push(json!({"name": k, "n": c - c0})); } }
                v["unlocks"] = json!(un);
            }
        }
    }
    v
}

/// Peace offers and embassies with tribes the player has met but whose cities it has not seen: the generator aims them at the
/// other tribe's capital, which the view hides. They are generated on the true state and shown with no tile, only the tribe.
fn diplomacy_extras(truth: &Game, view: &Game, pov: i32) -> Vec<Box<dyn Move>> {
    let vkeys: HashSet<String> = view.legal_moves().iter().map(|m| m.serialize().to_string()).collect();
    let known = truth.state.tribes.get(&pov).map(|t| t.known_players.clone()).unwrap_or_default();
    truth.legal_moves().into_iter().filter(|m| {
        matches!(api::kind(m.as_ref()).as_str(), "PeaceTreaty" | "EstablishEmbassy") && !vkeys.contains(&m.serialize().to_string())
            && m.serialize()["src"].as_i64().map_or(false, |o| known.contains(&(o as i32)))
    }).collect()
}

/// `describe_move` for such a move: played on the true state, but only the relation change and the stars are reported.
fn describe_hidden_diplomacy(truth: &Game, pov: i32, mv: &dyn Move) -> Value {
    let mut j = describe_move(&mut Ctx { base: truth, pov, dice: None }, mv);
    j["events"] = json!(j["events"].as_array().into_iter().flatten().filter(|e| e["ev"] == "relation").cloned().collect::<Vec<_>>());
    j["label"] = json!(format!("{} {}", j["kind"].as_str().unwrap_or(""), j["other"]["tribe"].as_str().unwrap_or("")));
    j["key"] = mv.serialize();
    j["territory"] = json!([0, 0]);
    j["explored_new"] = json!(0);
    j["hidden_target"] = json!(true);
    j
}

/// Static reach of each enemy unit (movement + range, Chebyshev, terrain ignored): a rough "in reach" for step exposure.
fn enemy_reach(g: &Game, pov: i32) -> Vec<(i32, String, i32)> {
    let mut out = Vec::new();
    for (id, t) in g.state.tribes.iter() {
        if *id == pov { continue; }
        for u in &t.units {
            let reach = f::get_unit_movement(&g.state, u) + get_unit_setting(u.unit_type).range;
            out.push((u.coords.idx, format!("{:?}", u.unit_type), reach));
        }
    }
    out
}

pub fn analyze(save: &Value, o: &Opts) -> Result<Value, String> {
    let g0 = fog::load_exact(save, "current", 1)?;
    let humans: Vec<i32> = g0.state.tribes.iter().filter(|(_, t)| !t.bot).map(|(k, _)| *k).collect();
    let pov = o.player.or_else(|| humans.first().copied()).ok_or("no human player; pass --player")?;
    if !g0.state.tribes.contains_key(&pov) { return Err(format!("no player {pov} in this save")); }
    let g1 = fog::load_exact(save, "current", pov)?;
    analyze_game(g1, pov, o)
}

/// `analyze` on a loaded game (the true state): `pov` moves.
pub fn analyze_game(mut g1: Game, pov: i32, o: &Opts) -> Result<Value, String> {
    g1.state.settings.current_player_turn_id = pov;
    let view = if o.truth { g1.clone() } else { fog::player_view(&g1, pov) };
    let st = &view.state;
    let sz = st.settings.size;
    let me = st.tribes.get(&pov).ok_or("no such tribe")?;
    let dice = o.dist.as_ref().and_then(|p| api::Dice::from_file(p, 1).ok());
    let mut cx = Ctx { base: &view, pov, dice };

    // --- situation
    let explored = st.tiles.values().filter(|t| t.explorers.contains(&pov)).count();
    let researchable: Vec<Value> = crate::settings::technology::get_researchable_techs(&me.tech_vanilla, me.tribe_type).iter()
        .map(|t| json!({"tech": format!("{t:?}"), "cost": f::get_tech_cost(me, *t)})).collect();
    let others: Vec<Value> = st.tribes.iter().filter(|(id, _)| **id != pov).map(|(id, t)| {
        let vu = t.units.iter().filter(|u| st.tiles.get(&u.coords.idx).map_or(false, |x| x.explorers.contains(&pov))).count();
        json!({"id": id, "tribe": format!("{:?}", t.tribe_type), "met": me.known_players.contains(id), "visible_units": vu, "visible_cities": t.cities.len(),
               "relation": me.relations.get(id).map(|r| r.state).unwrap_or(0), "at_peace": f::is_at_peace(st, pov, *id), "embassy": me.relations.get(id).map_or(0, |r| r.embassy_level)})
    }).collect();
    let enemy_units: Vec<Value> = st.tribes.iter().filter(|(id, _)| **id != pov).flat_map(|(_, t)| t.units.iter()).map(|u| unit_json(st, u)).collect();
    let enemy_cities: Vec<Value> = st.tribes.iter().filter(|(id, _)| **id != pov).flat_map(|(_, t)| t.cities.iter()).map(|c| city_json(st, c)).collect();
    let moves = view.legal_moves();
    let acting: HashSet<i32> = moves.iter().filter(|m| !matches!(m.move_type(), MoveType::EndTurn | MoveType::Resign) && !matches!(api::kind(m.as_ref()).as_str(), "Disband" | "Recover")).filter_map(|m| m.source_idx().ok()).map(|i| i as i32).collect();
    let my_units: Vec<Value> = me.units.iter().map(|u| { let mut j = unit_json(st, u); j["can_act"] = json!(acting.contains(&u.coords.idx)); j }).collect();
    let situation = json!({
        "turn": st.settings.turn, "player": pov, "tribe": format!("{:?}", me.tribe_type), "username": me.username, "is_bot": me.bot,
        "stars": me.stars, "income": f::get_tribe_spt(st, me), "score": me.score, "kills": me.kills, "map_size": sz,
        "techs": me.tech_vanilla.iter().filter(|t| t.discovered).map(|t| format!("{:?}", t.tech_type)).collect::<Vec<_>>(),
        "researchable": researchable,
        "cities": me.cities.iter().map(|c| city_json(st, c)).collect::<Vec<_>>(),
        "units": my_units,
        "enemy_units": enemy_units, "enemy_cities": enemy_cities, "others": others,
        "explored": [explored, st.tiles.len()], "tribes_total": st.tribes.len(), "tribes_met": me.known_players.len(),
        "truth_mode": o.truth, "pending_reward": moves.iter().any(|m| m.move_type() == MoveType::Reward),
    });

    // --- every legal move (EndTurn and Resign are not advice)
    let reach = enemy_reach(&view, pov);
    let mut out_moves: Vec<Value> = Vec::new();
    let mut seen_keys: HashSet<String> = HashSet::new();
    for mv in moves.iter().filter(|m| !matches!(m.move_type(), MoveType::EndTurn | MoveType::Resign)) {
        if !seen_keys.insert(mv.serialize().to_string()) { continue; } // the generator lists some moves twice (same key)
        let mut j = describe_move(&mut cx, mv.as_ref());
        // rough exposure for steps: enemy units whose static reach covers the destination
        if let Some(t) = j["target"].as_array().filter(|_| j["group"] == "move") {
            let ti = t[1].as_i64().unwrap_or(0) as i32 * sz + t[0].as_i64().unwrap_or(0) as i32;
            let n = reach.iter().filter(|(i, _, r)| f::get_chebyshev_distance(*i, ti, sz) <= *r).count();
            j["exposed_to"] = json!(n);
        }
        out_moves.push(j);
    }

    if !o.truth {
        for mv in diplomacy_extras(&g1, &view, pov) { out_moves.push(describe_hidden_diplomacy(&g1, pov, mv.as_ref())); }
    }

    // --- worst-case replies: now, and for the shortlisted moves
    let threats_now = reply_json(&view, pov);
    let mut replies: HashMap<usize, Value> = HashMap::new();
    if o.lookahead {
        let mut cand: Vec<(f64, usize)> = Vec::new();
        for (i, m) in out_moves.iter().enumerate() {
            let s = match m["group"].as_str().unwrap_or("") {
                "attack" => 1000.0 + attack_score(m),
                "move" => {
                    let t = m["then_attack"].as_array().map_or(0, |a| a.len()) as f64;
                    let ex = m["exposed_to"].as_i64().unwrap_or(0) as f64;
                    if t > 0.0 { 500.0 + t * 10.0 + ex } else if ex > 0.0 { 100.0 + ex } else { continue }
                }
                "capture" | "train" | "build" => 50.0,
                _ => continue,
            };
            cand.push((s, i));
        }
        cand.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap());
        for (_, i) in cand.into_iter().take(40) {
            let key = out_moves[i]["key"].clone();
            let Some(mv) = api::find(&view, &key) else { continue };
            let mut g2 = api::clone(&view);
            if api::apply(&mut g2, mv.as_ref()).is_some() { replies.insert(i, reply_json(&g2, pov)); }
        }
    }
    for (i, r) in replies { out_moves[i]["reply"] = r; }
    Ok(json!({"situation": situation, "moves": out_moves, "threats_now": threats_now}))
}

/// Ranking value of an attack: a kill is worth the victim's cost, otherwise damage dealt (as a share of its cost) minus damage taken.
fn attack_score(m: &Value) -> f64 {
    let a = &m["attack"];
    let d = &a["defender"];
    let dcost = d["cost"].as_f64().unwrap_or(2.0).max(1.0);
    let acost = a["attacker"]["cost"].as_f64().unwrap_or(2.0).max(1.0);
    let dmax = d["max"].as_f64().unwrap_or(10.0).max(1.0);
    let dealt = a["dmg_dealt"].as_f64().unwrap_or(0.0);
    let taken = a["dmg_taken"].as_f64().unwrap_or(0.0);
    let amax = a["attacker"]["max"].as_f64().unwrap_or(10.0).max(1.0);
    let killed = d["killed"].as_bool().unwrap_or(false);
    let died = a["attacker"]["died"].as_bool().unwrap_or(false);
    let gain = if killed { dcost } else { dealt / dmax * dcost };
    let loss = if died { acost } else { taken / amax * acost };
    gain - loss + if killed { 100.0 } else { 0.0 } - if died { 50.0 } else { 0.0 }
}

// ---------------------------------------------------------------------------------------------------------------------
// validation hook (pfreplay, PF_WHATIF=1): the tool's prediction for a logged move vs what the engine then does

/// Events a player could have predicted: drop those on tiles `pov` had not explored before the move.
fn visible_events(evs: &Value, explored: &HashSet<i32>, sz: i32) -> Vec<Value> {
    let at = |p: Option<(i64, i64)>| p.map_or(true, |(x, y)| explored.contains(&((y as i32) * sz + x as i32)));
    evs.as_array().into_iter().flatten().filter(|e| {
        let xy = if e["ev"] == "moved" { e["from"].as_array().map(|a| (a[0].as_i64().unwrap_or(0), a[1].as_i64().unwrap_or(0))) }
                 else { e["x"].as_i64().zip(e["y"].as_i64()) };
        at(xy)
    }).cloned().collect()
}

/// For a logged move about to be played on `truth` (the replay state): what `analyze` would have said (computed on
/// `pov`'s view) and whether it equals what the engine then does on the true state. Returns None if the move is not
/// in the view's move list. `dist` = ruin table (a ruin is a random outcome: the actual one must be among the predicted).
pub fn validate_move(truth: &Game, pov: i32, key: &Value, actual_mv: &dyn Move, dist: Option<&str>) -> Value {
    let mut view = fog::player_view(truth, pov);
    view.state.settings.current_player_turn_id = pov;
    let Some(mv) = api::find(&view, key) else {
        // a peace offer / embassy aimed at a capital the view hides: predicted from the true state, relation and stars only
        let Some(mv) = diplomacy_extras(truth, &view, pov).into_iter().find(|m| &m.serialize() == key) else { return json!({"in_view": false}) };
        let pred = describe_hidden_diplomacy(truth, pov, mv.as_ref());
        let mut g2 = api::clone(truth);
        if api::apply(&mut g2, actual_mv).is_none() { return json!({"in_view": true, "applies": false}); }
        let act = diff(&truth.state, &g2.state, pov);
        let rel = |e: &Value| -> Vec<Value> { e.as_array().into_iter().flatten().filter(|x| x["ev"] == "relation").cloned().collect() };
        return json!({"in_view": true, "kind": api::kind(mv.as_ref()), "group": "diplomacy", "fog": false, "match": rel(&pred["events"]) == rel(&act["events"]) && pred["stars"] == act["stars"]});
    };
    let dice = dist.and_then(|p| api::Dice::from_file(p, 1).ok());
    let mut cx = Ctx { base: &view, pov, dice };
    let pred = describe_move(&mut cx, mv.as_ref());
    let sz = truth.state.settings.size;
    let explored: HashSet<i32> = truth.state.tiles.iter().filter(|(_, t)| t.explorers.contains(&pov)).map(|(i, _)| *i).collect();
    let mut g2 = api::clone(truth);
    if api::apply(&mut g2, actual_mv).is_none() { return json!({"in_view": true, "applies": false}); }
    let act = diff(&truth.state, &g2.state, pov);
    let act_ev = visible_events(&act["events"], &explored, sz);
    let mut out = json!({"in_view": true, "kind": api::kind(mv.as_ref()), "group": pred["group"], "fog": pred["fog"]});
    if let Some(r) = pred.get("random") {
        // the actual result must be one of the predicted outcomes (same events and stars)
        let act_ev = tech_any(&json!(act_ev), &truth.state, pov).as_array().cloned().unwrap_or_default();
        let hit = r["outcomes"].as_array().into_iter().flatten().any(|o| visible_events(&o["events"], &explored, sz) == act_ev && o["stars"] == act["stars"]);
        out["random"] = json!(true);
        out["match"] = json!(hit);
        if !hit { out["why"] = json!({"actual": act_ev, "stars": act["stars"].clone(), "outcomes": r["outcomes"].as_array().into_iter().flatten().map(|o| json!({"reward": o["reward"], "events": visible_events(&o["events"], &explored, sz), "stars": o["stars"]})).collect::<Vec<_>>()}); }
        return out;
    }
    let no_out = |v: Vec<Value>| -> Vec<Value> { v.into_iter().filter(|e| e["ev"] != "tribe_out").collect() };
    let pev = no_out(visible_events(&pred["events"], &explored, sz));
    let act_ev = no_out(act_ev);
    let ev_ok = pev == act_ev;
    let st_ok = pred["stars"] == act["stars"];
    out["match"] = json!(ev_ok && st_ok);
    if !(ev_ok && st_ok) && std::env::var("PF_WHATIF_DBG").is_ok() {
        let mut gv = api::clone(&view);
        let _ = api::apply(&mut gv, mv.as_ref());
        eprintln!("WHATIF_DBG {} view-vs-true parts {:?} reward-key {} cities view {:?} true {:?}", pred["label"], api::diff_parts(&gv.state, &g2.state), key,
            gv.state.tribes.get(&pov).map(|t| t.cities.iter().map(|c| (c.idx, c.level, c.progress, c.rewards.len())).collect::<Vec<_>>()),
            g2.state.tribes.get(&pov).map(|t| t.cities.iter().map(|c| (c.idx, c.level, c.progress, c.rewards.len())).collect::<Vec<_>>()));
    }
    if !(ev_ok && st_ok) { out["why"] = json!({"pred": pev, "actual": act_ev, "stars": [pred["stars"].clone(), act["stars"].clone()]}); }
    if pred["group"] == "attack" {
        if let (Some(a), Some(s), Some(t)) = (pred.get("attack"), pred["src"].as_array(), pred["target"].as_array()) {
            let ix = |p: &Vec<Value>| p[1].as_i64().unwrap_or(0) as i32 * sz + p[0].as_i64().unwrap_or(0) as i32;
            let (si, ti) = (ix(s), ix(t));
            out["attack"] = json!({
                "att_uid": f::get_unit_at(&truth.state, si).map_or(0, |u| u.uid), "def_uid": f::get_unit_at(&truth.state, ti).map_or(0, |u| u.uid),
                "pred_dealt": a["dmg_dealt"], "pred_taken": a["dmg_taken"], "pred_killed": a["defender"]["killed"], "pred_died": a["attacker"]["died"],
                "pred_def_hp": a["defender"]["hp_after"], "pred_att_hp": a["attacker"]["hp_after"],
                "def_owner": a["defender"]["owner"],
            });
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::mapgen::{generate, MapGenSettings};

    fn game() -> Game {
        let tribes = vec![TribeType::XinXi, TribeType::Imperius, TribeType::Bardur, TribeType::Oumaji];
        let mut g = Game { state: generate(MapGenSettings { size: MapSize::Normal, map_type: MapType::Continents, tribes, seed: 11, version: 115, symmetric: false }) };
        g.post_load();
        g
    }

    #[test]
    fn lists_moves_with_outcomes_and_is_deterministic() {
        let g = game();
        let o = Opts { player: Some(1), truth: false, lookahead: true, dist: None };
        let a = analyze_game(g.clone(), 1, &o).unwrap();
        let b = analyze_game(g.clone(), 1, &o).unwrap();
        assert_eq!(a, b, "two runs on the same state agree");
        let moves = a["moves"].as_array().unwrap();
        assert!(!moves.is_empty());
        assert_eq!(a["situation"]["player"], 1);
        for m in moves {
            assert!(m["label"].as_str().is_some_and(|l| !l.is_empty()));
            assert!(m["group"].as_str().is_some());
            if m["group"] == "train" || m["group"] == "research" {
                // the stars the move costs are exactly what the state loses
                assert_eq!(m["cost"].as_i64().unwrap(), m["stars"][0].as_i64().unwrap() - m["stars"][1].as_i64().unwrap());
                assert!(m["cost"].as_i64().unwrap() >= 0);
            }
        }
    }

    #[test]
    fn attack_prediction_equals_playing_the_move() {
        // put an enemy Warrior next to player 1's Warrior and check dealt/taken against the engine's own result
        let mut g = game();
        let sz = g.state.settings.size;
        let (a_idx, d_idx) = {
            let u = g.state.tribes.get(&1).unwrap().units[0].coords.idx;
            (u, u + 1)
        };
        let mut e = g.state.tribes.get(&1).unwrap().units[0].clone();
        e.owner = 2; e.coords = crate::coords::Coords::from_index(d_idx, sz);
        g.state.tribes.get_mut(&2).unwrap().units.push(e);
        g.state.tribes.get_mut(&1).unwrap().known_players.insert(2);
        g.state.tribes.get_mut(&2).unwrap().known_players.insert(1);
        for t in g.state.tiles.values_mut() { t.explorers.insert(1); }
        g.post_load();
        g.state.settings.current_player_turn_id = 1;
        let o = Opts { player: Some(1), truth: true, lookahead: false, dist: None };
        let a = analyze_game(g.clone(), 1, &o).unwrap();
        let atk = a["moves"].as_array().unwrap().iter().find(|m| m["group"] == "attack" && m["target"] == json!([d_idx % sz, d_idx / sz]) && m["src"] == json!([a_idx % sz, a_idx / sz]));
        let atk = atk.expect("an attack on the adjacent enemy Warrior is listed");
        let at = &atk["attack"];
        let (h0, d0) = (at["attacker"]["hp"].as_f64().unwrap(), at["defender"]["hp"].as_f64().unwrap());
        let mut g2 = g.clone();
        let mv = api::find(&g2, &atk["key"]).unwrap();
        api::apply(&mut g2, mv.as_ref()).unwrap();
        let hp_a = f::get_unit_at(&g2.state, a_idx).map(|u| u.health as f64);
        let hp_d = f::get_unit_at(&g2.state, d_idx).filter(|u| u.owner == 2).map(|u| u.health as f64);
        assert_eq!(at["dmg_dealt"].as_f64().unwrap(), d0 - hp_d.unwrap_or(0.0));
        if let Some(h) = hp_a { assert_eq!(at["dmg_taken"].as_f64().unwrap(), h0 - h); }
    }
}
