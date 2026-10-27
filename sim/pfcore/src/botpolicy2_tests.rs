//! bot-policy: the policy picks legal moves, stays deterministic for a seed, and plays whole turns on a generated map.
use crate::api;
use crate::botpolicy2::{self, Policy, Weights};
use crate::game::Game;
use crate::mapgen::{generate, MapGenSettings};
use crate::moves::*;
use crate::types::*;
use std::collections::HashMap;

fn game() -> Game {
    let tribes = vec![TribeType::XinXi, TribeType::Imperius, TribeType::Bardur, TribeType::Oumaji];
    let mut g = Game { state: generate(MapGenSettings { size: MapSize::Normal, map_type: MapType::Continents, tribes, seed: 11, version: 115, symmetric: false }) };
    g.post_load();
    g
}

fn pol() -> Policy {
    let w = |l: &[(&str, f32)]| Weights(l.iter().map(|(k, x)| (k.to_string(), *x)).collect::<HashMap<_, _>>());
    Policy { g: w(&[("G:Step", 2.0), ("G:Step*frac_acted", -3.0), ("G:EndTurn*frac_acted", 4.0)]), w: w(&[("Step.village_gain", 1.0), ("Summon:Warrior", 1.0)]), capture_first: 0.9, ..Default::default() }
}

#[test]
fn features_and_groups() {
    let g = game();
    let legal = g.legal_moves();
    let ctx = botpolicy2::context(&g, &legal);
    assert_eq!(ctx.me, g.state.settings.current_player_turn_id);
    let f = botpolicy2::features(&g, &ctx, legal.iter().find(|m| m.move_type() == MoveType::Step).unwrap().as_ref());
    assert!(f.iter().any(|(k, _)| k == "Step") && f.iter().any(|(k, _)| k == "Step.village_gain"));
    let gf = botpolicy2::group_feats(&ctx, "Step", &[&f], &["Step".to_string(), "EndTurn".to_string()]);
    assert!(gf.iter().any(|(k, _)| k == "Gmax:Step.village_gain") && gf.iter().any(|(k, _)| k == "G:Step") && gf.iter().any(|(k, _)| k == "G:Step*has:EndTurn"));
}

#[test]
fn policy_plays_whole_turns_and_is_reproducible() {
    let run = |seed: u64| {
        let mut g = game();
        let mut rng = seed | 1;
        let mut ends = 0;
        for _ in 0..600 {
            let legal = g.legal_moves();
            let i = botpolicy2::choose(&g, &legal, &pol(), &mut rng, true);
            let end = legal[i].move_type() == MoveType::EndTurn;
            assert!(api::apply(&mut g, legal[i].as_ref()).is_some(), "legal move applies");
            if end { ends += 1; if ends == 8 { break; } }
        }
        assert!(ends >= 4, "the policy ends its turns ({ends})");
        api::fingerprint(&g.state)
    };
    assert_eq!(run(5), run(5));
    let mut rng = 3u64;
    let g = game();
    let legal = g.legal_moves();
    let i = botpolicy2::choose_random(&legal, &mut rng);
    assert!(i < legal.len());
}

#[test]
fn v3_file_loads_with_ext_and_rules() {
    let p = Policy::from_file("../../data/bot_policy_v3.json").expect("v3 policy file");
    assert!(p.ext, "v3 uses the extended features");
    assert!((p.capture_first - 0.94).abs() < 1e-6);
    assert!(p.group_bias.get("EndTurn").map_or(false, |&b| b < 0.0));
    let v2 = Policy::from_file("../../data/bot_policy_v2.json").expect("v2 policy file");
    assert!(!v2.ext && v2.group_bias.is_empty(), "v2 stays on the old features");
}
