//! bot-policy: a model of the built-in bots' move choice (Phase 6 groundwork, used for opponents in playouts).
//!
//! Every legal move gets a sparse feature vector (`features`), computed from the state before the move and, for
//! moves with an immediate outcome, from the forward model itself (the move is simulated on a clone: stars, units
//! killed, HP lost, population). Two scorers rank the moves:
//! - v1 (`score_v1`): hand rules from data/bot_rules.json (captures, then a kill, least return damage, most
//!   expensive target; train by turn bucket; research opener; walk toward villages);
//! - v2 (`Weights`): a linear score over the same features, fitted by tools/bot_policy.py (conditional logit) and
//!   read from data/bot_policy.json.
//! `choose` samples a move with softmax probabilities (deterministic at temperature 0).
//! No rule code here: everything goes through Polyfish's move generation and `simulate_move`.
use crate::functions::*;
use crate::moves::Move;
use crate::settings::units::get_unit_setting;
use crate::types::*;
use crate::{Game, GameState};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::Mutex;

/// Move classes, the first feature of every move.
pub const KINDS: [&str; 20] = [
    "EndTurn", "Step", "Attack", "Train", "Upgrade", "Research", "Build", "Harvest", "CapVillage", "CapCity",
    "CapRuin", "CapOther", "Reward", "Convert", "Recover", "HealOthers", "Promote", "Diplomacy", "Forest", "Ability",
];

/// Turn bucket used for kind x time crossings (sim-dist: trains rise with time, Warrior share falls).
pub fn bucket(turn: i32) -> usize {
    match turn { t if t < 5 => 0, t if t < 10 => 1, t if t < 20 => 2, _ => 3 }
}

static COLS: Mutex<Option<(Vec<String>, HashMap<String, u16>)>> = Mutex::new(None);

/// Column id of a feature name (a process-wide table; `col_names` lists it).
pub fn col(name: &str) -> u16 {
    let mut g = COLS.lock().unwrap();
    let (v, m) = g.get_or_insert_with(|| (Vec::new(), HashMap::new()));
    if let Some(&k) = m.get(name) { return k; }
    let k = v.len() as u16;
    v.push(name.to_string());
    m.insert(name.to_string(), k);
    k
}

pub fn col_names() -> Vec<String> {
    COLS.lock().unwrap().as_ref().map(|(v, _)| v.clone()).unwrap_or_default()
}

/// One legal move, described for the policy.
#[derive(Debug, Clone)]
pub struct Cand {
    pub kind: usize,
    pub src: i32,
    pub tgt: i32,
    pub sub: i32, // unit / structure / tech / reward type id, 0 if none
    pub f: Vec<(u16, f32)>,
}

impl Cand {
    pub fn get(&self, name: &str) -> f32 {
        let c = col(name);
        self.f.iter().find(|(k, _)| *k == c).map_or(0.0, |(_, v)| *v)
    }
}

/// Things computed once per decision.
pub struct Ctx {
    pub me: i32,
    pub turn: i32,
    pub bucket: usize,
    pub targets: Vec<i32>,       // capturable: villages, enemy cities, ruins the mover has explored
    pub enemies: Vec<(i32, f32)>, // enemy unit tiles and their unit price
    pub capital: Option<i32>,
    pub opener: Vec<TechnologyType>,
    pub crazy: bool,
    pub stars: i32,
}

fn dist(s: &GameState, a: i32, b: i32) -> i32 { get_chebyshev_distance(a, b, s.settings.size) }

fn nearest(s: &GameState, from: i32, set: &[i32]) -> i32 {
    set.iter().map(|&t| dist(s, from, t)).min().unwrap_or(30).min(30)
}

fn explored(s: &GameState, idx: i32, me: i32) -> bool {
    s.tiles.get(&idx).map_or(true, |t| t.explorers.contains(&me))
}

