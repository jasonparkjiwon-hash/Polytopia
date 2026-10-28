//! Unseen-opponent sampler (win-pct-2, belief mode): `belief::sample_belief` draws the hidden MAP; this completes the hidden
//! OPPONENTS. A player's view has no past sightings in a save, so the opposing tribes' cities and armies beyond what is visible
//! now are drawn from a bank of real tribe profiles (cities with levels, units with hp, stars) taken from other games:
//! profile weight = same bot level, same tribe, turn distance, and (for tribes the player has met, whose score is on the
//! scoreboard) score distance. Observed facts stay exact: visible cities and units are never touched, new ones only go on
//! tiles the player has not explored. The tribe's stars are replaced by the profile's (they are not observable).
//! Tech sets are NOT resampled (they stay as in the save: a tech count is cheap to learn in play; see win-pct.md).
use crate::belief::Rng;
use crate::coords::Coords;
use crate::functions as F;
use crate::game::Game;
use crate::states::{CityState, StructureState, UnitState};
use crate::types::*;
use serde::Deserialize;

/// One tribe at one checkpoint of a real game.
#[derive(Deserialize, serde::Serialize, Clone, Debug)]
pub struct Profile {
    pub g: String,                // game id prefix
    pub t: i32,                   // turn
    pub tr: String,               // tribe type name
    pub h: i32,                   // handicap (bot level)
    pub bot: bool,
    pub sc: i32,                  // score
    pub st: i32,                  // stars
    pub cities: Vec<(i32, i32)>,  // (level, population)
    pub units: Vec<(i8, f32)>,    // (unit type, hp / max hp)
}

#[derive(Default, Clone)]
pub struct Bank(pub Vec<Profile>);

impl Bank {
    pub fn from_file(path: &str) -> Result<Bank, String> {
        let v: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(path).map_err(|e| format!("{path}: {e}"))?).map_err(|e| format!("{path}: {e}"))?;
        let p = serde_json::from_value(v.get("profiles").cloned().unwrap_or_default()).map_err(|e| format!("{path}: {e}"))?;
        Ok(Bank(p))
    }
}

#[derive(Clone, Debug)]
pub struct Opts {
    /// condition the profile on the tribe's score when pov has met it (the scoreboard shows it)
    pub use_score: bool,
    /// condition on the score of every opposing tribe, met or not (the save's player records; an upper bound for what a scoreboard gives)
    pub score_all: bool,
    /// diagnostics: take the TRUE number of cities / of units of each opposing tribe (placement and composition still sampled)
    pub oracle_cities: bool,
    pub oracle_units: bool,
    /// profiles of these games are never drawn (the test game, held-out games)
    pub exclude: Vec<String>,
}

/// The profile of tribe `id` in `g` (also used to build the bank).
pub fn profile_of(g: &Game, id: i32, game: &str) -> Profile {
    let t = &g.state.tribes[&id];
    Profile {
        g: game.to_string(), t: g.state.settings.turn, tr: format!("{:?}", t.tribe_type), h: t.handicap, bot: t.bot, sc: t.score, st: t.stars,
        cities: t.cities.iter().map(|c| (c.level, c.population)).collect(),
        units: t.units.iter().filter(|u| u.unit_type != UnitType::Segment).map(|u| {
            let ut = u.passenger_type.unwrap_or(u.unit_type);
            (ut as i8, (u.health / F::get_unit_max_health(u).max(1.0)).clamp(0.05, 1.0))
        }).collect(),
    }
}

fn cheb(n: i32, a: i32, b: i32) -> i32 { ((a % n) - (b % n)).abs().max((a / n - b / n).abs()) }

fn landable(ut: UnitType) -> bool {
    !(matches!(ut, UnitType::None | UnitType::Segment | UnitType::LivingIsland | UnitType::InsectEgg | UnitType::DragonEgg) || ut.is_naval() || ut.is_aquatic())
}

