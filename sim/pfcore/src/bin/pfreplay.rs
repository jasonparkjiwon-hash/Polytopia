//! Replay a real save's logged actions in Polyfish, from one checkpoint to the next, and check each action is legal there.
//! usage: pfreplay <jobs.json>   (written by tools/pf_miss.py)
//! jobs.json: [{"tag", "start": checkpoint save, "final": save with the full log, "from": n0, "to": n1}]
//! Prints one JSON line per job: units (save ids; negative = new, paired by tile), stars, legality per action type,
//! illegal cases, load report. The scoring lives in tools/pf_miss.py.
use polyfish::functions::get_adjacent_indices;
use polyfish::game::Game;
use polyfish::moves::*;
use polyfish::save_loader::{self, unit_type, UNIT_STANDINS};
use polyfish::states::{GameState, UnitState};
use polyfish::types::*;
use serde_json::{json, Value};
use std::collections::{BTreeMap, HashMap};

fn fmt_of(t: i64) -> &'static str {
    // replay.py FMT: struct layout of each action payload
    match t {
        1 | 5 | 16 => "BHII",
        2 | 6 => "BIIIII",
        3 | 4 | 9 | 13 | 14 | 17 | 18 | 21 | 24 | 25 | 38 => "BII",
        7 => "BIII",
        8 => "BH",
        11 => "BIIH",
        27 | 29 | 30 => "BIIB",
        28 => "BBB",
        _ => "B",
    }
}

fn unpack(t: i64, raw: &str) -> Vec<i64> {
    let b: Vec<u8> = (0..raw.len() / 2).map(|k| u8::from_str_radix(&raw[2 * k..2 * k + 2], 16).unwrap_or(0)).collect();
    let mut o = 0usize;
    let mut v = Vec::new();
    for c in fmt_of(t).chars() {
        let n = match c { 'B' => 1, 'H' => 2, _ => 4 };
        if o + n > b.len() { v.push(0); continue; }
        let mut x: i64 = 0;
        for k in 0..n { x |= (b[o + k] as i64) << (8 * k); }
        v.push(x);
        o += n;
    }
    v
}

struct Replay {
    game: Game,
    size: i32,
    next_temp: i64,
    real_type: HashMap<i64, i32>,      // uid -> v123 unit type id, for units held as a stand-in
    passenger_uid: HashMap<i64, i64>,  // boat uid -> the passenger's own id (it gets it back on landing)
    legal: BTreeMap<String, [i64; 2]>, // action name -> [legal, total]
    illegal: Vec<Value>,
    notes: BTreeMap<String, i64>,
    acts: Vec<Value>,
    done: std::collections::HashSet<usize>, // logged actions already played out of order
    hints: HashMap<usize, (i64, Option<i64>)>, // action index -> ruin reward (RuinsRewardType), tech (from the next save)
}

fn name_of(t: i64) -> &'static str {
    match t {
        1 => "Build", 2 => "Attack", 3 => "Recover", 4 => "HealOthers", 5 => "Train", 6 => "Move", 7 => "Capture",
        8 => "Research", 9 => "Destroy", 11 => "CityReward", 13 => "Promote", 14 => "ExamineRuins", 15 => "EndTurn",
        16 => "Upgrade", 17 => "FreezeArea", 18 => "BreakIce", 20 => "StartMatch", 21 => "CityLevelUp", 24 => "Explode",
        27 => "OfferPeace", 28 => "PeaceReply", 29 => "BreakPeace", 30 => "Embassy", 38 => "Swarm", _ => "other",
    }
}

impl Replay {
    fn idx(&self, x: i64, y: i64) -> i32 { (y as i32) * self.size + x as i32 }

    fn note(&mut self, k: &str) { *self.notes.entry(k.to_string()).or_insert(0) += 1; }

    fn unit_at_mut(&mut self, idx: i32) -> Option<&mut UnitState> {
        polyfish::functions::get_unit_at_mut(&mut self.game.state, idx)
    }

    /// Give every unit Polyfish spawned (uid 0) a temporary negative id; pf_miss pairs these with saved units by tile.
    fn name_new_units(&mut self) {
        let mut t = self.next_temp;
        for tr in self.game.state.tribes.values_mut() {
            for u in tr.units.iter_mut() {
                if u.uid == 0 { t -= 1; u.uid = t; }
            }
        }
        self.next_temp = t;
    }

