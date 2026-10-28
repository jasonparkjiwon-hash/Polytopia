//! Belief sampler v1 (fog-inference, Phase 4 item 2): from a player's view of a save, sample plausible FULL states.
//! Every explored tile, every visible unit and city is kept exactly (`fog::player_view`); only what pov cannot see is drawn:
//!   1. hidden capitals (tribes without a visible capital): a free sector of the capital grid, a position inside it from the
//!      measured offsets, the 3x3 hidden, at least 4 apart; the capital city, its 3x3 border and a Warrior are added;
//!   2. terrain of the hidden tiles by Gibbs sampling a softmax model (fitted on other games' full maps) over neighbour
//!      counts, observed-region frequencies, edge and capital distance;
//!   3. resources from P(resource | terrain, near a capital);
//!   4. free villages (Poisson-disc, >= 3 apart; rate ~ Gamma posterior from the rate across games and the villages seen) and ruins.
//! `Mode::GlobalFreq` / `Mode::Uniform` are the baselines the sampler is scored against (tools/fog_eval: `pffog eval`).
//! Not modelled (see fog-inference.md): hidden enemy expansion cities, extra units, stars, techs, buildings, roads.
use crate::coords::Coords;
use crate::fog;
use crate::game::Game;
use crate::states::*;
use crate::types::*;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const NC: usize = 6; // Water, Ocean, Field, Forest, Mountain, Other (Ice, Wetland, ...)
pub const NR: usize = 10; // ResourceType 0..=9
const NF: usize = 29;
const KRAD: i32 = 8;

pub fn cls_of(t: TerrainType) -> usize {
    match t {
        TerrainType::Water => 0,
        TerrainType::Ocean => 1,
        TerrainType::Field => 2,
        TerrainType::Forest => 3,
        TerrainType::Mountain => 4,
        _ => 5,
    }
}
fn terrain_of(c: usize) -> TerrainType {
    [TerrainType::Water, TerrainType::Ocean, TerrainType::Field, TerrainType::Forest, TerrainType::Mountain, TerrainType::Ice][c.min(5)]
}
fn res_type(r: u8) -> Option<ResourceType> {
    use ResourceType::*;
    [Option::None, Some(Game), Some(Crop), Some(Fish), Option::None, Some(Metal), Some(Fruit), Some(Spores), Some(Starfish), Some(AquaCrop)].get(r as usize).copied().flatten()
}
fn is_land(c: usize) -> bool {
    (2..=4).contains(&c)
}
fn cheb(n: i32, a: i32, b: i32) -> i32 {
    ((a % n - b % n).abs()).max((a / n - b / n).abs())
}

/// splitmix64 + helpers; deterministic per seed.
pub struct Rng(pub u64);
impl Rng {
    pub fn u64(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E3779B97F4A7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB);
        z ^ (z >> 31)
    }
    pub fn f(&mut self) -> f64 {
        (self.u64() >> 11) as f64 / (1u64 << 53) as f64
    }
    pub fn below(&mut self, n: usize) -> usize {
        (self.f() * n as f64) as usize % n.max(1)
    }
    fn normal(&mut self) -> f64 {
        let (u, v) = (self.f().max(1e-12), self.f());
        (-2.0 * u.ln()).sqrt() * (2.0 * std::f64::consts::PI * v).cos()
    }
    pub fn gamma(&mut self, a: f64, b: f64) -> f64 {
        // Marsaglia-Tsang, rate b
        if a < 1.0 {
            return self.gamma(a + 1.0, b) * self.f().max(1e-12).powf(1.0 / a);
        }
        let d = a - 1.0 / 3.0;
        let c = 1.0 / (9.0 * d).sqrt();
        loop {
            let x = self.normal();
            let v = (1.0 + c * x).powi(3);
            if v <= 0.0 {
                continue;
            }
            if self.f().max(1e-12).ln() < 0.5 * x * x + d - d * v + d * v.ln() {
                return d * v / b;
            }
        }
    }
    pub fn poisson(&mut self, l: f64) -> usize {
        let (el, mut k, mut p) = ((-l).exp(), 0, 1.0);
        loop {
            p *= self.f();
            if p <= el || k > 400 {
                return k;
            }
            k += 1;
        }
    }
    pub fn pick(&mut self, w: &[f64]) -> usize {
        let t: f64 = w.iter().sum();
        let mut r = self.f() * t;
        for (i, x) in w.iter().enumerate() {
            r -= x;
            if r <= 0.0 {
                return i;
            }
        }
        w.len() - 1
    }
}