/// Complete the hidden part of the opposing tribes in `v` (a `belief::sample_belief` result for `pov`); `truth` is the full-information
/// game (only used for the oracle diagnostics). Returns (cities added, units added).
pub fn complete(v: &mut Game, truth: &Game, pov: i32, bank: &Bank, o: &Opts, rng: &mut Rng) -> (usize, usize) {
    let n = v.state.settings.size;
    let turn = v.state.settings.turn;
    let known: Vec<i32> = v.state.tribes.get(&pov).map(|t| t.known_players.iter().copied().collect()).unwrap_or_default();
    let hidden = |v: &Game, i: i32| v.state.tiles.get(&i).map_or(false, |t| !t.explorers.contains(&pov));
    let ids: Vec<i32> = v.state.tribes.keys().copied().filter(|&i| i != pov).collect();
    let (mut add_c, mut add_u) = (0, 0);
    for id in ids {
        let (alive, bot, h, tr, score) = { let t = &v.state.tribes[&id]; (t.killed_turn <= 0 && t.resigned_turn <= 0 && !t.cities.is_empty(), t.bot, t.handicap, format!("{:?}", t.tribe_type), t.score) };
        if !alive { continue; }
        let seen_c = v.state.tribes[&id].cities.len();
        let seen_u = v.state.tribes[&id].units.len();
        let met = known.contains(&id);
        // 1. a profile
        let w: Vec<f64> = bank.0.iter().map(|p| {
            if o.exclude.iter().any(|g| *g == p.g) || p.bot != bot { return 0.0; }
            let dt = (p.t - turn) as f64 / 1.5; let mut x = (-dt * dt / 2.0).exp();
            x *= if p.h == h { 1.0 } else { 0.25 };
            x *= if p.tr == tr { 1.5 } else { 1.0 };
            if o.use_score && (met || o.score_all) { let d = (p.sc - score) as f64 / (0.2 * (score.max(40)) as f64); x *= (-d * d / 2.0).exp(); }
            if o.oracle_cities { let nc = truth.state.tribes[&id].cities.len(); x *= if p.cities.len() == nc { 1.0 } else { 0.05 }; }
            else if p.cities.len() < seen_c { x *= 0.05; }
            x
        }).collect();
        let tot: f64 = w.iter().sum();
        if tot <= 0.0 { continue; }
        let p = &bank.0[rng.pick(&w)];
        // 2. cities: levels of the profile, the biggest already seen
        let want_c = if o.oracle_cities { truth.state.tribes[&id].cities.len() } else { p.cities.len() };
        let mut lv: Vec<i32> = if o.oracle_cities { truth.state.tribes[&id].cities.iter().map(|c| c.level).collect() } else { p.cities.iter().map(|c| c.0).collect() };
        lv.sort_by(|a, b| b.cmp(a));
        let mut centres: Vec<i32> = v.state.tribes[&id].cities.iter().map(|c| c.idx).collect();
        let all_cities: Vec<i32> = v.state.tribes.values().flat_map(|t| t.cities.iter().map(|c| c.idx)).collect();
        for k in seen_c..want_c {
            let level = lv.get(k).copied().unwrap_or(1).max(1);
            let cand: Vec<(i32, f64)> = (0..n * n).filter_map(|i| {
                let t = v.state.tiles.get(&i)?;
                if !hidden(v, i) || t.owner != 0 || matches!(t.terrain_type, TerrainType::Water | TerrainType::Ocean | TerrainType::Mountain) { return None; }
                if all_cities.iter().chain(centres.iter()).any(|&c| cheb(n, c, i) < 3) { return None; }
                let d = centres.iter().map(|&c| cheb(n, c, i)).min()?;
                if d > 6 { return None; }
                let vil = v.state.structures.get(&i).and_then(|s| s.as_ref()).map_or(false, |s| s.structure_type == StructureType::Village);
                Some((i, (-(d as f64) / 2.5).exp() * if vil { 3.0 } else { 1.0 }))
            }).collect();
            if cand.is_empty() { break; }
            let c = cand[rng.pick(&cand.iter().map(|x| x.1).collect::<Vec<_>>())].0;
            let cc = Coords::from_index(c, n);
            for dy in -1..=1 { for dx in -1..=1 {
                if let Some(t) = v.state.tiles.get_mut(&((cc.y + dy) * n + cc.x + dx)) { if t.owner == 0 { t.owner = id; t.ruling_city_coords = Some(cc); } }
            } }
            v.state.structures.insert(c, Some(StructureState { structure_type: StructureType::Village, level: 1, founded: 0 }));
            if let Some(tr) = v.state.tribes.get_mut(&id) {
                tr.cities.push(CityState { owner: id, idx: c, level, production: level, population: 0, border_size: 1, connected_to_capital: true, ..Default::default() });
            }
            centres.push(c);
            add_c += 1;
        }
        // 3. units
        let want_u = if o.oracle_units { truth.state.tribes[&id].units.len() } else { p.units.len() };
        let pool: Vec<(i8, f32)> = if o.oracle_units {
            truth.state.tribes[&id].units.iter().map(|u| (u.passenger_type.unwrap_or(u.unit_type) as i8, (u.health / F::get_unit_max_health(u).max(1.0)).clamp(0.05, 1.0))).collect()
        } else { p.units.clone() };
        let mut order: Vec<usize> = (0..pool.len()).collect();
        for j in (1..order.len()).rev() { order.swap(j, rng.below(j + 1)); }
        let mut taken = 0;
        let occupied: Vec<i32> = v.state.tribes.values().flat_map(|t| t.units.iter().map(|u| u.coords.idx)).collect();
        let mut occ = occupied;
        for &oi in &order {
            if seen_u + taken >= want_u { break; }
            let (ut_i, frac) = pool[oi];
            let ut = UnitType::from(ut_i as i32);
            if !landable(ut) { continue; }
            let cand: Vec<(i32, f64)> = (0..n * n).filter_map(|i| {
                let t = v.state.tiles.get(&i)?;
                if !hidden(v, i) || occ.contains(&i) || matches!(t.terrain_type, TerrainType::Water | TerrainType::Ocean | TerrainType::Mountain) { return None; }
                let d = centres.iter().map(|&c| cheb(n, c, i)).min()?;
                if d > 4 { return None; }
                Some((i, (-(d as f64) / 1.5).exp() * if t.owner == id { 2.0 } else { 1.0 }))
            }).collect();
            if cand.is_empty() { break; }
            let at = cand[rng.pick(&cand.iter().map(|x| x.1).collect::<Vec<_>>())].0;
            let home = centres.iter().min_by_key(|&&c| cheb(n, c, at)).copied().unwrap_or(at);
            let (cc, hc) = (Coords::from_index(at, n), Coords::from_index(home, n));
            let mut u = UnitState { owner: id, unit_type: ut, coords: cc, prev_coords: cc, home_coords: Some(hc), health: 10.0, created_turn: turn - 1, ..Default::default() };
            u.health = (F::get_unit_max_health(&u) * frac).max(1.0);
            if let Some(tr) = v.state.tribes.get_mut(&id) { tr.units.push(u); }
            occ.push(at);
            taken += 1;
            add_u += 1;
        }
        if std::env::var("UNSEEN_DEBUG").is_ok() { eprintln!("tribe {id} seen {seen_c}c/{seen_u}u want {want_c}c/{want_u}u placed {}c {}u (profile {} t{} sc{} vs {score})", centres.len() - seen_c, taken, p.g, p.t, p.sc); }
        // 4. stars are not observable: the profile's
        if !o.oracle_cities { if let Some(tr) = v.state.tribes.get_mut(&id) { tr.stars = p.st; } }
    }
    (add_c, add_u)
}
