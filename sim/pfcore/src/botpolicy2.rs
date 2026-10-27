//! Bot policy (Phase 6 groundwork, bot-policy-2; a second implementation, botpolicy.rs, was written in parallel by the first bot-policy session): rank Polyfish's legal moves the way the built-in bots seem to play.
//! `features` turns each legal move into sparse (name, value) pairs using only the forward model (move generation and
//! its combat preview); `Weights` is a sparse name -> weight table; `score = sum(weight * value)`. The same extractor
//! feeds three things: the decision dump from pfreplay (PF_BOTDUMP=file), the Python fit (tools/bot_policy.py), and
//! the playout bin `pfbot`. v1 = hand-set weights (data/bot_policy_v1.json), v2 = fitted ones. See
//! .scratchpad/investigations/bot-policy.md. No rule code is touched here.
use crate::api;
use crate::functions as F;
use crate::game::Game;
use crate::moves::*;
use crate::types::*;
use serde_json::Value;
use std::collections::HashMap;

pub type Feats = Vec<(String, f32)>;

/// name -> weight; missing names weigh 0. File form: {"w": {"name": weight, ...}}.
#[derive(Default, Clone)]
pub struct Weights(pub HashMap<String, f32>);

impl Weights {
    pub fn from_value(v: &Value, key: &str) -> Result<Weights, String> {
        let w = v.get(key).and_then(|w| w.as_object()).ok_or(format!("no \"{key}\" object"))?;
        Ok(Weights(w.iter().filter_map(|(k, x)| x.as_f64().map(|x| (k.clone(), x as f32))).collect()))
    }
    pub fn score(&self, f: &Feats) -> f32 { f.iter().map(|(k, x)| self.0.get(k).copied().unwrap_or(0.0) * x).sum() }
}

pub fn bucket(turn: i32) -> usize { if turn < 5 { 0 } else if turn < 10 { 1 } else if turn < 20 { 2 } else { 3 } }

/// Per-decision facts shared by every move: where the foes, enemy cities and free villages are.
pub struct Ctx {
    pub me: i32,
    pub turn: i32,
    pub size: i32,
    pub tribe: String,
    pub foes: Vec<i32>,       // enemy unit tiles
    pub enemy_cities: Vec<i32>,
    pub villages: Vec<i32>,   // unowned city tiles the tribe has explored
    pub own_cities: Vec<i32>,
    pub units_left: f32,      // own units that still have a non-train, non-end move
    pub cap: [f32; 5],        // 3x3 around the capital: water+ocean, metal, fruit, game, forest+mountain (for the research opener)
    pub n_techs: f32,
    pub cfeats: Feats,        // turn-level context shared by every group (see `context`)
}

fn nearest(from: i32, set: &[i32], size: i32) -> i32 {
    set.iter().map(|&t| F::get_chebyshev_distance(from, t, size)).min().unwrap_or(15).min(15)
}