/// BOT-RESEARCH-OPENER (tools/bot_rules.py `opener`), from the resources within 2 of the capital.
fn opener(s: &GameState, me: i32, cap: Option<i32>) -> Vec<TechnologyType> {
    use TechnologyType as T;
    let Some(tr) = s.tribes.get(&me) else { return vec![] };
    match tr.tribe_type {
        TribeType::Aquarion => return vec![T::AquaFishing],
        TribeType::Polaris => return vec![T::IceFishing, T::Sledding],
        _ => {}
    }
    let Some(c) = cap else { return vec![] };
    let (mut water, mut metal, mut fruit, mut game) = (0, 0, 0, 0);
    for k in get_square_indices(c, 2, s.settings.size) {
        if let Some(t) = s.tiles.get(&k) { if matches!(t.terrain_type, TerrainType::Water | TerrainType::Ocean) { water += 1; } }
        match get_resource_at(s, k) {
            Some(ResourceType::Metal) => metal += 1,
            Some(ResourceType::Fruit) => fruit += 1,
            Some(ResourceType::Game) => game += 1,
            _ => {}
        }
    }
    let has = |t: T| crate::settings::technology::has_tech_for_tribe(tr, t);
    let mine = has(T::Climbing) || has(T::Smithery);
    if mine && (metal >= 2 || metal >= 1 && water == 0) { return vec![T::Mining]; }
    if water > 0 && !has(T::Fishing) { return vec![T::Fishing]; }
    if fruit >= 2 && !has(T::Organization) { return vec![T::Organization]; }
    if game >= 2 && !has(T::Hunting) { return vec![T::Hunting]; }
    if metal > 0 && !mine { return vec![T::Climbing]; }
    vec![T::Riding]
}

pub fn context(s: &GameState) -> Ctx {
    let me = s.settings.current_player_turn_id;
    let mut targets = Vec::new();
    for (&k, st) in s.structures.iter() {
        let Some(st) = st else { continue };
        if !explored(s, k, me) { continue; }
        let ok = match st.structure_type {
            StructureType::Village => get_city_at(s, k).map_or(true, |c| c.owner != me && is_enemy(s, me, c.owner)),
            StructureType::Ruin => true,
            _ => false,
        };
        if ok { targets.push(k); }
    }
    for tr in s.tribes.values() {
        if tr.id == me || !is_enemy(s, me, tr.id) { continue; }
        for c in &tr.cities { if explored(s, c.idx, me) && !targets.contains(&c.idx) { targets.push(c.idx); } }
    }
    let mut enemies = Vec::new();
    for tr in s.tribes.values() {
        if tr.id == me || !is_enemy(s, me, tr.id) { continue; }
        for u in &tr.units { enemies.push((u.coords.idx, get_unit_setting(u.unit_type).cost.max(0) as f32)); }
    }
    let capital = get_capital_city(s, me).map(|c| c.idx);
    let tr = s.tribes.get(&me);
    Ctx {
        me, turn: s.settings.turn, bucket: bucket(s.settings.turn), targets, enemies, capital,
        opener: opener(s, me, capital),
        crazy: tr.map_or(false, |t| t.handicap >= 4), // DifficultyHandicap: Hard 2, Crazy 4 in the saves (1 = one game, easier)
        stars: tr.map_or(0, |t| t.stars),
    }
}

fn kind_of(s: &GameState, mv: &dyn Move) -> usize {
    let k = crate::api::kind(mv);
    let key = mv.serialize();
    let tile = key.get("src").and_then(|v| v.as_i64()).unwrap_or(-1) as i32;
    match k.as_str() {
        "EndTurn" | "Resign" => 0,
        "Step" => 1,
        "Attack" => 2,
        "Summon" => 3,
        "Upgrade" => 4,
        "Research" => 5,
        "Build" => 6,
        "Harvest" => 7,
        "Capture" => {
            if get_city_at(s, tile).is_some() { 9 }
            else {
                match get_structure_type_at(s, tile) {
                    Some(StructureType::Village) => 8,
                    Some(StructureType::Ruin) => 10,
                    _ => 11,
                }
            }
        }
        "Reward" => 12,
        "Convert" => 13,
        "Recover" => 14,
        "HealOthers" => 15,
        "Promote" => 16,
        "BreakPeace" | "PeaceRequestResponse" | "EstablishEmbassy" | "PeaceTreaty" | "DestroyEmbassy" => 17,
        "BurnForest" | "ClearForest" | "GrowForest" => 18,
        _ => 19,
    }
}

