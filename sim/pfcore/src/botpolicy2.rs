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
use crate::states::UnitState;
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
    /// v3: `crazy` adds the "C:"-prefixed delta weights (Crazy bots = the Hard fit + deltas); `has_c` says the table has any.
    pub fn score_c(&self, f: &Feats, crazy: bool, has_c: bool) -> f32 {
        let base = self.score(f);
        if !(crazy && has_c) { return base; }
        base + f.iter().map(|(k, x)| self.0.get(&format!("C:{k}")).copied().unwrap_or(0.0) * x).sum::<f32>()
    }
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
    // ---- v3 (bot-model-3); only filled when `ext` ----
    pub ext: bool,
    pub crazy: bool,          // the mover's DifficultyHandicap >= 4 (Crazy); Hard fit + "C:" deltas
    pub stars: f32,
    pub cheapest: f32,        // cost of the cheapest unit that can be trained now (0 if none)
    pub ruins: Vec<i32>,
    pub own_units: Vec<i32>,
    pub foe_info: Vec<(i32, f32, f32)>,   // enemy unit tile, attack, max-health-weighted strength
}

fn nearest(from: i32, set: &[i32], size: i32) -> i32 {
    set.iter().map(|&t| F::get_chebyshev_distance(from, t, size)).min().unwrap_or(15).min(15)
}

pub fn context(g: &Game, legal: &[Box<dyn Move>]) -> Ctx { context_x(g, legal, false) }

/// `ext`: also fill the v3 context (difficulty, spending, threat); v2 weights ignore the extra names.
pub fn context_x(g: &Game, legal: &[Box<dyn Move>], ext: bool) -> Ctx {
    let s = &g.state;
    let me = s.settings.current_player_turn_id;
    let size = s.settings.size;
    let mut foes = Vec::new();
    let mut foe_info: Vec<(i32, f32, f32)> = Vec::new();
    let mut enemy_cities = Vec::new();
    let mut own_cities = Vec::new();
    for (id, tr) in s.tribes.iter() {
        if *id == me { own_cities.extend(tr.cities.iter().map(|c| c.idx)); continue; }
        if F::is_enemy(s, me, *id) {
            foes.extend(tr.units.iter().map(|u| u.coords.idx));
            if ext { foe_info.extend(tr.units.iter().map(|u| (u.coords.idx, F::get_unit_attack(s, u), F::get_unit_attack(s, u) * u.health / 10.0))); }
            enemy_cities.extend(tr.cities.iter().filter(|c| F::is_tile_explored(s, c.idx, me)).map(|c| c.idx));
        }
    }
    // v2 looked for unowned *cities*; a free village is a tile with the Village structure (found in bot-model-3), so v2's village
    // features were constant 0. v3 (ext) uses the real villages; the v2 behaviour is kept for v2 weight files.
    let villages: Vec<i32> = if ext {
        s.tiles.iter().filter(|(k, t)| t.owner == 0 && F::get_structure_type_at(s, **k) == Some(StructureType::Village) && F::is_tile_explored(s, **k, me)).map(|(k, _)| *k).collect()
    } else {
        s.tiles.iter().filter(|(k, t)| t.owner == 0 && F::is_city(s, **k) && F::is_tile_explored(s, **k, me)).map(|(k, _)| *k).collect()
    };
    let ruins: Vec<i32> = if ext { s.tiles.keys().filter(|&&k| F::get_structure_type_at(s, k) == Some(StructureType::Ruin) && F::is_tile_explored(s, k, me)).cloned().collect() } else { vec![] };
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
    let mut cfeats: Feats = vec![
        ("frac_acted".into(), acted as f32 / (nu.max(1) as f32)),
        ("any_unit".into(), b(nu > 0)),
        ("foe_near".into(), b(foe_near)),
        ("cities".into(), tr.map_or(0.0, |t| t.cities.len() as f32) / 4.0),
        ("stars".into(), (tr.map_or(0, |t| t.stars) as f32 / 10.0).min(3.0)),
        ("turn".into(), (s.settings.turn as f32 / 20.0).min(1.5)),
        ("frac_left".into(), srcs.len() as f32 / (nu.max(1) as f32)),
        ("new_units".into(), tr.map_or(0, |t| t.units.iter().filter(|u| u.created_turn == s.settings.turn).count()) as f32 / 3.0),
    ];
    let stars = tr.map_or(0, |t| t.stars) as f32;
    let mut cheapest = 0f32;
    let mut crazy = false;
    if ext {
        cheapest = legal.iter().filter(|m| m.move_type() == MoveType::Summon).filter_map(|m| m.unit_type().ok())
            .map(|u| crate::settings::get_unit_setting(u).cost as f32).fold(f32::INFINITY, f32::min);
        if !cheapest.is_finite() { cheapest = 0.0; }
        crazy = tr.map_or(false, |t| t.handicap >= 4);
        let near_city = own_cities.iter().any(|&c| nearest(c, &foes, size) <= 2);
        let nfoe3 = foes.iter().filter(|&&f| own_units.iter().any(|&u| F::get_chebyshev_distance(u, f, size) <= 3)).count();
        let pop: i32 = tr.map_or(0, |t| t.cities.iter().map(|c| c.population).sum());
        let lvl: i32 = tr.map_or(0, |t| t.cities.iter().map(|c| c.level).sum());
        cfeats.extend(vec![
            ("crazy".into(), b(crazy)),
            ("n_units".into(), (nu as f32 / 8.0).min(2.0)),
            ("pop".into(), (pop as f32 / 10.0).min(3.0)),
            ("income".into(), (lvl as f32 / 6.0).min(3.0)),
            ("city_threat".into(), b(near_city)),
            ("n_foe_near".into(), (nfoe3 as f32 / 4.0).min(2.0)),
            ("afford_unit".into(), b(cheapest > 0.0)),
            ("stars_over_cheap".into(), if cheapest > 0.0 { ((stars - cheapest) / 10.0).clamp(-1.0, 3.0) } else { (stars / 10.0).min(3.0) }),
            ("n_enemy_cities".into(), (enemy_cities.len() as f32 / 4.0).min(2.0)),
            ("n_villages".into(), (villages.len() as f32 / 4.0).min(2.0)),
            ("turn2".into(), (s.settings.turn as f32 / 20.0).min(1.5).powi(2)),
        ]);
    }
    Ctx { me, turn: s.settings.turn, size, tribe: tr.map(|t| format!("{:?}", t.tribe_type)).unwrap_or_default(),
          foes, enemy_cities, villages, own_cities, units_left: srcs.len() as f32, cap, n_techs, cfeats,
          ext, crazy, stars, cheapest, foe_info, ruins, own_units: own_units.clone() }
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
    if ctx.ext { ext_features(g, ctx, mv, &key, &nm, src, tgt, unit, in_city, &mut f); }
    f
}

