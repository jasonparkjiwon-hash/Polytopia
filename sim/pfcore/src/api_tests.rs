//! fm-accept: the forward-model API on a generated map (no saves needed): labels, apply/undo, clone, determinism, Dice.
use crate::api;
use crate::game::Game;
use crate::mapgen::{generate, MapGenSettings};
use crate::types::*;

fn game() -> Game {
    let tribes = vec![TribeType::XinXi, TribeType::Imperius, TribeType::Bardur, TribeType::Oumaji];
    let mut g = Game { state: generate(MapGenSettings { size: MapSize::Normal, map_type: MapType::Continents, tribes, seed: 11, version: 115, symmetric: false }) };
    g.post_load();
    g
}

/// Plays `n` pseudo-random moves (EndTurn every 6th) so the state has units, cities and fog to undo.
fn advance(g: &mut Game, n: usize) {
    for i in 0..n {
        let ms = api::legal(g);
        let pick = if i % 6 == 5 { ms.iter().position(|m| m.label == "EndTurn") } else { ms.iter().position(|m| m.label != "EndTurn") };
        if let Some(k) = pick.or(Some(0)) { api::apply(g, ms[k].mv.as_ref()); }
    }
}

#[test]
fn labels_and_keys() {
    let g = game();
    let ms = api::legal(&g);
    assert!(ms.iter().any(|m| m.label == "EndTurn"));
    assert!(ms.iter().all(|m| !m.label.is_empty() && api::find(&g, &m.key).is_some()));
    assert!(ms.iter().any(|m| m.label.starts_with("Step Warrior (")), "{:?}", ms.iter().map(|m| &m.label).collect::<Vec<_>>());
}

#[test]
fn apply_undo_clone_determinism() {
    let mut g = game();
    advance(&mut g, 40);
    let f0 = api::fingerprint(&g.state);
    for m in api::legal(&g) {
        let (mut a, mut b) = (api::clone(&g), api::clone(&g));
        let ua = api::apply(&mut a, m.mv.as_ref()).expect("legal move applies");
        api::apply(&mut b, m.mv.as_ref());
        assert_eq!(api::fingerprint(&a.state), api::fingerprint(&b.state), "deterministic: {}", m.label);
        assert_eq!(api::fingerprint(&g.state), f0, "clone independent: {}", m.label);
        api::undo(&mut a, ua);
        assert_eq!(api::fingerprint_with(&a.state, true), api::fingerprint_with(&g.state, true), "undo up to reveals: {}", m.label);
    }
}

#[test]
fn end_turn_passes_play() {
    let mut g = game();
    let p = g.state.settings.current_player_turn_id;
    let f0 = api::fingerprint(&g.state);
    let u = api::end_turn(&mut g).expect("end turn");
    assert_ne!(g.state.settings.current_player_turn_id, p);
    api::undo(&mut g, u);
    assert_eq!(api::fingerprint_with(&g.state, true), api::fingerprint_with(&game().state, true));
    let _ = f0;
}

#[test]
fn dice_follows_the_table() {
    let dist = serde_json::json!({"ruin_reward": {
        "resolved_land": {"outcomes": {"stars": {"count": 3}, "tech": {"count": 1}, "pop": {"count": 0}, "explorer": {"count": 0}, "unit": {"count": 0}}},
        "resolved_water": {"outcomes": {"pop": {"count": 1}}}}});
    let mut d = api::Dice::new(&dist, 5).unwrap();
    let g = game();
    let land = *g.state.tiles.iter().find(|(_, t)| !t.is_water_terrain()).unwrap().0;
    let n = 4000;
    let stars = (0..n).filter(|_| d.sample_ruin(&g.state, land) == RuinsRewardType::Resources).count();
    assert!((stars as f64 / n as f64 - 0.75).abs() < 0.03, "{stars}");
    let water = *g.state.tiles.iter().find(|(_, t)| t.is_water_terrain()).unwrap().0;
    assert_eq!(d.sample_ruin(&g.state, water), RuinsRewardType::PopGrowth);
}