fn sum_hp(s: &GameState, pred: impl Fn(i32) -> bool) -> (f32, i32) {
    let (mut hp, mut n) = (0.0, 0);
    for tr in s.tribes.values() {
        if !pred(tr.id) { continue; }
        for u in &tr.units { hp += u.health; n += 1; }
    }
    (hp, n)
}

fn pop(s: &GameState, me: i32) -> i32 {
    s.tribes.get(&me).map_or(0, |t| t.cities.iter().map(|c| c.population + 3 * c.level).sum())
}

/// Features of every legal move. `sim` is a clone of the game used for forward-model outcomes (simulate_move
/// and undo; no tiles get explored).
pub fn features(g: &Game, legal: &[Box<dyn Move>]) -> (Ctx, Vec<Cand>) {
    let s = &g.state;
    let cx = context(s);
    let me = cx.me;
    let mut sim = crate::api::clone(g);
    let base_stars = cx.stars;
    let (ehp0, en0) = sum_hp(s, |p| p != me && is_enemy(s, me, p));
    let (ohp0, on0) = sum_hp(s, |p| p == me);
    let pop0 = pop(s, me);
    let ncity0 = s.tribes.get(&me).map_or(0, |t| t.cities.len());
    // turn order: own units that haven't acted yet, in the tribe's unit order; moves already made this turn
    let ready: Vec<i32> = s.tribes.get(&me).map(|t| t.units.iter().filter(|u| !u.moved && !u.attacked).map(|u| u.coords.idx).collect()).unwrap_or_default();
    let first_move = s.settings._recent_moves.is_empty();
    let mut out = Vec::with_capacity(legal.len());
    for mv in legal {
        let kind = kind_of(s, mv.as_ref());
        let key = mv.serialize();
        let src = mv.source_idx().map(|x| x as i32).ok().or_else(|| key.get("src").and_then(|v| v.as_i64()).map(|x| x as i32)).unwrap_or(-1);
        let tgt = mv.target_idx().map(|x| x as i32).ok().or_else(|| key.get("target").and_then(|v| v.as_i64()).map(|x| x as i32)).unwrap_or(-1);
        let sub = mv.unit_type().map(|t| t as i32)
            .or_else(|_| mv.structure_type().map(|t| t as i32))
            .or_else(|_| mv.tech_type().map(|t| t as i32))
            .or_else(|_| mv.reward_type().map(|t| t as i32)).unwrap_or(0);
        let mut f: Vec<(u16, f32)> = Vec::new();
        let mut put = |name: &str, v: f32| { if v != 0.0 { f.push((col(name), v)); } };
        let kn = KINDS[kind];
        put(&format!("k:{kn}"), 1.0);
        put(&format!("k:{kn}|t{}", cx.bucket), 1.0);
        if cx.crazy { put(&format!("k:{kn}|crazy"), 1.0); }
        if first_move { put(&format!("k:{kn}|first"), 1.0); }
        if ready.is_empty() { put(&format!("k:{kn}|allacted"), 1.0); }
        if let Some(r) = ready.iter().position(|&k| k == src).filter(|_| matches!(kind, 1 | 2 | 13 | 19)) {
            if r == 0 { put("ord:first", 1.0); }
            if r + 1 == ready.len() { put("ord:last", 1.0); }
            put("ord:rank", (r as f32 / ready.len().max(1) as f32));
        }
        let unit = if src >= 0 { get_unit_at(s, src).filter(|u| u.owner == me) } else { None };
        let in_own_city = |i: i32| get_city_at(s, i).map_or(false, |c| c.owner == me);
        match kind {
            1 => {
                // Step: toward capturable targets / enemies, into fog, onto a target
                let u = unit;
                let on_target = cx.targets.contains(&tgt);
                put("st:ontarget", on_target as i32 as f32);
                if !on_target {
                    let dv = (nearest(s, tgt, &cx.targets) - nearest(s, src, &cx.targets)) as f32;
                    put("st:dtarget", dv);
                }
                let ep: Vec<i32> = cx.enemies.iter().map(|e| e.0).collect();
                let de0 = nearest(s, src, &ep);
                if de0 <= 6 { put("st:denemy", (nearest(s, tgt, &ep) - de0) as f32); }
                let adj = ep.iter().filter(|&&e| dist(s, e, tgt) == 1).count();
                put("st:adjenemy", adj as f32);
                let r = if s.tiles.get(&tgt).map_or(false, |t| t.terrain_type == TerrainType::Mountain) { 2 } else { 1 };
                let fog = get_square_indices(tgt, r, s.settings.size).into_iter().filter(|&k| !explored(s, k, me)).count();
                put("st:fog", fog as f32);
                put("st:leavecity", in_own_city(src) as i32 as f32);
                put("st:intocity", in_own_city(tgt) as i32 as f32);
                if let Some(c) = cx.capital { put("st:dcap", (dist(s, tgt, c) - dist(s, src, c)) as f32); }
                if let Some(u) = u {
                    let hpf = u.health / get_unit_max_health(u).max(1.0);
                    if hpf < 0.5 { put("st:lowhp", 1.0); put("st:lowhp_dcap", cx.capital.map_or(0, |c| dist(s, tgt, c) - dist(s, src, c)) as f32); }
                    if u.unit_type == UnitType::Defender { put("st:defender", 1.0); }
                    if u.attacked { put("st:afterattack", 1.0); }
                    let water = s.tiles.get(&tgt).map_or(false, |t| matches!(t.terrain_type, TerrainType::Water | TerrainType::Ocean));
                    if water && !u.unit_type.is_naval() && !u.unit_type.is_aquatic() { put("st:embark", 1.0); }
                }
            }
            2 | 13 => {
                // Attack / Convert: combat preview (sim-dist rules) + who stands where
                if let Some(p) = calculate_combat_preview(s, src, tgt) {
                    put("atk:kill", p.defender_dies as i32 as f32);
                    put("atk:dmg", p.damage_to_defender / 5.0);
                    if !p.defender_dies { put("atk:ret", p.damage_to_attacker / 5.0); }
                    put("atk:die", (p.attacker_dies && !p.defender_dies) as i32 as f32);
                }
                if let Some(d) = get_unit_at(s, tgt) {
                    put("atk:tcost", get_unit_setting(d.unit_type).cost.max(0) as f32 / 5.0);
                    put("atk:tcity", (get_city_at(s, tgt).is_some()) as i32 as f32);
                }
                put("atk:incity", in_own_city(src) as i32 as f32);
                if unit.map_or(false, |u| u.unit_type == UnitType::Defender) { put("atk:defender", 1.0); }
                if unit.map_or(false, |u| u.moved) { put("atk:aftermove", 1.0); }
            }
            3 => {
                let ut = UnitType::from_repr(sub as i8).unwrap_or(UnitType::None);
                put(&format!("tr:{ut:?}"), 1.0);
                put(&format!("tr:{ut:?}|t{}", cx.bucket), 1.0);
                let cost = get_unit_setting(ut).cost.max(0);
                put("tr:cost", cost as f32 / 5.0);
                put("tr:left", (base_stars - cost).clamp(0, 30) as f32 / 10.0);
                let threat = cx.enemies.iter().filter(|e| dist(s, e.0, src) <= 2).count();
                put("tr:threat", threat.min(4) as f32);
                if threat > 0 && ut == UnitType::Defender { put("tr:threat_def", 1.0); }
            }
            4 => {
                let ut = UnitType::from_repr(sub as i8).unwrap_or(UnitType::None);
                put(&format!("up:{ut:?}"), 1.0);
            }
            5 => {
                let Some(tt) = TechnologyType::from_repr(sub as i8) else { out.push(Cand { kind, src, tgt, sub, f }); continue; };
                put(&format!("rs:{tt:?}"), 1.0);
                if let Some(tr) = s.tribes.get(&me) { put("rs:cost", get_tech_cost(tr, tt) as f32 / 5.0); }
                put("rs:tier", get_tech_tier(tt) as f32);
                if cx.turn <= 3 && cx.opener.contains(&tt) { put("rs:opener", 1.0); }
            }
            6 => {
                let st = StructureType::from_repr(sub as i8).unwrap_or(StructureType::None);
                put(&format!("bd:{st:?}"), 1.0);
            }
            7 => {
                let r = get_resource_at(s, tgt).map(|r| format!("{r:?}")).unwrap_or_default();
                put(&format!("hv:{r}"), 1.0);
            }
            12 => {
                let rw = CityRewardType::from_repr(sub as i8).unwrap_or(CityRewardType::None);
                put(&format!("rw:{rw:?}"), 1.0);
            }
            _ => {}
        }
        // forward-model outcome (not for EndTurn, Step, Research: their effect is the position / a tech)
        if !matches!(kind, 0 | 1 | 5) {
            if let Some(u) = sim.simulate_move(mv.as_ref()) {
                let t = &sim.state;
                let (ehp, en) = sum_hp(t, |p| p != me && is_enemy(s, me, p));
                let (ohp, on) = sum_hp(t, |p| p == me);
                let ds = t.tribes.get(&me).map_or(0, |x| x.stars) - base_stars;
                let dpop = pop(t, me) - pop0;
                let dcity = t.tribes.get(&me).map_or(0, |x| x.cities.len()) as i32 - ncity0 as i32;
                put("fm:ekill", (en0 - en).max(0) as f32);
                put("fm:ehp", (ehp0 - ehp) / 5.0);
                put("fm:ohp", (ohp0 - ohp).max(0.0) / 5.0);
                put("fm:odie", (on0 - on + if kind == 3 { 1 } else { 0 }).max(0) as f32);
                if kind != 3 && kind != 4 { put("fm:dstars", ds as f32 / 5.0); }
                put("fm:dpop", dpop as f32);
                put("fm:dcity", dcity as f32);
                crate::api::undo(&mut sim, u);
            }
        }
        out.push(Cand { kind, src, tgt, sub, f });
    }
    (cx, out)
}