    fn temp_id(&mut self) -> i64 { self.next_temp -= 1; self.next_temp }

    /// The logged move/attack names the unit: a temp id at the source tile takes the real id.
    fn rekey(&mut self, idx: i32, uid: i64) {
        let mut old = None;
        if let Some(u) = self.unit_at_mut(idx) {
            if u.uid < 0 && uid > 0 { old = Some(u.uid); u.uid = uid; }
        }
        if let Some(o) = old {
            if let Some(rt) = self.real_type.remove(&o) { self.real_type.insert(uid, rt); }
            if let Some(p) = self.passenger_uid.remove(&o) { self.passenger_uid.insert(uid, p); }
        }
    }

    /// Examine Ruins with the reward the next save shows (the log doesn't record it).
    fn ruin_move(&self, i: usize, v: &[i64]) -> Option<Box<dyn Move>> {
        let (rw, tech) = *self.hints.get(&i)?;
        let mut m = CaptureMove::with_reward(self.idx(v[1], v[2]), RuinsRewardType::from_repr(rw as i8)?);
        m.tech_hint = tech.and_then(|k| TechnologyType::from_repr(k as i8));
        Some(Box::new(m))
    }

    /// v123 lets a player choose a level-up reward later in the turn; Polyfish offers only the reward until it is chosen.
    /// So play the player's next logged CityReward now (counted legal if Polyfish offers it).
    fn rewards_first(&mut self, i: usize, actor: i32) {
        for _ in 0..8 {
            let legal = self.game.legal_moves();
            if !legal.iter().any(|m| m.move_type() == MoveType::Reward) { return; }
            let keys: Vec<Value> = legal.iter().map(|m| m.serialize()).collect();
            let mut found = None;
            for j in i + 1..self.acts.len() {
                let a = &self.acts[j];
                let (t, raw) = (a["type"].as_i64().unwrap_or(0), a["raw"].as_str().unwrap_or(""));
                let v = unpack(t, raw);
                if v[0] as i32 != actor { if t == 15 { break; } continue; }
                if t == 15 { break; }
                if t == 11 && !self.done.contains(&j) {
                    if let Some(rw) = CityRewardType::from_repr(v[3] as i8) {
                        let m = RewardMove::new(self.idx(v[1], v[2]), rw);
                        if keys.contains(&m.serialize()) { found = Some((j, m)); break; }
                    }
                }
            }
            let Some((j, m)) = found else { return; };
            self.done.insert(j);
            let e = self.legal.entry("CityReward".into()).or_insert([0, 0]);
            e[0] += 1; e[1] += 1;
            self.note("city reward played early (Polyfish offers it first)");
            if self.game.play_move(&m).is_none() { self.note("CityReward: Polyfish refused to execute"); }
            self.name_new_units();
        }
    }