/// What a full game says about the map, flat by tile index (the unit of both training and scoring).
pub struct MapView {
    pub n: i32,
    pub turn: i32,
    pub players: usize,
    pub cls: Vec<u8>,
    pub res: Vec<u8>,
    /// a Village structure on a tile that is no capital (free village or a captured/founded city)
    pub village: Vec<bool>,
    pub ruin: Vec<bool>,
    /// tribe whose capital stands on the tile (0 none)
    pub cap: Vec<i32>,
    pub explored: BTreeMap<i32, Vec<bool>>,
}
impl MapView {
    pub fn from_game(g: &Game) -> MapView {
        let n = g.state.settings.size;
        let nn = (n * n) as usize;
        let mut m = MapView { n, turn: g.state.settings.turn, players: g.state.tribes.len(), cls: vec![5; nn], res: vec![0; nn], village: vec![false; nn], ruin: vec![false; nn], cap: vec![0; nn], explored: BTreeMap::new() };
        for (i, t) in g.state.tiles.iter() {
            m.cls[*i as usize] = cls_of(t.terrain_type) as u8;
            m.cap[*i as usize] = t.capital_of;
        }
        for (i, r) in g.state.resources.iter() {
            if let Some(r) = r {
                m.res[*i as usize] = (r.resource_type as u8).min(NR as u8 - 1);
            }
        }
        for (i, s) in g.state.structures.iter() {
            if let Some(s) = s {
                match s.structure_type {
                    StructureType::Village if m.cap[*i as usize] == 0 => m.village[*i as usize] = true,
                    StructureType::Ruin => m.ruin[*i as usize] = true,
                    _ => {}
                }
            }
        }
        for p in g.state.tribes.keys() {
            m.explored.insert(*p, (0..nn as i32).map(|i| g.state.tiles.get(&i).map_or(false, |t| t.explorers.contains(p))).collect());
        }
        m
    }
}

#[derive(Serialize, Deserialize, Clone, Default)]
pub struct Model {
    /// softmax weights, NC rows of NF
    pub w: Vec<Vec<f32>>,
    /// global class frequency (all tiles) and observed-resource table [inner][class][res]
    pub class_freq: Vec<f64>,
    pub res: Vec<Vec<Vec<f64>>>,
    pub res_global: Vec<f64>,
    /// free-village rate per eligible land tile across games: gamma prior (shape, rate)
    pub vil_prior: (f64, f64),
    /// lower end of the share of packing spots that hold a village (VILLAGE-PACK); each sample draws its share from [this, 1]
    #[serde(default = "one")]
    pub vil_fill: f64,
    pub vil_terrain_w: Vec<f64>,
    /// ruins per hidden tile by turn bucket (<=3, 4..=8, 9+) and class weights
    pub ruin_rate: Vec<f64>,
    pub ruin_class_w: Vec<f64>,
    /// capital positions inside their sector, as fractions (fx, fy)
    pub cap_frac: Vec<(f32, f32)>,
    /// neighbour-feature scale used when sampling (0 = independent tiles, 1 = the fitted coupling)
    pub tau: f32,
    /// training summary: maps, (save, pov) pairs, examples, sector-occupancy check
    pub notes: String,
}

#[derive(Clone, Copy, PartialEq, Debug)]
pub enum Mode {
    Full,
    GlobalFreq,
    Uniform,
}

fn one() -> f64 { 0.9 }
fn grid_k(players: usize) -> i32 {
    (players as f64).sqrt().ceil() as i32
}
fn sector_of(n: i32, k: i32, idx: i32) -> (i32, i32) {
    (((idx % n) * k / n), ((idx / n) * k / n))
}
fn turn_bucket(t: i32) -> usize {
    if t <= 3 { 0 } else if t <= 8 { 1 } else { 2 }
}
fn eligible_land(m_cls: &[u8], n: i32, i: i32) -> bool {
    let (x, y) = (i % n, i / n);
    // villages stand from the second ring in (x = 0 never; ring 1 holds 22% of the hidden villages in the 3 test games)
    x >= 1 && y >= 1 && x <= n - 2 && y <= n - 2 && is_land(m_cls[i as usize] as usize)
}