/// v1: hand rules (data/bot_rules.json and sim-dist findings). Higher = more likely.
pub fn score_v1(cx: &Ctx, c: &Cand) -> f64 {
    let g = |n: &str| c.get(n) as f64;
    match c.kind {
        12 => 100.0,                              // pending level-up reward
        9 => 95.0,                                // capture a city
        8 => 90.0,                                // capture a village
        10 => 85.0,                               // examine a ruin
        11 => 40.0,
        2 | 13 => {
            // BOT-ATTACK-TARGET: kill > least return damage > most expensive target;
            // BOT-ATTACK-DECISION: not from the own city, not a Defender without a kill
            let base = if g("atk:kill") > 0.0 { 80.0 } else if g("atk:incity") > 0.0 || g("atk:defender") > 0.0 { 20.0 } else { 50.0 };
            base - 3.0 * g("atk:ret") + g("atk:tcost") + 0.5 * g("atk:dmg") - 30.0 * g("atk:die")
        }
        1 => {
            let mut v = 30.0;
            if g("st:ontarget") > 0.0 { v += 40.0; }
            v -= 6.0 * g("st:dtarget");
            v -= 2.0 * g("st:denemy");
            v += 1.0 * g("st:fog");
            if g("st:leavecity") > 0.0 && g("st:adjenemy") == 0.0 { v -= 3.0; }
            if g("st:lowhp") > 0.0 { v -= 4.0 * g("st:lowhp_dcap"); }
            if g("st:embark") > 0.0 { v -= 10.0; }
            v
        }
        3 => {
            // trains: Warrior early, more mixed later (sim-dist); trains rise with time
            let early = cx.turn < 10;
            let ut = UnitType::from_repr(c.sub as i8).unwrap_or(UnitType::None);
            let pref = match ut {
                UnitType::Warrior | UnitType::Mermaid => if early { 10.0 } else { 4.0 },
                UnitType::Defender | UnitType::MermaidDefender => if g("tr:threat") > 0.0 { 9.0 } else { 3.0 },
                UnitType::Swordsman | UnitType::Swordsmaid | UnitType::Rider | UnitType::Archer => 5.0,
                _ => 2.0,
            };
            [20.0, 26.0, 30.0, 34.0][cx.bucket] + pref
        }
        5 => if g("rs:opener") > 0.0 { 45.0 } else { 18.0 - 3.0 * g("rs:tier") },
        4 => 15.0,
        6 | 7 => 22.0 + 6.0 * g("fm:dpop").min(3.0),
        0 => 5.0,
        _ => 10.0,
    }
}