    /// Candidate Polyfish moves for one logged action; the first legal one is played.
    fn candidates(&mut self, t: i64, v: &[i64]) -> Result<Vec<Box<dyn Move>>, String> {
        let s = &self.game.state;
        let at = |x: i64, y: i64| (y as i32) * s.settings.size + x as i32;
        Ok(match t {
            6 => vec![Box::new(StepMove::new(at(v[1], v[2]), at(v[3], v[4])))],
            2 => {
                let (a, d) = (at(v[2], v[3]), at(v[4], v[5]));
                let converts = polyfish::functions::get_unit_at(s, a).map_or(false, |u| polyfish::settings::has_skill(u.unit_type, SkillType::Convert));
                // a converter's logged attack converts (Python replay); Polyfish's move list never offers ConvertMove
                if converts { vec![Box::new(ConvertMove::new(a, d))] }
                else { vec![Box::new(AttackMove::new(a, d)), Box::new(ConvertMove::new(a, d))] }
            }
            5 => {
                let ut = unit_type(v[1] as i32).ok_or(format!("unit type {} not in Polyfish", v[1]))?;
                vec![Box::new(SummonMove::new(at(v[2], v[3]), ut))]
            }
            16 => {
                let ut = unit_type(v[1] as i32).ok_or(format!("unit type {} not in Polyfish", v[1]))?;
                vec![Box::new(UpgradeMove::new(at(v[2], v[3]), ut))]
            }
            1 => {
                let k = at(v[2], v[3]);
                match v[1] {
                    7 | 9 | 15 => vec![Box::new(HarvestMove::new(k))], // Fishing, Hunting, Harvest Fruit
                    46 => vec![Box::new(CaptureMove::new(k)), Box::new(HarvestMove::new(k))], // Starfish
                    30 => vec![Box::new(EnchantAnimalMove::new(k))],
                    10 => vec![Box::new(ClearForestMove::new(k))],
                    11 => vec![Box::new(BurnForestMove::new(k))],
                    imp => {
                        let st: StructureType = serde_json::from_value(Value::from(imp)).map_err(|_| format!("improvement {imp} not in Polyfish"))?;
                        vec![Box::new(BuildMove::new(k, st))]
                    }
                }
            }
            7 => vec![Box::new(CaptureMove::new(at(v[2], v[3])))],
            14 => vec![Box::new(CaptureMove::new(at(v[1], v[2])))],
            8 => {
                let tt = TechnologyType::from_repr(v[1] as i8).filter(|_| v[1] < 128).ok_or(format!("tech {} not in Polyfish", v[1]))?;
                vec![Box::new(ResearchMove::new(tt))]
            }
            11 => {
                let rw = CityRewardType::from_repr(v[3] as i8).ok_or(format!("city reward {} not in Polyfish", v[3]))?;
                vec![Box::new(RewardMove::new(at(v[1], v[2]), rw))]
            }
            13 => vec![Box::new(PromoteMove::new(at(v[1], v[2])))],
            3 => vec![Box::new(RecoverMove::new(at(v[1], v[2])))],
            4 => vec![Box::new(HealOthersMove::new(at(v[1], v[2])))],
            17 => vec![Box::new(FreezeAreaMove::new(at(v[1], v[2])))],
            24 => vec![Box::new(ExplodeMove::new(at(v[1], v[2])))],
            38 => vec![Box::new(BoostMove::new(at(v[1], v[2])))],
            9 => vec![Box::new(DestroyMove::new(at(v[1], v[2])))],
            18 => {
                // v123 logs the acting unit's tile and breaks the ice around it; Polyfish breaks one ice tile per move
                let u = at(v[1], v[2]);
                let ice: Vec<i32> = get_adjacent_indices(s, u, 1).into_iter()
                    .filter(|k| s.tiles.get(k).map_or(false, |t| t.terrain_type == TerrainType::Ice)).collect();
                if ice.is_empty() { return Err("break ice: no ice next to the unit".into()); }
                ice.into_iter().map(|k| Box::new(BreakIceMove::new(k)) as Box<dyn Move>).collect()
            }
            27 => vec![Box::new(abilities::diplomacy::PeaceTreatyMove::new(at(v[1], v[2]), v[3] as i32))],
            28 => vec![Box::new(abilities::diplomacy::PeaceRequestResponse::new(v[1] as i32, v[2] as i32))],
            29 => vec![Box::new(BreakPeaceMove::new(v[3] as i32))],
            30 => vec![Box::new(abilities::diplomacy::EstablishEmbassyMove::new(at(v[1], v[2]), v[3] as i32))],
            15 => vec![Box::new(EndTurnMove)],
            _ => return Err(format!("action type {t} has no Polyfish move")),
        })
    }