pub fn context(g: &Game, legal: &[Box<dyn Move>]) -> Ctx {
    let s = &g.state;
    let me = s.settings.current_player_turn_id;
    let size = s.settings.size;
    let mut foes = Vec::new();
    let mut enemy_cities = Vec::new();
    let mut own_cities = Vec::new();
    for (id, tr) in s.tribes.iter() {
        if *id == me { own_cities.extend(tr.cities.iter().map(|c| c.idx)); continue; }
        if F::is_enemy(s, me, *id) {
            foes.extend(tr.units.iter().map(|u| u.coords.idx));
            enemy_cities.extend(tr.cities.iter().filter(|c| F::is_tile_explored(s, c.idx, me)).map(|c| c.idx));
        }
    }
    let villages = s.tiles.iter().filter(|(k, t)| t.owner == 0 && F::is_city(s, **k) && F::is_tile_explored(s, **k, me)).map(|(k, _)| *k).collect();
    let mut srcs = std::collections::HashSet::new();
    for m in legal {
        if matches!(m.move_type(), MoveType::Step | MoveType::Attack | MoveType::Capture | MoveType::Ability) {
            if let Ok(i) = m.source_idx() { srcs.insert(i); }
        }
    }
    let tr = s.tribes.get(&me);
    let nu = tr.map_or(0, |t| t.units.len());
    let acted = tr.map_or(0, |t| t.units.iter().filter(|u| u.moved || u.attacked).count());
    let own_units: Vec<i32> = tr.map_or(vec![], |t| t.units.iter().map(|u| u.coords.idx).collect());
    let foe_near = own_units.iter().any(|&u| nearest(u, &foes, size) <= 3);
    let mut cap = [0f32; 5];
    if let Some(c) = F::get_capital_city(s, me) {
        for k in F::get_square_indices(c.idx, 1, size) {
            if let Some(t) = s.tiles.get(&k) {
                match t.terrain_type { TerrainType::Water | TerrainType::Ocean => cap[0] += 1.0, TerrainType::Forest | TerrainType::Mountain => cap[4] += 1.0, _ => {} }
            }
            match s.resources.get(&k).and_then(|r| r.as_ref()).map(|r| r.resource_type) {
                Some(ResourceType::Metal) => cap[1] += 1.0, Some(ResourceType::Fruit) => cap[2] += 1.0, Some(ResourceType::Game) => cap[3] += 1.0, _ => {}
            }
        }
    }
    let n_techs = tr.map_or(0, |t| t.tech_vanilla.len()) as f32;
    let cfeats: Feats = vec![
        ("frac_acted".into(), acted as f32 / (nu.max(1) as f32)),
        ("any_unit".into(), b(nu > 0)),
        ("foe_near".into(), b(foe_near)),
        ("cities".into(), tr.map_or(0.0, |t| t.cities.len() as f32) / 4.0),
        ("stars".into(), (tr.map_or(0, |t| t.stars) as f32 / 10.0).min(3.0)),
        ("turn".into(), (s.settings.turn as f32 / 20.0).min(1.5)),
        ("frac_left".into(), srcs.len() as f32 / (nu.max(1) as f32)),
        ("new_units".into(), tr.map_or(0, |t| t.units.iter().filter(|u| u.created_turn == s.settings.turn).count()) as f32 / 3.0),
    ];
    Ctx { me, turn: s.settings.turn, size, tribe: tr.map(|t| format!("{:?}", t.tribe_type)).unwrap_or_default(),
          foes, enemy_cities, villages, own_cities, units_left: srcs.len() as f32, cap, n_techs, cfeats }
}

/// The type a move names (structure, tech, unit, ability, reward), as in `api::label`.
pub fn named(mv: &dyn Move) -> String {
    mv.structure_type().map(|t| format!("{t:?}"))
        .or_else(|_| mv.tech_type().map(|t| format!("{t:?}")))
        .or_else(|_| mv.unit_type().map(|t| format!("{t:?}")))
        .or_else(|_| mv.ability_type().map(|t| format!("{t:?}")))
        .or_else(|_| mv.reward_type().map(|t| format!("{t:?}")))
        .unwrap_or_default()
}

/// Feature group of a move: the rule family (`api::kind`), the unit of per-type agreement reports.
pub fn group(mv: &dyn Move) -> String { api::kind(mv) }

fn b(x: bool) -> f32 { if x { 1.0 } else { 0.0 } }