/// v2: a fitted linear score, data/bot_policy.json {"weights": {feature: w}, "temperature": t}.
#[derive(Debug, Clone, Default)]
pub struct Weights { pub w: HashMap<u16, f64>, pub temperature: f64, pub capture_first: bool }

impl Weights {
    pub fn from_json(v: &Value) -> Self {
        let mut w = HashMap::new();
        for (k, x) in v["weights"].as_object().into_iter().flatten() { w.insert(col(k), x.as_f64().unwrap_or(0.0)); }
        // endturn_bias: an offset on EndTurn, calibrated on playouts (tools/bot_policy.py play --endbias)
        *w.entry(col("k:EndTurn")).or_insert(0.0) += v["endturn_bias"].as_f64().unwrap_or(0.0);
        // bias: further offsets {feature: x}, calibrated the same way
        for (k, x) in v["bias"].as_object().into_iter().flatten() { *w.entry(col(k)).or_insert(0.0) += x.as_f64().unwrap_or(0.0); }
        Weights { w, temperature: v["temperature"].as_f64().unwrap_or(1.0), capture_first: v["capture_first"].as_bool().unwrap_or(false) }
    }
    pub fn from_file(path: &str) -> Result<Self, String> {
        let t = std::fs::read_to_string(path).map_err(|e| format!("{path}: {e}"))?;
        Ok(Self::from_json(&serde_json::from_str(&t).map_err(|e| format!("{path}: {e}"))?))
    }
    pub fn score(&self, c: &Cand) -> f64 {
        c.f.iter().map(|(k, v)| self.w.get(k).copied().unwrap_or(0.0) * *v as f64).sum()
    }
}

