//! Load a real v123 save (our `polytopia-state-json/2`, written by verify/state_v123.py) into a Polyfish GameState.
//!
//! Field map and the fields that can't be mapped: .scratchpad/investigations/pf-loader.md ("Field map").
//! Anything the loader has to drop or substitute is counted in `LoadReport`, so a run says what it lost.

use crate::coords::Coords;
use crate::game::Game;
use crate::states::*;
use crate::types::*;
use serde_json::Value;
use std::collections::{BTreeMap, HashSet};

/// v123 unit types Polyfish (v115) doesn't have, and the stand-in each one is loaded as.
/// The replay keeps the real type per unit id and reports it back.
pub const UNIT_STANDINS: &[(i32, UnitType)] = &[
    (46, UnitType::Amphibian),  // Mermaid: Aquarion start unit, 10 HP
    (48, UnitType::Tridention), // Swordsmaid: 15 HP
    (53, UnitType::Amphibian),  // Shark: 10 HP water unit
];

pub fn unit_type(id: i32) -> Option<UnitType> {
    if id != 0 {
        if let Some(t) = UnitType::from_repr(id as i8) {
            return Some(t);
        }
    }
    UNIT_STANDINS.iter().find(|(i, _)| *i == id).map(|(_, t)| *t)
}

/// What the loader dropped or substituted, by kind.
#[derive(Debug, Default, Clone, serde::Serialize)]
pub struct LoadReport {
    pub dropped: BTreeMap<String, i32>,
    pub substituted: BTreeMap<String, i32>,
}

impl LoadReport {
    fn drop(&mut self, what: String) {
        *self.dropped.entry(what).or_insert(0) += 1;
    }
    fn sub(&mut self, what: String) {
        *self.substituted.entry(what).or_insert(0) += 1;
    }
}

/// Enum from its game id, via its serde repr (None for an id Polyfish doesn't have).
fn enum_of<T: serde::de::DeserializeOwned>(k: i64) -> Option<T> {
    serde_json::from_value(Value::from(k)).ok()
}

fn i(v: &Value, k: &str) -> i64 {
    match v.get(k) {
        Some(Value::Bool(b)) => *b as i64,
        Some(x) => x.as_i64().unwrap_or(0),
        None => 0,
    }
}

fn unit_state(u: &Value, passenger: Option<&Value>, effects: Option<&Value>, facing: Option<&Value>, size: i32, rep: &mut LoadReport) -> Option<UnitState> {
    let tid = i(u, "UnitType") as i32;
    let t = match unit_type(tid) {
        Some(t) => t,
        None => {
            rep.drop(format!("unit type {tid}"));
            return None;
        }
    };
    if UnitType::from_repr(tid as i8).is_none() {
        rep.sub(format!("unit type {tid} as {t:?}"));
    }
    let (x, y) = (i(u, "cx") as i32, i(u, "cy") as i32);
    let (hx, hy) = (i(u, "hx") as i32, i(u, "hy") as i32);
    let mut s = UnitState {
        owner: i(u, "Owner") as i32,
        unit_type: t,
        health: i(u, "Health") as f32 / 10.0,
        veteran: i(u, "PromotionLevel") > 0,
        kills: i(u, "Experience") as i32,
        coords: Coords::from_xy(x, y, size),
        prev_coords: Coords::invalid(),
        home_coords: if hx >= 0 && hy >= 0 && hx < size && hy < size { Some(Coords::from_xy(hx, hy, size)) } else { None },
        flipped: i(u, "Flipped") != 0,
        created_turn: i(u, "CreatedTurn") as i32,
        moved: i(u, "Moved") != 0,
        attacked: i(u, "Attacked") != 0,
        uid: i(u, "Id"),
        ..Default::default()
    };
    // facing (pf-port SAVE-UNIT-FACING): UnitDirection byte 2 is 0..7 = NW, W, SW, S, SE, E, NE, N; Polyfish stores it + 1 (0 = unknown)
    if let Some(d) = facing.and_then(|f| f.get(2)).and_then(|b| b.as_i64()) {
        if d < 8 { s.direction = d as i32 + 1; }
    }
    if let Some(p) = passenger {
        let pid = i(p, "UnitType") as i32;
        match unit_type(pid) {
            Some(pt) => s.passenger_type = Some(pt),
            None => rep.drop(format!("passenger type {pid}")),
        }
        s.veteran = i(p, "PromotionLevel") > 0; // the boat record always shows 0; the passenger keeps the level
    }
    if let Some(Value::Array(es)) = effects {
        for e in es {
            let e = e.as_i64().unwrap_or(-1);
            match enum_of::<UnitEffect>(e) {
                Some(ef) if e >= 0 => {
                    s.effects.insert(ef);
                }
                _ => rep.drop(format!("unit effect {e}")),
            }
        }
    }
    Some(s)
}