/// Sparse features of one legal move in the position `g` (the mover is `ctx.me`).
pub fn features(g: &Game, ctx: &Ctx, mv: &dyn Move) -> Feats {
    let s = &g.state;
    let bk = bucket(ctx.turn);
    let kind = api::kind(mv);
    let nm = named(mv);
    let key = if nm.is_empty() || nm == kind { kind.clone() } else { format!("{kind}:{nm}") };
    let mut f: Feats = vec![(key.clone(), 1.0), (format!("{key}@b{bk}"), 1.0), (format!("{key}@{}", ctx.tribe), 1.0)];
    let src = mv.source_idx().ok().map(|x| x as i32);
    let tgt = mv.target_idx().ok().map(|x| x as i32);
    let unit = src.and_then(|i| F::get_unit_at(s, i));
    let in_city = src.map_or(false, |i| ctx.own_cities.contains(&i));
    match mv.move_type() {
        MoveType::Step => {
            if let (Some(a), Some(t)) = (src, tgt) {
                let gain = |set: &[i32]| (nearest(a, set, ctx.size) - nearest(t, set, ctx.size)) as f32;
                f.push(("Step.foe_gain".into(), gain(&ctx.foes)));
                f.push(("Step.village_gain".into(), gain(&ctx.villages)));
                f.push(("Step.enemycity_gain".into(), gain(&ctx.enemy_cities)));
                let dfoe = nearest(t, &ctx.foes, ctx.size);
                f.push(("Step.foe_adjacent".into(), b(dfoe <= 1)));
                f.push(("Step.foe_within3".into(), b(dfoe <= 3)));
                f.push(("Step.leaves_city".into(), b(in_city)));
                f.push(("Step.to_city".into(), b(ctx.own_cities.contains(&t))));
                // scouting: tiles around the destination this tribe has not explored yet
                let unexp = F::get_square_indices(t, 1, ctx.size).iter().filter(|&&k| !F::is_tile_explored(s, k, ctx.me)).count();
                f.push(("Step.unexplored".into(), unexp as f32 / 4.0));
                f.push(("Step.own_city_gain".into(), (nearest(a, &ctx.own_cities, ctx.size) - nearest(t, &ctx.own_cities, ctx.size)) as f32));
                if let Some(tl) = s.tiles.get(&t) {
                    f.push((format!("Step.ter:{:?}", tl.terrain_type), 1.0));
                    f.push(("Step.own_land".into(), b(tl.owner == ctx.me)));
                }
                if let Some(r) = F::get_resource_at(s, t) { f.push((format!("Step.res:{r:?}"), 1.0)); }
                if let Some(u) = unit {
                    let frac = u.health / F::get_unit_max_health(u).max(1.0);
                    f.push(("Step.hurt_x_foe_gain".into(), (1.0 - frac) * gain(&ctx.foes)));
                    f.push((format!("Step.u:{:?}", u.unit_type), 1.0));
                }
            }
        }
        MoveType::Attack => {
            if let (Some(a), Some(t)) = (src, tgt) {
                if let Some(p) = F::calculate_combat_preview(s, a, t) {
                    f.push(("Attack.kill".into(), b(p.defender_dies)));
                    f.push(("Attack.dmg".into(), p.damage_to_defender / 10.0));
                    f.push(("Attack.ret".into(), p.damage_to_attacker / 10.0));
                    f.push(("Attack.self_dies".into(), b(p.attacker_dies)));
                    f.push(("Attack.nokill_ret".into(), if p.defender_dies { 0.0 } else { p.damage_to_attacker / 10.0 }));
                    if let Some(d) = F::get_unit_at(s, t) {
                        f.push(("Attack.tgt_cost".into(), crate::settings::get_unit_setting(d.unit_type).cost as f32 / 5.0));
                        f.push(("Attack.tgt_on_city".into(), b(F::is_city(s, t))));
                    }
                }
                if let Some(u) = unit {
                    f.push(("Attack.from_city".into(), b(in_city)));
                    f.push((format!("Attack.u:{:?}", u.unit_type), 1.0));
                    f.push(("Attack.defender_nokill".into(), b(u.unit_type == UnitType::Defender)));
                }
            }
        }
        MoveType::Build | MoveType::Harvest => {
            if let Some(t) = tgt.or(src) {
                let r = F::get_resource_at(s, t).map(|r| format!("{r:?}")).unwrap_or_else(|| "None".into());
                f.push((format!("{key}*res:{r}"), 1.0));
                if let Some(tl) = s.tiles.get(&t) { f.push((format!("{key}*ter:{:?}", tl.terrain_type), 1.0)); }
                f.push((format!("{key}*cities"), ctx.cfeats[3].1));
            }
        }
        MoveType::Capture => {
            if let Some(a) = src.or(tgt) { f.push(("Capture.city".into(), b(F::is_city(s, a) && s.tiles.get(&a).map_or(false, |t| t.owner != 0)))); }
        }
        MoveType::Research => {
            // BOT-RESEARCH-OPENER inputs: what lies around the capital, crossed with the tech, while few techs are known
            let early = b(ctx.n_techs <= 2.0);
            for (name, x) in [("water", ctx.cap[0]), ("metal", ctx.cap[1]), ("fruit", ctx.cap[2]), ("game", ctx.cap[3]), ("rough", ctx.cap[4])] {
                f.push((format!("Rs:{nm}*{name}"), x.min(2.0) / 2.0 * early));
            }
            f.push((format!("Rs:{nm}*early"), early));
        }
        MoveType::EndTurn => f.push(("EndTurn.units_left".into(), ctx.units_left)),
        MoveType::Summon => {
            let near = ctx.own_cities.iter().any(|&c| src == Some(c) || tgt == Some(c));
            let _ = near;
            if let Some(c) = src.or(tgt) { f.push(("Train.foe_near".into(), b(nearest(c, &ctx.foes, ctx.size) <= 3))); }
            if let Ok(ut) = mv.unit_type() {
                let cost = crate::settings::get_unit_setting(ut).cost as f32;
                let stars = s.tribes.get(&ctx.me).map_or(0.0, |t| t.stars as f32);
                f.push(("Train.cost".into(), cost / 5.0));
                f.push(("Train.stars_left".into(), ((stars - cost) / 10.0).clamp(-1.0, 3.0)));
            }
        }
        _ => {}
    }
    f
}