pub enum Policy { V1, V2(Weights), Random }

impl Policy {
    pub fn scores(&self, cx: &Ctx, cands: &[Cand]) -> Vec<f64> {
        match self {
            Policy::V1 => cands.iter().map(|c| score_v1(cx, c)).collect(),
            // captures are near-certain for the bots (v1 rule: village 0.965, city 0.987 top-1), so v2 takes them
            // first instead of sampling past them (cities came out low in playouts)
            Policy::V2(w) => cands.iter().map(|c| w.score(c) + if w.capture_first && matches!(c.kind, 8 | 9) { 50.0 } else { 0.0 }).collect(),
            Policy::Random => vec![0.0; cands.len()],
        }
    }
}

/// Small deterministic RNG (xorshift64*) so playouts are reproducible from a seed.
pub struct Rng(pub u64);
impl Rng {
    pub fn next_f64(&mut self) -> f64 {
        self.0 ^= self.0 >> 12; self.0 ^= self.0 << 25; self.0 ^= self.0 >> 27;
        (self.0.wrapping_mul(0x2545F4914F6CDD1D) >> 11) as f64 / (1u64 << 53) as f64
    }
}

/// Index of the chosen move: softmax over scores / temperature (argmax when temperature <= 0).
pub fn pick(scores: &[f64], temperature: f64, rng: &mut Rng) -> usize {
    if scores.is_empty() { return 0; }
    let best = scores.iter().cloned().fold(f64::MIN, f64::max);
    if temperature <= 0.0 { return scores.iter().position(|&x| x == best).unwrap(); }
    let p: Vec<f64> = scores.iter().map(|x| ((x - best) / temperature).exp()).collect();
    let mut r = rng.next_f64() * p.iter().sum::<f64>();
    for (i, x) in p.iter().enumerate() { r -= x; if r <= 0.0 { return i; } }
    p.len() - 1
}