struct Ctx<'a> {
    n: i32,
    obs: &'a [bool],
    cls: Vec<u8>,
    capd: Vec<u8>,
    glob: [f32; 5],
}
impl<'a> Ctx<'a> {
    fn new(n: i32, obs: &'a [bool], cls: Vec<u8>, caps: &[i32]) -> Ctx<'a> {
        let nn = (n * n) as usize;
        let mut c = Ctx { n, obs, cls, capd: vec![9; nn], glob: [0.2; 5] };
        c.set_caps(caps);
        let mut cnt = [0.5f32; 5];
        for i in 0..nn {
            if obs[i] && c.cls[i] < 5 {
                cnt[c.cls[i] as usize] += 1.0;
            }
        }
        let s: f32 = cnt.iter().sum();
        for k in 0..5 {
            c.glob[k] = cnt[k] / s;
        }
        c
    }
    fn set_caps(&mut self, caps: &[i32]) {
        let n = self.n;
        for d in self.capd.iter_mut() {
            *d = 9;
        }
        for &cp in caps {
            for dy in -5..=5 {
                for dx in -5..=5 {
                    let (x, y) = (cp % n + dx, cp / n + dy);
                    if x >= 0 && y >= 0 && x < n && y < n {
                        let d = dx.abs().max(dy.abs()) as u8;
                        let j = (y * n + x) as usize;
                        self.capd[j] = self.capd[j].min(d);
                    }
                }
            }
        }
    }
    /// observed-region class frequencies around tile i (kernel exp(-d/3), radius KRAD), excluding i
    fn kern(&self, i: i32) -> [f32; 5] {
        let n = self.n;
        let (x0, y0) = (i % n, i / n);
        let mut k = [0.02f32; 5];
        for dy in -KRAD..=KRAD {
            for dx in -KRAD..=KRAD {
                let (x, y) = (x0 + dx, y0 + dy);
                if (dx == 0 && dy == 0) || x < 0 || y < 0 || x >= n || y >= n {
                    continue;
                }
                let j = (y * n + x) as usize;
                if self.obs[j] && self.cls[j] < 5 {
                    k[self.cls[j] as usize] += (-(dx.abs().max(dy.abs()) as f32) / 3.0).exp();
                }
            }
        }
        let s: f32 = k.iter().sum();
        for v in k.iter_mut() {
            *v /= s;
        }
        k
    }
    fn feats(&self, i: i32, kern: &[f32; 5]) -> [f32; NF] {
        let n = self.n;
        let (x0, y0) = (i % n, i / n);
        let mut f = [0f32; NF];
        for dy in -2i32..=2 {
            for dx in -2i32..=2 {
                let (x, y) = (x0 + dx, y0 + dy);
                if (dx == 0 && dy == 0) || x < 0 || y < 0 || x >= n || y >= n {
                    continue;
                }
                let c = self.cls[(y * n + x) as usize] as usize;
                if c < 5 {
                    f[c + if dx.abs().max(dy.abs()) == 1 { 0 } else { 5 }] += 1.0 / if dx.abs().max(dy.abs()) == 1 { 4.0 } else { 8.0 };
                }
            }
        }
        for k in 0..5 {
            f[10 + k] = kern[k];
            f[15 + k] = 0.0 * self.glob[k]; // global fractions identify the game (only ~10 games to learn from): left out
        }
        f[20 + (x0.min(y0).min(n - 1 - x0).min(n - 1 - y0)).min(2) as usize] = 1.0;
        f[23 + match self.capd[i as usize] { 0 => 0, 1 => 1, 2 => 2, 3 | 4 => 3, _ => 4 }] = 1.0;
        f[28] = 1.0;
        f
    }
}

fn softmax(w: &[Vec<f32>], f: &[f32; NF]) -> [f64; NC] {
    let mut z = [0f64; NC];
    for c in 0..NC {
        z[c] = w[c].iter().zip(f.iter()).map(|(a, b)| (*a * *b) as f64).sum();
    }
    let m = z.iter().cloned().fold(f64::MIN, f64::max);
    let mut s = 0.0;
    for v in z.iter_mut() {
        *v = (*v - m).exp();
        s += *v;
    }
    for v in z.iter_mut() {
        *v /= s;
    }
    z
}

fn fit(ex: &mut Vec<([f32; NF], u8)>, w: &mut Vec<Vec<f32>>, cols: std::ops::Range<usize>, zero_nb: bool, rng: &mut Rng) {
    let (mut mm, mut vv) = (vec![vec![0f32; NF]; NC], vec![vec![0f32; NF]; NC]);
    let mut step = 0;
    for _epoch in 0..14 {
        for i in (1..ex.len()).rev() {
            ex.swap(i, rng.below(i + 1));
        }
        for batch in ex.chunks(256) {
            let mut g = vec![vec![0f32; NF]; NC];
            for (f0, y) in batch {
                let mut f = *f0;
                if zero_nb {
                    for j in 0..10 { f[j] = 0.0; }
                }
                let p = softmax(w, &f);
                for c in 0..NC {
                    let d = (p[c] as f32) - if *y as usize == c { 1.0 } else { 0.0 };
                    for j in cols.clone() {
                        g[c][j] += d * f[j];
                    }
                }
            }
            step += 1;
            for c in 0..NC {
                for j in cols.clone() {
                    let gr = g[c][j] / batch.len() as f32 + 1e-4 * w[c][j];
                    mm[c][j] = 0.9 * mm[c][j] + 0.1 * gr;
                    vv[c][j] = 0.999 * vv[c][j] + 0.001 * gr * gr;
                    let (mh, vh) = (mm[c][j] / (1.0 - 0.9f32.powi(step)), vv[c][j] / (1.0 - 0.999f32.powi(step)));
                    w[c][j] -= 0.03 * mh / (vh.sqrt() + 1e-8);
                }
            }
        }
    }
}

/// Fit the model on full maps. `maps` are (MapView) of saves; every (map, pov) pair contributes up to 200 hidden tiles.
pub fn train(maps: &[MapView], seed: u64) -> Model {
    let mut rng = Rng(seed);
    let mut m = Model { w: vec![vec![0.0; NF]; NC], tau: 0.3, ..Default::default() };
    let mut ex: Vec<([f32; NF], u8)> = Vec::new();
    let mut pairs = 0;
    let mut cfreq = vec![1.0f64; NC];
    let mut res_t = vec![vec![vec![0.5f64; NR]; NC]; 2];
    let mut rg = vec![0.5f64; NR];
    let (mut rates, mut vcls, mut lcls) = (vec![], vec![0.5f64; NC], vec![0.5f64; NC]);
    let (mut ruin_n, mut ruin_h) = (vec![0.0f64; 3], vec![1.0f64; 3]);
    let mut rcls = vec![0.5f64; NC];
    let mut allcls = vec![1.0f64; NC];
    let (mut sec_ok, mut sec_all) = (0, 0);
    for mv in maps {
        let n = mv.n;
        let caps: Vec<i32> = (0..(n * n)).filter(|&i| mv.cap[i as usize] > 0).collect();
        // sector occupancy (assumption of the capital model)
        let k = grid_k(mv.players);
        let mut occ = std::collections::HashSet::new();
        let mut ok = true;
        for &c in &caps {
            ok &= occ.insert(sector_of(n, k, c));
        }
        sec_all += 1;
        sec_ok += ok as usize;
        for &c in &caps {
            let (sx, sy) = sector_of(n, k, c);
            let (cx, cy) = (c % n, c / n);
            m.cap_frac.push((((cx * k) as f32 / n as f32) - sx as f32, ((cy * k) as f32 / n as f32) - sy as f32));
        }
        let (mut settle, mut elig) = (0.0f64, 0.0f64);
        let mut nearcap = vec![false; (n * n) as usize];
        for &c in &caps {
            for i in 0..n * n {
                if cheb(n, c, i) <= 2 {
                    nearcap[i as usize] = true;
                }
            }
        }
        for i in 0..(n * n) as usize {
            let c = mv.cls[i] as usize;
            cfreq[c] += 1.0;
            allcls[c] += 1.0;
            res_t[nearcap[i] as usize][c][mv.res[i] as usize] += 1.0;
            rg[mv.res[i] as usize] += 1.0;
            if eligible_land(&mv.cls, n, i as i32) {
                elig += 1.0;
                lcls[c] += 1.0;
            }
            if mv.village[i] {
                settle += 1.0;
                vcls[c] += 1.0;
            }
            if mv.ruin[i] {
                rcls[c] += 1.0;
            }
        }
        rates.push(settle / elig.max(1.0));
        let tb = turn_bucket(mv.turn);
        ruin_n[tb] += mv.ruin.iter().filter(|&&r| r).count() as f64;
        ruin_h[tb] += (n * n) as f64;
        for (pov, obs) in mv.explored.iter() {
            let _ = pov;
            pairs += 1;
            let ctx = Ctx::new(n, obs, mv.cls.clone(), &caps);
            let hidden: Vec<i32> = (0..n * n).filter(|&i| !obs[i as usize]).collect();
            if hidden.is_empty() || obs.iter().filter(|&&o| o).count() < 9 {
                continue;
            }
            for _ in 0..200.min(hidden.len()) {
                let i = hidden[rng.below(hidden.len())];
                let kern = ctx.kern(i);
                ex.push((ctx.feats(i, &kern), mv.cls[i as usize]));
            }
        }
    }
    // two stages: marginal part (observed-region context, edge, capital distance) first, then the neighbour columns on top
    for (cols, zero_nb) in [(10..NF, true), (0..10, false)] {
        fit(&mut ex, &mut m.w, cols, zero_nb, &mut rng);
    }
    let norm = |v: &Vec<f64>| -> Vec<f64> { let s: f64 = v.iter().sum(); v.iter().map(|x| x / s).collect() };
    m.class_freq = norm(&cfreq);
    m.res = res_t.iter().map(|t| t.iter().map(norm).collect()).collect();
    m.res_global = norm(&rg);
    let mean = rates.iter().sum::<f64>() / rates.len() as f64;
    let var = (rates.iter().map(|r| (r - mean).powi(2)).sum::<f64>() / rates.len() as f64).max((0.3 * mean).powi(2));
    m.vil_fill = 0.9;
    m.vil_prior = (mean * mean / var, mean / var);
    m.vil_terrain_w = (0..NC).map(|c| (vcls[c] / vcls.iter().sum::<f64>()) / (lcls[c] / lcls.iter().sum::<f64>())).collect();
    m.ruin_rate = (0..3).map(|b| ruin_n[b] / ruin_h[b]).collect();
    m.ruin_class_w = (0..NC).map(|c| (rcls[c] / rcls.iter().sum::<f64>()) / (allcls[c] / allcls.iter().sum::<f64>())).collect();
    m.notes = format!("{} maps, {} (map,pov) pairs, {} examples; capital sector grid holds one capital per sector in {}/{} maps; villages/eligible land {:.3}±{:.3}", maps.len(), pairs, ex.len(), sec_ok, sec_all, mean, var.sqrt());
    m
}

/// Sample one plausible full game consistent with pov's view of `g` (the full game from a save).
pub fn sample_belief(g: &Game, pov: i32, model: &Model, mode: Mode, seed: u64) -> Game {
    let mut rng = Rng(seed ^ 0xA5A5_1234_5678_9ABC);
    let mut v = fog::player_view(g, pov);
    let n = v.state.settings.size;
    let nn = (n * n) as usize;
    let obs: Vec<bool> = (0..nn as i32).map(|i| v.state.tiles.get(&i).map_or(false, |t| t.explorers.contains(&pov))).collect();
    let turn = v.state.settings.turn;
    let players = v.state.tribes.len();
    // known capitals (visible tiles) and the tribes that still need one
    let known_caps: Vec<i32> = (0..nn as i32).filter(|&i| obs[i as usize] && v.state.tiles.get(&i).map_or(0, |t| t.capital_of) > 0).collect();
    let need: Vec<i32> = v.state.tribes.iter().filter(|(id, t)| **id != pov && t.killed_turn == 0 && !known_caps.iter().any(|&c| v.state.tiles[&c].capital_of == **id)).map(|(id, _)| *id).collect();
    // 1. hidden capitals
    let k = grid_k(players);
    let mut used: Vec<(i32, i32)> = known_caps.iter().map(|&c| sector_of(n, k, c)).collect();
    if let Some(own) = v.state.tribes.get(&pov).and_then(|t| t.cities.first()) {
        let s = sector_of(n, k, own.idx);
        if !used.contains(&s) { used.push(s); }
    }
    let mut caps: Vec<i32> = known_caps.clone();
    let mut placed: Vec<(i32, i32)> = vec![]; // (tribe, tile)
    let ok_tile = |c: i32, caps: &Vec<i32>, obs: &Vec<bool>| -> bool {
        let (x, y) = (c % n, c / n);
        (-1..=1).all(|dy| (-1..=1).all(|dx| { let (a, b) = (x + dx, y + dy); a >= 0 && b >= 0 && a < n && b < n && !obs[(b * n + a) as usize] }))
            && caps.iter().all(|&o| cheb(n, o, c) >= 4)
    };
    for &tribe in &need {
        let free: Vec<(i32, i32)> = (0..k).flat_map(|a| (0..k).map(move |b| (a, b))).filter(|s| !used.contains(s)).collect();
        let mut chosen = None;
        for _try in 0..400 {
            let c = if mode == Mode::Full && !free.is_empty() && !model.cap_frac.is_empty() {
                let s = free[rng.below(free.len())];
                let f = model.cap_frac[rng.below(model.cap_frac.len())];
                let x = (((s.0 as f32 + f.0) * n as f32 / k as f32) as i32).clamp(1, n - 2);
                let y = (((s.1 as f32 + f.1) * n as f32 / k as f32) as i32).clamp(1, n - 2);
                y * n + x
            } else {
                (rng.below(((n - 2) * (n - 2)) as usize) as i32 / (n - 2) + 1) * n + (rng.below((n - 2) as usize) as i32 + 1)
            };
            if ok_tile(c, &caps, &obs) {
                chosen = Some(c);
                break;
            }
        }
        let c = chosen.unwrap_or_else(|| (0..nn as i32).find(|&c| ok_tile(c, &caps, &obs)).unwrap_or(0));
        used.push(sector_of(n, k, c));
        caps.push(c);
        placed.push((tribe, c));
    }
    // 2. terrain
    let mut cls: Vec<u8> = (0..nn as i32).map(|i| v.state.tiles.get(&i).map_or(5, |t| cls_of(t.terrain_type)) as u8).collect();
    let hidden: Vec<i32> = (0..nn as i32).filter(|&i| !obs[i as usize]).collect();
    let mut ctx = Ctx::new(n, &obs, cls.clone(), &caps);
    let kerns: BTreeMap<i32, [f32; 5]> = hidden.iter().map(|&i| (i, ctx.kern(i))).collect();
    let draw = |ctx: &Ctx, i: i32, rng: &mut Rng| -> u8 {
        let mut c = match mode {
            Mode::Full => { let mut f = ctx.feats(i, &kerns[&i]); for j in 0..10 { f[j] *= model.tau; } rng.pick(&softmax(&model.w, &f)) as u8 }
            Mode::GlobalFreq => rng.pick(&model.class_freq) as u8,
            Mode::Uniform => rng.below(5) as u8,
        };
        if ctx.capd[i as usize] == 0 && !is_land(c as usize) {
            c = 2;
        }
        c
    };
    for &i in &hidden {
        ctx.cls[i as usize] = rng.pick(&ctx.glob.iter().map(|x| *x as f64).collect::<Vec<_>>()) as u8;
    }
    for _sweep in 0..if mode == Mode::Full { 15 } else { 1 } {
        let mut order = hidden.clone();
        for j in (1..order.len()).rev() {
            order.swap(j, rng.below(j + 1));
        }
        for &i in &order {
            let c = draw(&ctx, i, &mut rng);
            ctx.cls[i as usize] = c;
        }
    }
    cls.clone_from(&ctx.cls);
    // 3. resources, 4. villages and ruins
    let mut res = vec![0u8; nn];
    for &i in &hidden {
        let near = ctx.capd[i as usize] <= 2;
        let p: &[f64] = if mode == Mode::Full { &model.res[near as usize][cls[i as usize] as usize] } else { &model.res_global };
        res[i as usize] = if mode == Mode::Uniform { rng.below(NR) as u8 } else { rng.pick(p) as u8 };
    }
    let mut settle: Vec<i32> = caps.clone();
    let mut obs_vil = 0.0;
    for i in 0..nn as i32 {
        let is_village = v.state.structures.get(&i).and_then(|s| s.as_ref()).map_or(false, |s| s.structure_type == StructureType::Village);
        if obs[i as usize] && is_village {
            settle.push(i);
            if v.state.tiles[&i].capital_of == 0 { obs_vil += 1.0; }
        }
    }
    let elig_obs = (0..nn as i32).filter(|&i| obs[i as usize] && eligible_land(&cls, n, i)).count() as f64;
    let mut vil: Vec<i32> = vec![];
    let cand: Vec<i32> = hidden.iter().copied().filter(|&i| eligible_land(&cls, n, i)).collect();
    // Villages: random sequential packing of the hidden interior land (VILLAGE-PACK, polyvision-maps.md): every settlement spot is
    // taken at turn 0, so a hidden spot (Chebyshev >= 3 from every known/sampled settlement and from each other) is a village or an
    // enemy city, never empty. A Poisson rate by eligible tile (the old way) gave a bias of -12.6 villages (90% interval covers 0.21).
    let _ = (obs_vil, elig_obs);
    // the share of packing spots that really hold a village varies by game (captured, razed or never-founded spots): drawn per sample
    let lo: f64 = std::env::var("VIL_LO").ok().and_then(|v| v.parse().ok()).unwrap_or(model.vil_fill);
    let fill: f64 = lo + (1.0 - lo) * rng.f();
    let mut pool = cand;
    let pack = std::env::var("VIL_PACK").map_or(true, |v| v != "0"); // VIL_PACK=0: the old Poisson count (bias -8.3 with the edge fix, -12.6 before)
    if !pack {
        let rate = rng.gamma(model.vil_prior.0, model.vil_prior.1);
        let kv = rng.poisson(rate * pool.len() as f64);
        for _ in 0..kv {
            let w: Vec<f64> = pool.iter().map(|&i| if settle.iter().all(|&s| cheb(n, s, i) >= 3) { if mode == Mode::Full { model.vil_terrain_w[cls[i as usize] as usize] } else { 1.0 } } else { 0.0 }).collect();
            if w.iter().sum::<f64>() <= 0.0 { break; }
            let i = pool[rng.pick(&w)];
            settle.push(i);
            vil.push(i);
            pool.retain(|&j| j != i);
        }
    } else {
        let use_w = mode == Mode::Full && std::env::var("VIL_W").map_or(true, |v| v != "0");
        loop {
            let w: Vec<f64> = pool.iter().map(|&i| if settle.iter().all(|&s| cheb(n, s, i) >= 3) { if use_w { model.vil_terrain_w[cls[i as usize] as usize] } else { 1.0 } } else { 0.0 }).collect();
            if w.iter().sum::<f64>() <= 0.0 { break; }
            let i = pool[rng.pick(&w)];
            pool.retain(|&j| j != i);
            if rng.f() < fill { settle.push(i); vil.push(i); }
        }
    }
    let rr = rng.poisson(model.ruin_rate[turn_bucket(turn)] * hidden.len() as f64);
    let mut ruins: Vec<i32> = vec![];
    for _ in 0..rr {
        let w: Vec<f64> = hidden.iter().map(|&i| {
            let (x, y) = (i % n, i / n);
            let corner = (x == 0 || x == n - 1) && (y == 0 || y == n - 1);
            if corner || settle.iter().any(|&s| cheb(n, s, i) < 2) || ruins.contains(&i) { 0.0 } else if mode == Mode::Full { model.ruin_class_w[cls[i as usize] as usize] } else { 1.0 }
        }).collect();
        if w.iter().sum::<f64>() <= 0.0 { break; }
        ruins.push(hidden[rng.pick(&w)]);
    }
    // write into the game
    for &i in &hidden {
        if let Some(t) = v.state.tiles.get_mut(&i) {
            t.terrain_type = terrain_of(cls[i as usize] as usize);
        }
        v.state.resources.insert(i, if res[i as usize] == 0 { None } else { res_type(res[i as usize]).map(|r| ResourceState { resource_type: r }) });
        v.state.structures.insert(i, None);
    }
    for &i in &vil {
        v.state.structures.insert(i, Some(StructureState { structure_type: StructureType::Village, level: 1, founded: 0 }));
    }
    for &i in &ruins {
        v.state.structures.insert(i, Some(StructureState { structure_type: StructureType::Ruin, level: 1, founded: 0 }));
    }
    for &(tribe, c) in &placed {
        let cc = Coords::from_index(c, n);
        for dy in -1..=1 {
            for dx in -1..=1 {
                if let Some(t) = v.state.tiles.get_mut(&((cc.y + dy) * n + cc.x + dx)) {
                    t.owner = tribe;
                    t.ruling_city_coords = Some(cc);
                }
            }
        }
        if let Some(t) = v.state.tiles.get_mut(&c) {
            t.capital_of = tribe;
            t._unit_owner_id = Some(tribe);
        }
        v.state.resources.insert(c, None);
        v.state.structures.insert(c, Some(StructureState { structure_type: StructureType::Village, level: 1, founded: 0 }));
        if let Some(tr) = v.state.tribes.get_mut(&tribe) {
            tr.cities.push(CityState { owner: tribe, idx: c, level: 1, production: 1, population: 0, border_size: 1, ..Default::default() });
            tr.units.push(UnitState { owner: tribe, unit_type: UnitType::Warrior, coords: cc, prev_coords: cc, home_coords: Some(cc), health: 10.0, ..Default::default() });
        }
    }
    v
}

/// Diagnostic: mean ln p(true class) over pov's hidden tiles, one tile at a time given the TRUE neighbours (what the Gibbs
/// conditionals can reach at best), and with the neighbour features zeroed (observed-region context only). Also the
/// per-map village rate stats. Returns (with neighbours, without, tiles).
pub fn diag(model: &Model, mv: &MapView, pov: i32) -> (f64, f64, usize) {
    let obs = &mv.explored[&pov];
    let caps: Vec<i32> = (0..mv.n * mv.n).filter(|&i| mv.cap[i as usize] > 0).collect();
    let ctx = Ctx::new(mv.n, obs, mv.cls.clone(), &caps);
    let (mut a, mut b, mut c) = (0.0, 0.0, 0);
    for i in 0..mv.n * mv.n {
        if obs[i as usize] { continue; }
        let kern = ctx.kern(i);
        let mut f = ctx.feats(i, &kern);
        let y = mv.cls[i as usize] as usize;
        a += softmax(&model.w, &f)[y].max(1e-9).ln();
        for j in 0..10 { f[j] = 0.0; }
        b += softmax(&model.w, &f)[y].max(1e-9).ln();
        c += 1;
    }
    (a, b, c)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Skipped without decoded saves. The sample keeps every explored tile and visible unit/city and adds the hidden capitals.
    #[test]
    fn sample_keeps_what_pov_sees() {
        let path = format!("{}/../../saves/ed6cb932-c741-4ba8-9fd3-66f5c3f6bad7_t5.json", env!("CARGO_MANIFEST_DIR"));
        let Ok(txt) = std::fs::read_to_string(&path) else { return };
        let g = fog::load_exact(&serde_json::from_str(&txt).unwrap(), "current", 1).unwrap();
        let truth = MapView::from_game(&g);
        let model = train(&[MapView::from_game(&g)], 1);
        let s = sample_belief(&g, 1, &model, Mode::Full, 7);
        let m = MapView::from_game(&s);
        let obs = &truth.explored[&1];
        for i in 0..obs.len() {
            if obs[i] {
                assert!(m.cls[i] == truth.cls[i] && m.res[i] == truth.res[i] && m.village[i] == truth.village[i] && m.cap[i] == truth.cap[i], "observed tile {i} changed");
            }
        }
        assert_eq!((0..obs.len()).filter(|&i| !obs[i] && m.cap[i] > 0).count(), 15, "15 hidden capitals expected");
    }
}