/// Build a GameState from save JSON. `which` is "current" (the checkpoint) or "initial" (turn 0).
/// `current_player`: whose turn it is (the save doesn't say directly; the replay reads it from the log).
/// A structure's Polyfish level from the save's ImprovementData.Level.
/// v123 (ledger FUNGI-GROWTH, pf-port): the save's Fungi levels 0/1 are Polyfish's 1/2.
pub fn structure_level(s: StructureType, save_level: i32) -> i32 {
    save_level + if s == StructureType::Fungi { 1 } else { 0 }
}

pub fn load(d: &Value, which: &str, current_player: i32) -> Result<(Game, LoadReport), String> {
    let tiles = d.get(format!("{which}Tiles")).and_then(|v| v.as_array()).ok_or("no tiles")?;
    let players = d.get(format!("{which}Players")).and_then(|v| v.as_array()).ok_or("no players")?;
    let size = d.get("mapWidth").and_then(|v| v.as_i64()).ok_or("no mapWidth")? as i32;
    if d.get("mapHeight").and_then(|v| v.as_i64()) != Some(size as i64) {
        return Err("map not square".into());
    }
    let mut rep = LoadReport::default();
    let mut st = GameState::default();
    let hdr = d.pointer("/header/MapHeaderInput").cloned().unwrap_or(Value::Null);
    st.settings.size = size;
    st.settings.tile_count = size * size;
    st.settings.turn = d.get("currentTurn").and_then(|v| v.as_i64()).unwrap_or(0) as i32;
    st.settings.version = 115; // newest rules Polyfish knows; the saves are v123
    st.settings.seed = i(&hdr, "Seed");
    st.initial_seed = st.settings.seed;
    st.settings.win_by_capital = i(&hdr, "WinByCapital") != 0;
    st.settings.max_turns = 10_000; // saves are open-ended Domination; don't end the game on a turn count
    st.settings._max_tribe_count = players.iter().map(|p| i(p, "PlayerId") as i32).max().unwrap_or(0);
    st.settings.current_player_turn_id = current_player;
    st.settings._fow = true;

    // Tribes
    for p in players {
        let id = i(p, "PlayerId") as i32;
        let tribe = TribeType::from_repr(i(p, "Tribe") as i8).unwrap_or_else(|| {
            rep.drop(format!("tribe {}", i(p, "Tribe")));
            TribeType::None
        });
        let mut t = TribeState { id, tribe_type: tribe, ..Default::default() };
        t.username = p.get("Name").and_then(|v| v.as_str()).unwrap_or("").to_string();
        t.bot = i(p, "AutoPlay") != 0;
        t.handicap = i(p, "DifficultyHandicap") as i32; // pf-port ECON-BOT-BONUS
        t.stars = i(p, "Currency") as i32;
        t.score = i(p, "Score") as i32;
        t.kills = i(p, "Kills") as i32;
        t.casualties = i(p, "Losses") as i32;
        let st_xy = p.get("StartTile").and_then(|v| v.as_array());
        if let Some(a) = st_xy {
            let (x, y) = (a[0].as_i64().unwrap_or(-1) as i32, a[1].as_i64().unwrap_or(-1) as i32);
            t.starting_tile_coords = Coords::from_xy(x, y, size);
        }
        for tv in p.get("AvailableTech").and_then(|v| v.as_array()).into_iter().flatten() {
            let k = tv.as_i64().unwrap_or(-99);
            match TechnologyType::from_repr(k as i8) {
                Some(tt) if k >= 0 => t.tech_vanilla.push(TechnologyState { tech_type: tt, discovered: true, discovered_turn: 0 }),
                _ => rep.drop(format!("tech {k}")),
            }
        }
        for e in p.get("Encountered").and_then(|v| v.as_array()).into_iter().flatten() {
            if let Some(k) = e.as_i64() {
                if k as i32 != id && k > 0 {
                    t.known_players.insert(k as i32);
                }
            }
        }
        for e in p.get("UniqueImprovements").and_then(|v| v.as_array()).into_iter().flatten() {
            let k = e.as_i64().unwrap_or(0);
            match StructureType::from_repr(k as i8) {
                Some(s) if k > 0 && k < 128 => {
                    t.built_unique_improvements.insert(s);
                }
                _ => rep.drop(format!("unique improvement {k}")),
            }
        }
        for r in p.get("Diplomacy").and_then(|v| v.as_array()).into_iter().flatten() {
            let rel = DiplomacyRelationState {
                state: i(r, "RelationState") as i32, // save: 0 neutral, 1 peace, 3 war; Polyfish reads 1 as peace (pf-port keeps 3 for embassy income)
                last_attack_turn: i(r, "LastAttackTurn") as i32,
                embassy_level: i(r, "EmbassyLevel") as i32,
                last_peace_broken_turn: i(r, "LastPeaceBrokenTurn") as i32,
                first_meet: i(r, "FirstMeet") as i32,
                embassy_build_turn: i(r, "EmbassyBuildTurn") as i32,
                previous_attack_turn: i(r, "PreviousAttackTurn") as i32,
                has_offered_peace: false, // pending offers: DiplomacyMessages below
            };
            t.relations.insert(i(r, "PlayerId") as i32, rel);
        }
        // DiplomacyMessages: [1, sender] = a peace offer from sender still waiting for this tribe's reply
        // (14 in the saves, all type 1; each is answered by a logged action 28 after the save).
        for m in p.get("DiplomacyMessages").and_then(|v| v.as_array()).into_iter().flatten() {
            let m: Vec<i64> = m.as_array().into_iter().flatten().filter_map(|x| x.as_i64()).collect();
            match m.as_slice() {
                [1, sender] => t.relations.entry(*sender as i32).or_default().has_offered_peace = true,
                _ => rep.drop(format!("diplomacy message {m:?}")),
            }
        }
        if i(p, "DestroyedTurn") > 0 || i(p, "DestroyedByTribe") > 0 {
            t.killed_turn = i(p, "DestroyedTurn").max(1) as i32;
            t.killer_id = i(p, "DestroyedByTribe") as i32;
        }
        st.tribes.insert(id, t);
    }
    embassies_to_builder_side(&mut st);

    // Tiles, structures, resources, cities, units
    for (y, row) in tiles.iter().enumerate() {
        for (x, tv) in row.as_array().ok_or("bad tile row")?.iter().enumerate() {
            let c = Coords::from_xy(x as i32, y as i32, size);
            let terr = i(tv, "Terrain");
            let mut t = TileState { coords: c, ..Default::default() };
            t.terrain_type = enum_of::<TerrainType>(terr).unwrap_or_else(|| {
                rep.drop(format!("terrain {terr}"));
                TerrainType::Field
            });
            let cl = i(tv, "Climate");
            t.climate = TribeType::from_repr(cl as i8).unwrap_or_else(|| {
                rep.drop(format!("climate {cl}"));
                TribeType::Nature
            });
            t.owner = i(tv, "Owner") as i32;
            t.capital_of = i(tv, "Capital") as i32;
            t.has_road = i(tv, "HasRoad") != 0;
            t.has_route = i(tv, "HasWaterRoute") != 0;
            t.skin_type = i(tv, "TileSkin") as i32;
            if let Some(Value::Array(cc)) = tv.get("CapitalCoordinates") {
                let (cx, cy) = (cc[0].as_i64().unwrap_or(-1), cc[1].as_i64().unwrap_or(-1));
                if t.owner != 0 && cx >= 0 && cy >= 0 {
                    t.ruling_city_coords = Some(Coords::from_xy(cx as i32, cy as i32, size));
                }
            }
            for e in tv.get("PlayerVisibility").and_then(|v| v.as_array()).into_iter().flatten() {
                if let Some(k) = e.as_i64() {
                    t.explorers.insert(k as i32);
                }
            }
            if i(tv, "FloodedFlag") != 0 {
                match i(tv, "FloodedValue") {
                    1 => {
                        t.effects.insert(TileEffect::Flooded);
                    }
                    4 => {
                        t.effects.insert(TileEffect::Algae);
                    }
                    v => rep.drop(format!("flood value {v}")),
                }
            }
            if tv.get("ResourceExists").map_or(false, |v| v.as_bool().unwrap_or(false)) {
                let r = i(tv, "ResourceType");
                match enum_of::<ResourceType>(r) {
                    Some(rt) if r > 0 => {
                        st.resources.insert(c.idx, Some(ResourceState { resource_type: rt }));
                    }
                    _ => rep.drop(format!("resource {r}")),
                }
            }
            if tv.get("ImprovementExists").map_or(false, |v| v.as_bool().unwrap_or(false)) {
                let k = i(tv, "ImprovementType");
                let data = tv.get("ImprovementData").cloned().unwrap_or(Value::Null);
                match StructureType::from_repr(k as i8) {
                    Some(s) if k > 0 && k < 128 => {
                        let level = structure_level(s, i(&data, "Level") as i32);
                        st.structures.insert(c.idx, Some(StructureState { structure_type: s, level, founded: i(&data, "FoundedTurn") as i32 }));
                        if s == StructureType::Village && t.owner != 0 {
                            let mut rewards = Vec::new();
                            for rv in data.get("CityRewards").and_then(|v| v.as_array()).into_iter().flatten() {
                                let k = rv.as_i64().unwrap_or(-1);
                                match CityRewardType::from_repr(k as i8) {
                                    Some(r) if k > 0 => rewards.push(r),
                                    _ => rep.drop(format!("city reward {k}")),
                                }
                            }
                            let city = CityState {
                                owner: t.owner,
                                name: data.get("CityName").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                                idx: c.idx,
                                population: i(&data, "TotalPopulation") as i32,
                                progress: i(&data, "CurrentPopulation") as i32,
                                border_size: i(&data, "BorderSize") as i32,
                                connected_to_capital: i(&data, "ConnectedPlayerCapital") != 0,
                                level: i(&data, "Level") as i32,
                                // Polyfish's production is the city's star income before bonuses (= level, as mapgen sets it).
                                // The save's "Production" field is something else (1 or 2 at every level; meaning unknown).
                                production: i(&data, "Level") as i32,
                                rewards,
                                _territory: Vec::new(),
                            };
                            t.ruling_city_coords = Some(c);
                            match st.tribes.get_mut(&t.owner) {
                                Some(tr) => tr.cities.push(city),
                                None => rep.drop(format!("city of missing player {}", t.owner)),
                            }
                        }
                    }
                    _ => rep.drop(format!("improvement {k}")),
                }
            }
            if let Some(u) = tv.get("Unit").filter(|u| !u.is_null()) {
                if let Some(us) = unit_state(u, tv.get("PassengerUnit").filter(|p| !p.is_null()), tv.get("UnitEffects"), tv.get("UnitDirection"), size, &mut rep) {
                    if i(u, "FollowerUnitId") != 0 || i(u, "LeaderUnitId") != 0 {
                        rep.drop("centipede leader/follower links".into());
                    }
                    t._unit_owner_id = Some(us.owner);
                    match st.tribes.get_mut(&us.owner) {
                        Some(tr) => tr.units.push(us),
                        None => rep.drop(format!("unit of missing player {}", us.owner)),
                    }
                }
            }
            st.tiles.insert(c.idx, t);
        }
    }
    let mut game = Game { state: st };
    game.post_load();
    Ok((game, rep))
}

/// Unit ids present in a state (for checks).
/// EMBASSY-INCOME-NEUTRAL: the save keeps an embassy on the host's Diplomacy record for the builder (EmbassyLevel);
/// Polyfish keeps it on the builder's record for the host (EstablishEmbassyMove, get_embassy_cost).
pub fn embassies_to_builder_side(st: &mut GameState) {
    let hosted: Vec<(i32, i32, i32)> = st.tribes.iter()
        .flat_map(|(&host, t)| t.relations.iter().filter(|(_, r)| r.embassy_level > 0).map(move |(&b, r)| (b, host, r.embassy_level)))
        .collect();
    for t in st.tribes.values_mut() {
        for r in t.relations.values_mut() {
            r.embassy_level = 0;
        }
    }
    for (builder, host, level) in hosted {
        if let Some(t) = st.tribes.get_mut(&builder) {
            t.relations.entry(host).or_default().embassy_level = level;
        }
    }
}

pub fn uids(state: &GameState) -> HashSet<i64> {
    state.tribes.values().flat_map(|t| t.units.iter().map(|u| u.uid)).collect()
}