/// Play one move for the player to move. Returns the move played (None if no legal move or it failed).
pub fn step(g: &mut Game, pol: &Policy, temperature: f64, rng: &mut Rng) -> Option<Box<dyn Move>> {
    let legal = g.legal_moves();
    if legal.is_empty() { return None; }
    let (cx, cands) = features(g, &legal);
    let sc = pol.scores(&cx, &cands);
    let i = if matches!(pol, Policy::Random) { (rng.next_f64() * legal.len() as f64) as usize % legal.len() } else { pick(&sc, temperature, rng) };
    let mv = dyn_clone::clone_box(legal[i].as_ref());
    let _undo = g.play_move(mv.as_ref())?;
    Some(mv)
}

/// Play the current player's whole turn (until EndTurn, or `cap` moves, then EndTurn).
pub fn play_turn(g: &mut Game, pol: &Policy, temperature: f64, rng: &mut Rng, cap: usize) -> Vec<String> {
    let me = g.state.settings.current_player_turn_id;
    let mut log = Vec::new();
    for _ in 0..cap {
        if g.state.settings.current_player_turn_id != me || g.state.settings._game_over { return log; }
        let label_state = crate::api::clone(g);
        match step(g, pol, temperature, rng) {
            Some(mv) => {
                log.push(crate::api::label(&label_state.state, mv.as_ref()));
                if mv.move_type() == MoveType::EndTurn { return log; }
            }
            None => return log,
        }
    }
    if g.state.settings.current_player_turn_id == me { crate::api::end_turn(g); log.push("EndTurn (cap)".into()); }
    log
}

/// One decision for tools/bot_policy.py: the candidates (kind, src, tgt, sub, v1 score, sparse features) and
/// the index of the move the bot played.
pub fn record(g: &Game, legal: &[Box<dyn Move>], chosen: usize) -> Value {
    let (cx, cands) = features(g, legal);
    let rows: Vec<Value> = cands.iter().map(|c| {
        let mut flat: Vec<Value> = Vec::with_capacity(c.f.len() * 2);
        for (k, v) in &c.f { flat.push(json!(k)); flat.push(json!((*v * 100.0).round() / 100.0)); }
        json!([c.kind, c.src, c.tgt, c.sub, (score_v1(&cx, c) * 100.0).round() / 100.0, flat])
    }).collect();
    let tribe = g.state.tribes.get(&cx.me).map(|t| format!("{:?}", t.tribe_type)).unwrap_or_default();
    json!({"pl": cx.me, "turn": cx.turn, "tribe": tribe, "crazy": cx.crazy, "handicap": g.state.tribes.get(&cx.me).map_or(0, |t| t.handicap), "stars": cx.stars, "chosen": chosen, "c": rows})
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pick_argmax_and_seeded_sampling() {
        let sc = [1.0, 3.0, 2.0];
        let mut r = Rng(7);
        assert_eq!(pick(&sc, 0.0, &mut r), 1);
        let a: Vec<usize> = { let mut r = Rng(42); (0..50).map(|_| pick(&sc, 1.0, &mut r)).collect() };
        let b: Vec<usize> = { let mut r = Rng(42); (0..50).map(|_| pick(&sc, 1.0, &mut r)).collect() };
        assert_eq!(a, b);
        assert!(a.iter().filter(|&&i| i == 1).count() > a.iter().filter(|&&i| i == 0).count());
    }

    #[test]
    fn weights_endturn_bias() {
        let w = Weights::from_json(&json!({"weights": {"k:EndTurn": 1.0}, "endturn_bias": -1.5, "capture_first": true}));
        let c = Cand { kind: 0, src: -1, tgt: -1, sub: 0, f: vec![(col("k:EndTurn"), 1.0)] };
        assert!((w.score(&c) + 0.5).abs() < 1e-9);
        assert!(w.capture_first);
    }
}