    fn apply(&mut self, i: usize, a: &Value) {
        let t = a["type"].as_i64().unwrap_or(0);
        let raw = a["raw"].as_str().unwrap_or("");
        let v = unpack(t, raw);
        let pl = *v.first().unwrap_or(&0) as i32;
        let name = name_of(t).to_string();
        if self.done.contains(&i) { return; }
        if t == 20 || t == 21 { return; } // StartMatch; CityLevelUp is a marker (the level-up itself comes with the CityReward)
        if t == 15 && pl == 255 {
            // round end: Polyfish wraps to player 1 and counts the turn inside the last player's EndTurn
            return;
        }
        let actor = if t == 28 { v[0] as i32 } else { pl };
        if actor != self.game.state.settings.current_player_turn_id {
            self.note("turn order differs (actor set)");
            self.game.state.settings.current_player_turn_id = actor;
        }
        if t != 11 { self.rewards_first(i, actor); }
        // rekey temp ids named by the log
        if t == 6 { let k = self.idx(v[1], v[2]); self.rekey(k, v[5]); }
        if t == 2 { let k = self.idx(v[2], v[3]); self.rekey(k, v[1]); }
        // the acting unit (Move or Attack): its uid and type before, to catch boarding/landing (an attack can move it in)
        let before: Option<(i64, UnitType)> = match t {
            6 => polyfish::functions::get_unit_at(&self.game.state, self.idx(v[1], v[2])),
            2 => polyfish::functions::get_unit_at(&self.game.state, self.idx(v[2], v[3])),
            _ => None,
        }.map(|u| (u.uid, u.unit_type));

        let cands = match self.candidates(t, &v) {
            Ok(c) => c,
            Err(e) => {
                self.legal.entry(name.clone()).or_insert([0, 0])[1] += 1;
                self.illegal.push(json!({"i": i, "type": name, "raw": raw, "cause": "unmapped", "why": e}));
                return;
            }
        };
        let legal = self.game.legal_moves();
        let keys: Vec<Value> = legal.iter().map(|m| m.serialize()).collect();
        let pick = cands.iter().position(|c| keys.contains(&c.serialize()));
        let e = self.legal.entry(name.clone()).or_insert([0, 0]);
        e[1] += 1;
        let played_ok;
        match pick {
            Some(p) => {
                e[0] += 1;
                let mut mv = legal.into_iter().find(|m| m.serialize() == cands[p].serialize()).unwrap();
                if t == 14 {
                    if let Some(h) = self.ruin_move(i, &v) { mv = h; }
                }
                played_ok = self.game.play_move(mv.as_ref()).is_some();
                if t == 18 {
                    for (k, c) in cands.iter().enumerate() {
                        if k != p && self.game.play_move(c.as_ref()).is_none() { self.note("break ice: extra tile refused"); }
                    }
                }
            }
            None => {
                let pending = legal.iter().any(|m| m.move_type() == MoveType::Reward);
                // Short of stars only (Polyfish's stars drifted)? Then play it on credit: the tribe's stars go below what they'd be.
                const CREDIT: i32 = 1000;
                let me = self.game.state.settings.current_player_turn_id;
                let short = !pending && matches!(t, 1 | 5 | 8 | 16 | 30) && {
                    if let Some(tr) = self.game.state.tribes.get_mut(&me) { tr.stars += CREDIT; }
                    let keys2: Vec<Value> = self.game.legal_moves().iter().map(|m| m.serialize()).collect();
                    if let Some(tr) = self.game.state.tribes.get_mut(&me) { tr.stars -= CREDIT; }
                    cands.iter().any(|c| keys2.contains(&c.serialize()))
                };
                let why = if short { "stars short in Polyfish (drift)".to_string() } else { self.why_illegal(t, &v, pending) };
                let detail = self.detail(t, &v, &keys);
                self.illegal.push(json!({"i": i, "type": name, "raw": raw, "cause": why, "turn": self.game.state.settings.turn, "detail": detail}));
                if short {
                    if let Some(tr) = self.game.state.tribes.get_mut(&me) { tr.stars += CREDIT; }
                    played_ok = cands.iter().any(|c| self.game.play_move(c.as_ref()).is_some());
                    if let Some(tr) = self.game.state.tribes.get_mut(&me) { tr.stars -= CREDIT; }
                } else {
                    played_ok = cands.iter().any(|c| self.game.play_move(c.as_ref()).is_some());
                }
            }
        }
        if !played_ok {
            self.note(&format!("{name}: Polyfish refused to execute"));
        }
        // boarding gives the boat a new id; landing gives the passenger its id back
        if let Some((uid, old)) = before {
            let now = self.game.state.tribes.get(&actor).and_then(|tr| tr.units.iter().find(|u| u.uid == uid)).map(|u| u.unit_type);
            if let Some(nt) = now {
                let new_id = if !old.is_naval() && nt.is_naval() {
                    let tmp = self.temp_id();
                    self.passenger_uid.insert(tmp, uid);
                    if let Some(rt) = self.real_type.remove(&uid) { self.real_type.insert(tmp, rt); }
                    Some(tmp)
                } else if old.is_naval() && !nt.is_naval() {
                    self.passenger_uid.remove(&uid)
                } else { None };
                if let Some(n) = new_id {
                    if let Some(u) = self.game.state.tribes.get_mut(&actor).and_then(|tr| tr.units.iter_mut().find(|u| u.uid == uid)) { u.uid = n; }
                }
            }
        }
        if t == 16 && played_ok {
            let k = self.idx(v[2], v[3]);
            let tmp = self.temp_id();
            let mut old = None;
            if let Some(u) = self.unit_at_mut(k) { old = Some(u.uid); u.uid = tmp; }
            if let Some(o) = old { if let Some(p) = self.passenger_uid.remove(&o) { self.passenger_uid.insert(tmp, p); } }
        }
        let new_before = self.next_temp;
        self.name_new_units();
        if t == 5 && UnitType::from_repr(v[1] as i8).is_none() {
            for id in self.next_temp..new_before { self.real_type.insert(id, v[1] as i32); }
        }
    }