fn role(u: UnitType) -> &'static str {
    let st = crate::settings::get_unit_setting(u);
    if u == UnitType::Defender { "tank" } else if st.range > 1 { "ranged" } else if st.movement >= 2 { "fast" } else { "melee" }
}

/// v3 features (bot-model-3): threat, unit role, spending and difficulty-aware move features. New names only, so v2 weights ignore them.
#[allow(clippy::too_many_arguments)]
fn ext_features(g: &Game, ctx: &Ctx, mv: &dyn Move, key: &str, nm: &str, src: Option<i32>, tgt: Option<i32>, unit: Option<&UnitState>, in_city: bool, f: &mut Feats) {
    let s = &g.state;
    let threat = |t: i32| -> f32 { ctx.foe_info.iter().filter(|e| F::get_chebyshev_distance(e.0, t, ctx.size) <= 2).map(|e| e.2).sum::<f32>() / 3.0 };
    match mv.move_type() {
        MoveType::Step => {
            if let (Some(a), Some(t), Some(u)) = (src, tgt, unit) {
                let r = role(u.unit_type);
                let inv = |set: &[i32]| 1.0 / (1.0 + nearest(t, set, ctx.size) as f32);
                let gain = |set: &[i32]| (nearest(a, set, ctx.size) - nearest(t, set, ctx.size)) as f32;
                let vg = gain(&ctx.villages); let eg = gain(&ctx.enemy_cities); let fg = gain(&ctx.foes);
                f.push(("Step.vil_inv".into(), inv(&ctx.villages)));
                f.push(("Step.ecity_inv".into(), inv(&ctx.enemy_cities)));
                f.push(("Step.foe_inv".into(), inv(&ctx.foes)));
                f.push(("Step.on_village".into(), b(ctx.villages.contains(&t))));
                f.push(("Step.on_ruin".into(), b(ctx.ruins.contains(&t))));
                f.push(("Step.ruin_inv".into(), inv(&ctx.ruins)));
                // target claiming: is this unit the closest own unit to its nearest village / enemy city?
                for (nmx, set, gx) in [("vil", &ctx.villages, vg), ("ecity", &ctx.enemy_cities, eg)] {
                    if let Some(&tv) = set.iter().min_by_key(|&&x| F::get_chebyshev_distance(a, x, ctx.size)) {
                        let da = F::get_chebyshev_distance(a, tv, ctx.size);
                        let closest = ctx.own_units.iter().all(|&o| o == a || F::get_chebyshev_distance(o, tv, ctx.size) >= da);
                        f.push((format!("Step.{nmx}_gain_{}", if closest { "closest" } else { "other" }), gx));
                    }
                }
                f.push(("Step.on_ecity".into(), b(ctx.enemy_cities.contains(&t))));
                f.push((format!("Step.vil_gain@{r}"), vg));
                f.push((format!("Step.ecity_gain@{r}"), eg));
                f.push((format!("Step.foe_gain@{r}"), fg));
                f.push((format!("Step.unexplored@{r}"), F::get_square_indices(t, 1, ctx.size).iter().filter(|&&k| !F::is_tile_explored(s, k, ctx.me)).count() as f32 / 4.0));
                let th_t = threat(t); let th_a = threat(a);
                f.push(("Step.threat_dest".into(), th_t));
                f.push(("Step.threat_gain".into(), th_t - th_a));
                f.push(("Step.threat_from_city".into(), if in_city { th_a } else { 0.0 }));
                let my = crate::settings::get_unit_setting(u.unit_type);
                let rng = my.range.max(1);
                let tg = ctx.foe_info.iter().filter(|e| F::get_chebyshev_distance(e.0, t, ctx.size) <= rng).count();
                f.push(("Step.targets_next".into(), tg as f32 / 2.0));
                // nearest foe: is it stronger than this unit (attack x health)?
                let mine = my.attack * u.health / 10.0;
                if let Some(e) = ctx.foe_info.iter().min_by_key(|e| F::get_chebyshev_distance(e.0, a, ctx.size)) {
                    let stronger = e.2 > mine * 1.2;
                    f.push(("Step.foe_gain_stronger".into(), if stronger { fg } else { 0.0 }));
                    f.push(("Step.foe_gain_weaker".into(), if stronger { 0.0 } else { fg }));
                }
                if let Some(tl) = s.tiles.get(&t) {
                    let rough = matches!(tl.terrain_type, TerrainType::Forest | TerrainType::Mountain);
                    f.push(("Step.rough_x_threat".into(), b(rough) * th_t.min(2.0)));
                    f.push(("Step.rough".into(), b(rough)));
                }
                f.push(("Step.dist".into(), F::get_chebyshev_distance(a, t, ctx.size) as f32 / 3.0));
                let crowd = F::get_square_indices(t, 1, ctx.size).iter().filter(|&&k| k != a && F::get_unit_at(s, k).map_or(false, |x| x.owner == ctx.me)).count();
                f.push(("Step.crowd".into(), crowd as f32 / 3.0));
                let cap_cities = ctx.own_cities.contains(&a) as i32;
                f.push(("Step.city_left_empty".into(), (cap_cities as f32) * b(F::get_square_indices(a, 1, ctx.size).iter().all(|&k| F::get_unit_at(s, k).map_or(true, |x| x.owner != ctx.me)))));
                f.push(("Step.hurt".into(), 1.0 - u.health / F::get_unit_max_health(u).max(1.0)));
            }
        }
        MoveType::Attack => {
            if let (Some(a), Some(t)) = (src, tgt) {
                if let (Some(p), Some(d)) = (F::calculate_combat_preview(s, a, t), F::get_unit_at(s, t)) {
                    f.push(("Attack.ratio".into(), p.damage_to_defender / (p.damage_to_attacker + 2.0)));
                    f.push(("Attack.tgt_hp".into(), d.health / F::get_unit_max_health(d).max(1.0)));
                    f.push(("Attack.tgt_atk".into(), F::get_unit_attack(s, d) / 2.0));
                    f.push(("Attack.tgt_near_city".into(), b(nearest(t, &ctx.own_cities, ctx.size) <= 2)));
                    if let Some(u) = unit {
                        f.push(("Attack.value".into(), (crate::settings::get_unit_setting(d.unit_type).cost as f32 - crate::settings::get_unit_setting(u.unit_type).cost as f32) / 5.0));
                        f.push((format!("Attack.kill@{}", role(u.unit_type)), b(p.defender_dies)));
                    }
                }
            }
        }
        MoveType::Summon => {
            if let Ok(ut) = mv.unit_type() {
                let cost = crate::settings::get_unit_setting(ut).cost as f32;
                let own_t = s.tribes.get(&ctx.me).map_or(0, |t| t.units.iter().filter(|u| u.unit_type == ut).count());
                let nu = s.tribes.get(&ctx.me).map_or(0, |t| t.units.len());
                f.push((format!("Train.n_same@{ut:?}"), own_t as f32 / 3.0));
                f.push(("Train.n_same".into(), own_t as f32 / 3.0));
                f.push(("Train.n_units".into(), nu as f32 / 8.0));
                f.push(("Train.cheapest".into(), b((cost - ctx.cheapest).abs() < 0.5)));
                f.push(("Train.cost_over_stars".into(), cost / ctx.stars.max(1.0)));
                let c = src.or(tgt);
                if let Some(ci) = c.and_then(|c| F::get_city_at(s, c)) {
                    f.push(("Train.city_lvl".into(), ci.level as f32 / 3.0));
                    f.push(("Train.capital".into(), b(ci.connected_to_capital && ctx.own_cities.first() == Some(&ci.idx))));
                }
                let near = c.map_or(false, |c| nearest(c, &ctx.foes, ctx.size) <= 3);
                f.push((format!("Train.{ut:?}*foe_near"), b(near)));
                f.push((format!("Train.{ut:?}*stars"), (ctx.stars / 10.0).min(3.0)));
                f.push((format!("Train.{ut:?}*crazy"), b(ctx.crazy)));
                f.push((format!("Train.{ut:?}*cities"), ctx.cfeats[3].1));
            }
        }
        MoveType::Research => {
            if let (Ok(tt), Some(tr)) = (mv.tech_type(), s.tribes.get(&ctx.me)) {
                let cost = F::get_tech_cost(tr, tt) as f32;
                f.push(("Rs.cost".into(), cost / 20.0));
                f.push(("Rs.stars_left".into(), ((ctx.stars - cost) / 10.0).clamp(-1.0, 3.0)));
                f.push(("Rs.tier".into(), F::get_tech_tier(tt) as f32 / 3.0));
            }
        }
        MoveType::Build | MoveType::Harvest => {
            if mv.move_type() == MoveType::Build {
                if let Ok(st) = mv.structure_type() {
                    let cost = crate::settings::get_structure_setting(st).cost.unwrap_or(0) as f32;
                    f.push(("Build.cost".into(), cost / 5.0));
                    f.push(("Build.stars_left".into(), ((ctx.stars - cost) / 10.0).clamp(-1.0, 3.0)));
                    f.push((format!("Build.{st:?}*stars"), (ctx.stars / 10.0).min(3.0)));
                    if let Some(t) = tgt.or(src) {
                        let adj = F::get_square_indices(t, 1, ctx.size).iter().filter(|&&k| F::get_structure_type_at(s, k) == Some(st)).count();
                        f.push(("Build.adj_same".into(), adj as f32 / 2.0));
                    }
                }
            }
            let _ = (key, nm);
        }
        _ => {}
    }
}

