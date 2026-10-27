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