/// State as a JSON value minus what search mode doesn't keep: reveals (explorers), fog memory, history, message log.
fn search_view(g: &Game) -> serde_json::Value {
    let mut v = serde_json::to_value(&g.state).unwrap();
    let o = v.as_object_mut().unwrap();
    for k in ["_messages", "_history", "history"] { o.remove(k); }
    if let Some(t) = o.get_mut("tiles").and_then(|t| t.as_object_mut()) {
        for tile in t.values_mut() { tile.as_object_mut().map(|o| o.remove("explorers")); }
    }
    if let Some(t) = o.get_mut("tribes").and_then(|t| t.as_object_mut()) {
        for tribe in t.values_mut() {
            if let Some(o) = tribe.as_object_mut() { for k in ["memoryUnits", "memoryAttacks"] { o.remove(k); } }
        }
    }
    v
}

/// First few paths where two JSON values differ.
fn view_diff(a: &serde_json::Value, b: &serde_json::Value, path: &str, depth: usize) -> String {
    use serde_json::Value::{Array, Null, Object};
    match (a, b) {
        (Object(x), Object(y)) if depth < 6 => {
            let mut out = Vec::new();
            for (k, v) in x { if y.get(k) != Some(v) { out.push(view_diff(v, y.get(k).unwrap_or(&Null), &format!("{path}.{k}"), depth + 1)); } }
            out.truncate(4); out.join(" | ")
        }
        (Array(x), Array(y)) if x.len() == y.len() && depth < 6 => {
            let mut out = Vec::new();
            for (i, v) in x.iter().enumerate() { if y[i] != *v { out.push(view_diff(v, &y[i], &format!("{path}[{i}]"), depth + 1)); } }
            out.truncate(4); out.join(" | ")
        }
        _ => format!("{path}: {} vs {}", a.to_string().chars().take(80).collect::<String>(), b.to_string().chars().take(80).collect::<String>()),
    }
}

#[test]
fn search_end_turn_goes_to_next_player() {
    let mut g = game();
    let p = g.state.settings.current_player_turn_id;
    let f0 = api::fingerprint(&g.state);
    let end = api::legal(&g).into_iter().find(|m| m.label == "EndTurn").unwrap();
    let u = api::apply_search(&mut g, end.mv.as_ref()).expect("end turn");
    assert_eq!(g.state.settings.current_player_turn_id, p % 4 + 1, "the next player moves, not the mover again");
    api::undo(&mut g, u);
    assert_eq!(api::fingerprint(&g.state), f0, "search undo is exact, reveals included");
}

#[test]
fn search_apply_undo_is_exact_and_reveals_nothing() {
    let mut g = game();
    advance(&mut g, 40);
    let f0 = api::fingerprint(&g.state);
    let explored = |g: &Game| g.state.tiles.values().map(|t| { let mut e: Vec<_> = t.explorers.iter().copied().collect(); e.sort(); e }).collect::<Vec<_>>();
    let e0 = explored(&g);
    for m in api::legal(&g) {
        let mut a = api::clone(&g);
        let u = api::apply_search(&mut a, m.mv.as_ref()).expect("legal move applies");
        assert_eq!(explored(&a), e0, "{} reveals nothing", m.label);
        api::undo(&mut a, u);
        assert_eq!(api::fingerprint(&a.state), f0, "exact undo: {}", m.label);
    }
    assert_eq!(api::fingerprint(&g.state), f0);
}

#[test]
fn search_apply_matches_play_move_except_reveals_and_memory() {
    // Moves that reveal tiles in play_move (score +5 a tile, Lighthouse +1 population) may differ by design; the
    // search game is then resynced from the play_move game. Every other move must leave identical states.
    let explored = |g: &Game| g.state.tiles.values().map(|t| t.explorers.len()).sum::<usize>();
    let mut a = game();
    let mut b = api::clone(&a);
    let (mut matched, mut reveals) = (0, 0);
    for i in 0..400 {
        let ms = api::legal(&a);
        let pick = if i % 6 == 5 { ms.iter().position(|m| m.label == "EndTurn") } else { ms.iter().position(|m| m.label != "EndTurn") }.unwrap_or(0);
        let mb = api::find(&b, &ms[pick].key).expect("same move in the search game");
        let e0 = explored(&a);
        api::apply(&mut a, ms[pick].mv.as_ref());
        api::apply_search(&mut b, mb.as_ref());
        if explored(&a) != e0 {
            reveals += 1;
            b = api::clone(&a);
        } else {
            let (va, vb) = (search_view(&a), search_view(&b));
            if va != vb { panic!("search diverged from play_move on {} (move {i}, {matched} matched): {}", ms[pick].label, view_diff(&va, &vb, "", 0)); }
            matched += 1;
        }
    }
    assert!(matched > 250, "only {matched} moves compared ({reveals} revealed)");
}