/// Features of a whole move group at one decision (stage 1: which kind of move comes next): the group bias, by turn
/// bucket, the log count of its moves, each context feature crossed with the group, and the max over the group's moves
/// of every named move feature (`Attack.kill`, `Step.foe_gain`, ...; one-hots with ':' are skipped).
pub fn group_feats(ctx: &Ctx, g: &str, members: &[&Feats], present: &[String]) -> Feats {
    let mut f: Feats = vec![(format!("G:{g}"), 1.0), (format!("G:{g}@b{}", bucket(ctx.turn)), 1.0), (format!("G:{g}.n"), (1.0 + members.len() as f32).ln())];
    for (c, x) in &ctx.cfeats { f.push((format!("G:{g}*{c}"), *x)); }
    for h in present { if h != g { f.push((format!("G:{g}*has:{h}"), 1.0)); } }   // what else could be played now (an idle turn ends only when the economy is spent)
    if ctx.ext && g == "EndTurn" {   // spending: an idle turn ends when what is left to buy is not affordable / not wanted
        let st = (ctx.stars / 10.0).min(3.0);
        for h in present { if h != g { f.push((format!("G:EndTurn*has:{h}*stars"), st)); f.push((format!("G:EndTurn*has:{h}*acted"), ctx.cfeats[0].1)); } }
    }
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
    let ctx = context_x(g, legal, true);
    let fs: Vec<Feats> = legal.iter().map(|mv| features(g, &ctx, mv.as_ref())).collect();
    let m: Vec<Value> = legal.iter().zip(fs.iter()).map(|(mv, f)| {
        let f: Vec<Value> = f.iter().map(|(k, x)| serde_json::json!([k, x])).collect();
        serde_json::json!([group(mv.as_ref()), f, mv.source_idx().map_or(-1, |x| x as i64), mv.target_idx().map_or(-1, |x| x as i64)])
    }).collect();
    // stage-1 features per group, computed here so the Python fit never mirrors group_feats
    let mut names: Vec<String> = Vec::new();
    for mv in legal { let n = group(mv.as_ref()); if !names.contains(&n) { names.push(n); } }
    let gf: serde_json::Map<String, Value> = names.iter().map(|n| {
        let members: Vec<&Feats> = legal.iter().zip(fs.iter()).filter(|(mv, _)| &group(mv.as_ref()) == n).map(|(_, f)| f).collect();
        let f: Vec<Value> = group_feats(&ctx, n, &members, &names).into_iter().map(|(k, x)| serde_json::json!([k, x])).collect();
        (n.clone(), Value::Array(f))
    }).collect();
    let bot = g.state.tribes.get(&ctx.me).map_or(false, |t| t.bot);
    let line = serde_json::json!({"tag": *TAG.lock().unwrap(), "i": action_i, "t": ctx.turn, "p": ctx.me, "tr": ctx.tribe, "bot": bot,
                                  "c": chosen.map_or(-1, |c| c as i64), "h": g.state.tribes.get(&ctx.me).map_or(0, |t| t.handicap), "st": ctx.stars, "cheap": ctx.cheapest, "gf": gf, "m": m});
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
    /// v3 file ("ext": true): features use the real villages, threat and spending context (`context_x(.., true)`).
    pub ext: bool,
    /// {"rules": {"group_bias": {"EndTurn": -0.5, ...}}}: added to a group's stage-1 score; playout calibration (sequence effects the
    /// per-decision fit cannot see, e.g. a small EndTurn chance at every decision cuts turns short).
    pub group_bias: HashMap<String, f32>,
    pub has_c_g: bool,
    pub has_c_w: bool,
}