    /// What Polyfish sees around an illegal unit action: the unit, the two tiles, and the targets Polyfish offers from that tile.
    fn detail(&self, t: i64, v: &[i64], keys: &[Value]) -> Value {
        let s = &self.game.state;
        let at = |x: i64, y: i64| (y as i32) * s.settings.size + x as i32;
        let me = s.settings.current_player_turn_id;
        let city = |c: &polyfish::states::CityState| json!({"xy": [c.idx % s.settings.size, c.idx / s.settings.size], "level": c.level, "progress": c.progress, "pop": c.population, "rewards": c.rewards.iter().map(|r| *r as i32).collect::<Vec<_>>()});
        let pending: Vec<Value> = s.tribes.get(&me).map(|tr| tr.cities.iter().filter(|c| c.level > 1 && c.rewards.len() < (c.level - 1) as usize).map(|c| city(c)).collect()).unwrap_or_default();
        if t == 11 {
            let k = at(v[1], v[2]);
            let c = s.tribes.values().flat_map(|tr| tr.cities.iter()).find(|c| c.idx == k).map(|c| json!([c.owner, city(c)]));
            return json!({"city": c, "pending": pending});
        }
        if !pending.is_empty() { return json!({"pending": pending}); }
        let (src, dst) = match t { 6 => (at(v[1], v[2]), at(v[3], v[4])), 2 => (at(v[2], v[3]), at(v[4], v[5])), 3 | 4 | 13 | 14 | 17 | 18 | 24 | 38 => (at(v[1], v[2]), -1), _ => return Value::Null };
        let tile = |k: i32| -> Value {
            if k < 0 { return Value::Null; }
            let tl = &s.tiles[&k];
            let st = polyfish::functions::get_structure_at(s, k).map(|x| x.structure_type as i32);
            let u = polyfish::functions::get_unit_at(s, k).map(|u| json!([u.owner, u.unit_type as i32, u.health, u.uid]));
            json!({"xy": [tl.coords.x, tl.coords.y], "terrain": tl.terrain_type as i32, "owner": tl.owner, "fx": tl.effects.iter().map(|e| *e as i32).collect::<Vec<_>>(), "struct": st, "unit": u,
                   "seen": tl.explorers.contains(&s.settings.current_player_turn_id)})
        };
        let u = polyfish::functions::get_unit_at(s, src).map(|u| json!({"type": u.unit_type as i32, "pass": u.passenger_type.map(|p| p as i32), "moved": u.moved, "attacked": u.attacked, "fx": u.effects.iter().map(|e| *e as i32).collect::<Vec<_>>(), "hp": u.health, "uid": u.uid}));
        let offers: Vec<Value> = keys.iter().filter(|k| k.get("src").and_then(|x| x.as_i64()) == Some(src as i64))
            .map(|k| json!([k["moveType"], k.get("target").and_then(|x| x.as_i64()).map(|x| [x % s.settings.size as i64, x / s.settings.size as i64])])).collect();
        json!({"unit": u, "src": tile(src), "dst": tile(dst), "offers": offers})
    }