/// Features of a whole move group at one decision (stage 1: which kind of move comes next): the group bias, by turn
/// bucket, the log count of its moves, each context feature crossed with the group, and the max over the group's moves
/// of every named move feature (`Attack.kill`, `Step.foe_gain`, ...; one-hots with ':' are skipped).
pub fn group_feats(ctx: &Ctx, g: &str, members: &[&Feats], present: &[String]) -> Feats {
    let mut f: Feats = vec![(format!("G:{g}"), 1.0), (format!("G:{g}@b{}", bucket(ctx.turn)), 1.0), (format!("G:{g}.n"), (1.0 + members.len() as f32).ln())];
    for (c, x) in &ctx.cfeats { f.push((format!("G:{g}*{c}"), *x)); }
    for h in present { if h != g { f.push((format!("G:{g}*has:{h}"), 1.0)); } }   // what else could be played now (an idle turn ends only when the economy is spent)
    let mut mx: Vec<(String, f32)> = Vec::new();
    for m in members {
        for (k, x) in m.iter() {
            if !k.contains('.') || k.contains(':') { continue; }
            match mx.iter_mut().find(|e| &e.0 == k) { Some(e) => { if *x > e.1 { e.1 = *x } } None => mx.push((k.clone(), *x)) }
        }
    }
    for (k, x) in mx { f.push((format!("Gmax:{k}"), x)); }
    f
}

/// Softmax over scores (temperature 1); returns probabilities.
pub fn softmax(scores: &[f32]) -> Vec<f32> {
    let m = scores.iter().cloned().fold(f32::NEG_INFINITY, f32::max);
    let e: Vec<f32> = scores.iter().map(|x| (x - m).exp()).collect();
    let z: f32 = e.iter().sum();
    e.into_iter().map(|x| x / z).collect()
}

// ---- decision dump (pfreplay, PF_BOTDUMP=file): one JSON line per logged action of any player ----

static TAG: std::sync::Mutex<String> = std::sync::Mutex::new(String::new());
static OUT: std::sync::Mutex<Option<std::fs::File>> = std::sync::Mutex::new(None);

pub fn set_tag(t: &str) { *TAG.lock().unwrap() = t.to_string(); }

pub fn dump_on() -> bool { std::env::var("PF_BOTDUMP").is_ok() }

/// {"tag","i","t","p","tr","bot","c" (chosen index in "m", -1 if the log's move was not in the list),"m":[[group, [[feature, value],...]], ...]}
pub fn dump(g: &Game, legal: &[Box<dyn Move>], chosen: Option<usize>, action_i: usize) {
    use std::io::Write;
    let Ok(path) = std::env::var("PF_BOTDUMP") else { return };
    let ctx = context(g, legal);
    let m: Vec<Value> = legal.iter().map(|mv| {
        let f: Vec<Value> = features(g, &ctx, mv.as_ref()).into_iter().map(|(k, x)| serde_json::json!([k, x])).collect();
        serde_json::json!([group(mv.as_ref()), f, mv.source_idx().map_or(-1, |x| x as i64), mv.target_idx().map_or(-1, |x| x as i64)])
    }).collect();
    let bot = g.state.tribes.get(&ctx.me).map_or(false, |t| t.bot);
    let line = serde_json::json!({"tag": *TAG.lock().unwrap(), "i": action_i, "t": ctx.turn, "p": ctx.me, "tr": ctx.tribe, "bot": bot,
                                  "c": chosen.map_or(-1, |c| c as i64), "x": ctx.cfeats, "m": m});
    let mut o = OUT.lock().unwrap();
    if o.is_none() { *o = std::fs::OpenOptions::new().create(true).append(true).open(path).ok(); }
    if let Some(f) = o.as_mut() { let _ = writeln!(f, "{line}"); }
}