impl Policy {
    pub fn from_file(path: &str) -> Result<Policy, String> {
        let v: Value = serde_json::from_str(&std::fs::read_to_string(path).map_err(|e| format!("{path}: {e}"))?).map_err(|e| format!("{path}: {e}"))?;
        let cf = v.pointer("/rules/capture_first").and_then(|x| x.as_f64()).unwrap_or(0.0) as f32;
        let ext = v.get("ext").and_then(|x| x.as_bool()).unwrap_or(false);
        let (g, w) = (Weights::from_value(&v, "g")?, Weights::from_value(&v, "w")?);
        let (has_c_g, has_c_w) = (g.0.keys().any(|k| k.starts_with("C:")), w.0.keys().any(|k| k.starts_with("C:")));
        let group_bias = v.pointer("/rules/group_bias").and_then(|x| x.as_object()).map(|o| o.iter().filter_map(|(k, x)| x.as_f64().map(|x| (k.clone(), x as f32))).collect()).unwrap_or_default();
        Ok(Policy { g, w, capture_first: cf, ext, group_bias, has_c_g, has_c_w })
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
    let ctx = context_x(g, legal, pol.ext);
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
        pol.g.score_c(&group_feats(&ctx, name, &members, &names), ctx.crazy, pol.has_c_g) + pol.group_bias.get(name).copied().unwrap_or(0.0)
    }).collect();
    let forced = if pol.capture_first > 0.0 { groups.iter().position(|e| e.0 == "Capture").filter(|_| xorshift(rng) < pol.capture_first as f64) } else { None };
    let gi = forced.unwrap_or_else(|| pick(&softmax(&gs), rng, sample));
    let ps = &groups[gi].1;
    let ms: Vec<f32> = ps.iter().map(|&p| pol.w.score_c(&feats[p], ctx.crazy, pol.has_c_w)).collect();
    ok[ps[pick(&softmax(&ms), rng, sample)]]
}

/// Random-legal baseline (the same as the fm-accept playouts): EndTurn with chance 1/8, else a uniform non-EndTurn move.
pub fn choose_random(legal: &[Box<dyn Move>], rng: &mut u64) -> usize {
    let end = legal.iter().position(|m| m.move_type() == MoveType::EndTurn).unwrap_or(0);
    let others: Vec<usize> = (0..legal.len()).filter(|&i| !matches!(legal[i].move_type(), MoveType::EndTurn | MoveType::Resign)).collect();
    if others.is_empty() || xorshift(rng) < 0.125 { return end; }
    others[(xorshift(rng) * others.len() as f64) as usize % others.len()]
}