    /// Why a logged action isn't in Polyfish's legal list: a first-cut classification, refined in pf-loader.md.
    fn why_illegal(&self, t: i64, v: &[i64], pending_reward: bool) -> String {
        let s = &self.game.state;
        let at = |x: i64, y: i64| (y as i32) * s.settings.size + x as i32;
        if pending_reward { return "reward pending (Polyfish offers only the city reward)".into(); }
        let tribe = s.tribes.get(&s.settings.current_player_turn_id);
        let src = match t { 6 => Some(at(v[1], v[2])), 2 => Some(at(v[2], v[3])), 3 | 4 | 13 | 14 | 17 | 18 | 24 | 38 => Some(at(v[1], v[2])), 7 => Some(at(v[2], v[3])), _ => None };
        if let Some(k) = src {
            match polyfish::functions::get_unit_at(s, k) {
                None => return "no unit at source in Polyfish".into(),
                Some(u) if u.owner != s.settings.current_player_turn_id => return "source unit has another owner in Polyfish".into(),
                Some(u) => {
                    if t == 6 && u.moved { return "unit already moved in Polyfish".into(); }
                    if t == 2 && u.attacked { return "unit already attacked in Polyfish".into(); }
                    if t == 2 && polyfish::settings::has_skill(u.unit_type, SkillType::Convert) { return "convert: Polyfish's move list has no ConvertMove".into(); }
                    if t == 2 {
                        let d = at(v[4], v[5]);
                        if polyfish::functions::get_unit_at(s, d).is_none() { return "no defender at target in Polyfish".into(); }
                        return "target not in Polyfish attack list".into();
                    }
                    if t == 6 {
                        let d = at(v[3], v[4]);
                        if polyfish::functions::get_unit_at(s, d).is_some() { return "target tile occupied in Polyfish".into(); }
                        return "target not in Polyfish step list".into();
                    }
                }
            }
        }
        let stars = tribe.map_or(0, |t| t.stars);
        if t == 5 {
            let k = at(v[2], v[3]);
            let ut = unit_type(v[1] as i32).unwrap_or(UnitType::None);
            let Some(tr) = tribe else { return "no tribe".into() };
            let Some(city) = tr.cities.iter().find(|c| c.idx == k) else { return "train: no city of this player there in Polyfish".into() };
            if polyfish::functions::get_unit_at(s, k).is_some() { return "train: city tile occupied in Polyfish".into(); }
            let count = polyfish::functions::get_city_unit_count(s, city);
            if count > city.level { return format!("train: city full in Polyfish (units {count} > level {})", city.level); }
            let unlocked = ut == UnitType::Warrior || tr.tech_vanilla.iter().any(|ts| polyfish::settings::technology::get_unlocked_units(ts.tech_type, tr.tribe_type).contains(&ut));
            if !unlocked { return format!("train: unit {} not unlocked by the tribe's techs in Polyfish", v[1]); }
            return format!("train not offered (stars {stars}, cost {})", polyfish::settings::get_unit_setting(ut).cost);
        }
        match t {
            1 => format!("build {} not offered (stars {stars})", v[1]),
            8 => format!("research not offered (stars {stars})"),
            16 => format!("upgrade not offered (stars {stars})"),
            11 => "city reward not pending in Polyfish".into(),
            15 => "end turn not offered".into(),
            _ => "not offered".into(),
        }
    }
}

fn units_out(r: &Replay) -> Vec<Value> {
    let mut out = Vec::new();
    for tr in r.game.state.tribes.values() {
        for u in &tr.units {
            let ty = r.real_type.get(&u.uid).copied().unwrap_or(u.unit_type as i32);
            let pas = u.passenger_type.map(|p| p as i32);
            out.push(json!([u.uid, u.owner, ty, u.coords.x, u.coords.y, u.health, u.veteran as i32, pas]));
        }
    }
    out
}

/// The player to move at a checkpoint: the next actor in the log (round-end markers skipped).
fn current_player(acts: &[Value], from: usize) -> i32 {
    for a in &acts[from..] {
        let raw = a["raw"].as_str().unwrap_or("");
        let p = i64::from_str_radix(raw.get(0..2).unwrap_or("00"), 16).unwrap_or(0);
        let t = a["type"].as_i64().unwrap_or(0);
        if p != 255 && t != 20 { return if t == 28 { p as i32 } else { p as i32 }; }
    }
    1
}