// ---- the policy: stage 1 picks a move group, stage 2 a move inside it ----

/// File form: {"g": {stage-1 weights}, "w": {stage-2 weights}} (tools/bot_policy.py writes it).
#[derive(Default, Clone)]
pub struct Policy {
    pub g: Weights,
    pub w: Weights,
    /// {"rules": {"capture_first": p}}: with chance p a capture (village, city, ruin) is taken as soon as one is possible. Bots
    /// capture in 94% of the turns where one is possible (BOT-CAPTURE-FIRST), but per decision the softmax gives it only ~0.3.
    pub capture_first: f32,
}

impl Policy {
    pub fn from_file(path: &str) -> Result<Policy, String> {
        let v: Value = serde_json::from_str(&std::fs::read_to_string(path).map_err(|e| format!("{path}: {e}"))?).map_err(|e| format!("{path}: {e}"))?;
        let cf = v.pointer("/rules/capture_first").and_then(|x| x.as_f64()).unwrap_or(0.0) as f32;
        Ok(Policy { g: Weights::from_value(&v, "g")?, w: Weights::from_value(&v, "w")?, capture_first: cf })
    }
}

pub fn xorshift(s: &mut u64) -> f64 {
    *s ^= *s << 13; *s ^= *s >> 7; *s ^= *s << 17;
    (*s >> 11) as f64 / (1u64 << 53) as f64
}

fn pick(probs: &[f32], rng: &mut u64, sample: bool) -> usize {
    if !sample {
        return probs.iter().enumerate().fold((0, f32::NEG_INFINITY), |a, (i, &p)| if p > a.1 { (i, p) } else { a }).0;
    }
    let mut r = xorshift(rng) as f32;
    for (i, p) in probs.iter().enumerate() { if r < *p { return i; } r -= p; }
    probs.len() - 1
}

/// Index into `legal` of the move the policy plays. `sample`: draw from the two softmaxes; else argmax of each stage.
/// Resign is never chosen. Falls back to the first move if nothing else is possible.
pub fn choose(g: &Game, legal: &[Box<dyn Move>], pol: &Policy, rng: &mut u64, sample: bool) -> usize {
    let ctx = context(g, legal);
    let ok: Vec<usize> = (0..legal.len()).filter(|&i| legal[i].move_type() != MoveType::Resign).collect();
    if ok.is_empty() { return 0; }
    let feats: Vec<Feats> = ok.iter().map(|&i| features(g, &ctx, legal[i].as_ref())).collect();
    let mut groups: Vec<(String, Vec<usize>)> = Vec::new();   // group -> positions in `ok`
    for (p, &i) in ok.iter().enumerate() {
        let name = group(legal[i].as_ref());
        match groups.iter_mut().find(|e| e.0 == name) { Some(e) => e.1.push(p), None => groups.push((name, vec![p])) }
    }
    let names: Vec<String> = groups.iter().map(|e| e.0.clone()).collect();
    let gs: Vec<f32> = groups.iter().map(|(name, ps)| {
        let members: Vec<&Feats> = ps.iter().map(|&p| &feats[p]).collect();
        pol.g.score(&group_feats(&ctx, name, &members, &names))
    }).collect();
    let forced = if pol.capture_first > 0.0 { groups.iter().position(|e| e.0 == "Capture").filter(|_| xorshift(rng) < pol.capture_first as f64) } else { None };
    let gi = forced.unwrap_or_else(|| pick(&softmax(&gs), rng, sample));
    let ps = &groups[gi].1;
    let ms: Vec<f32> = ps.iter().map(|&p| pol.w.score(&feats[p])).collect();
    ok[ps[pick(&softmax(&ms), rng, sample)]]
}

/// Random-legal baseline (the same as the fm-accept playouts): EndTurn with chance 1/8, else a uniform non-EndTurn move.
pub fn choose_random(legal: &[Box<dyn Move>], rng: &mut u64) -> usize {
    let end = legal.iter().position(|m| m.move_type() == MoveType::EndTurn).unwrap_or(0);
    let others: Vec<usize> = (0..legal.len()).filter(|&i| !matches!(legal[i].move_type(), MoveType::EndTurn | MoveType::Resign)).collect();
    if others.is_empty() || xorshift(rng) < 0.125 { return end; }
    others[(xorshift(rng) * others.len() as f64) as usize % others.len()]
}