fn run_job(job: &Value) -> Result<Value, String> {
    let rd = |k: &str| -> Result<Value, String> {
        let p = job[k].as_str().ok_or(format!("job has no {k}"))?;
        serde_json::from_str(&std::fs::read_to_string(p).map_err(|e| format!("{p}: {e}"))?).map_err(|e| format!("{p}: {e}"))
    };
    let start = rd("start")?;
    let fin = rd("final")?;
    let acts = fin["actions"].as_array().ok_or("no actions")?.clone();
    let from = job["from"].as_u64().unwrap_or(0) as usize;
    let to = (job["to"].as_u64().unwrap_or(acts.len() as u64) as usize).min(acts.len());
    let cur = current_player(&acts, from);
    let (game, rep) = save_loader::load(&start, "current", cur)?;
    let size = game.state.settings.size;
    let mut r = Replay { game, size, next_temp: 0, real_type: HashMap::new(), passenger_uid: HashMap::new(),
        legal: BTreeMap::new(), illegal: Vec::new(), notes: BTreeMap::new(), acts: acts[..to].to_vec(), done: Default::default(), hints: HashMap::new() };
    for h in job["hints"].as_array().into_iter().flatten() {
        r.hints.insert(h["i"].as_u64().unwrap_or(0) as usize, (h["reward"].as_i64().unwrap_or(0), h["tech"].as_i64()));
    }
    // stand-in types and boat passengers, from the save records
    for row in start["currentTiles"].as_array().into_iter().flatten() {
        for tv in row.as_array().into_iter().flatten() {
            if let Some(u) = tv.get("Unit").filter(|u| !u.is_null()) {
                let (id, ut) = (u["Id"].as_i64().unwrap_or(0), u["UnitType"].as_i64().unwrap_or(0) as i32);
                if UNIT_STANDINS.iter().any(|(k, _)| *k == ut) { r.real_type.insert(id, ut); }
                if let Some(p) = tv.get("PassengerUnit").filter(|p| !p.is_null()) {
                    r.passenger_uid.insert(id, p["Id"].as_i64().unwrap_or(0));
                    let pt = p["UnitType"].as_i64().unwrap_or(0) as i32;
                    if UNIT_STANDINS.iter().any(|(k, _)| *k == pt) { r.note("stand-in passenger"); }
                }
            }
        }
    }
    // last move direction carries across turns: prime prev_coords from the log (replay.py prime_last_moves)
    let mut last: HashMap<i64, (i32, i32)> = HashMap::new();
    for a in &acts[..from] {
        if a["type"].as_i64() == Some(6) {
            let v = unpack(6, a["raw"].as_str().unwrap_or(""));
            last.insert(v[5], (r.idx(v[1], v[2]), r.idx(v[3], v[4])));
        }
    }
    for tr in r.game.state.tribes.values_mut() {
        for u in tr.units.iter_mut() {
            if let Some((f, to_)) = last.get(&u.uid) {
                if *to_ == u.coords.idx { u.prev_coords = polyfish::coords::Coords::from_index(*f, size); }
            }
        }
    }
    let stars0: BTreeMap<i32, i32> = r.game.state.tribes.iter().map(|(k, t)| (*k, t.stars)).collect();
    // PF_TRACE=1: every star change, as [action index, type, first byte, {player: delta}]
    let trace_on = std::env::var("PF_TRACE").is_ok();
    let mut trace = Vec::new();
    for i in from..to {
        let s0: Vec<(i32, i32)> = if trace_on { r.game.state.tribes.iter().map(|(k, t)| (*k, t.stars)).collect() } else { vec![] };
        r.apply(i, &acts[i]);
        if trace_on {
            let d: BTreeMap<i32, i32> = s0.iter().filter_map(|(k, s)| { let n = r.game.state.tribes[k].stars; (n != *s).then(|| (*k, n - s)) }).collect();
            let raw = acts[i]["raw"].as_str().unwrap_or("");
            if !d.is_empty() { trace.push(json!([i, acts[i]["type"], i64::from_str_radix(raw.get(0..2).unwrap_or("0"), 16).unwrap_or(0), d])); }
        }
    }
    let stars: BTreeMap<i32, i32> = r.game.state.tribes.iter().map(|(k, t)| (*k, t.stars)).collect();
    Ok(json!({"tag": job["tag"], "units": units_out(&r), "stars": stars, "stars0": stars0, "legal": r.legal,
              "illegal": r.illegal, "notes": r.notes, "load": rep, "turn": r.game.state.settings.turn,
              "player": r.game.state.settings.current_player_turn_id, "trace": trace}))
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let jobs: Value = serde_json::from_str(&std::fs::read_to_string(&a[1]).expect("jobs file")).expect("jobs json");
    for job in jobs.as_array().expect("jobs list") {
        let out = std::panic::catch_unwind(|| run_job(job));
        let line = match out {
            Ok(Ok(v)) => v,
            Ok(Err(e)) => json!({"tag": job["tag"], "error": e}),
            Err(_) => json!({"tag": job["tag"], "error": "panic"}),
        };
        println!("PFJSON {}", line);
    }
}

#[allow(dead_code)]
fn _unused(_: &GameState) {}
