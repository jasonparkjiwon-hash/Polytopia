//! Legal-move generation tests for v123 (Polytopia repo, not upstream Polyfish; pf-legal stream).
//! Each test names the ledger id (verify/ledger.json) and the save case it comes from. Board helpers are
//! shared with v123_tests.
#![cfg(test)]

use crate::moves::{generate_legal_moves, Move};
use crate::types::*;
use crate::v123_tests::{add_city, board, idx};

fn legal(s: &crate::states::GameState) -> Vec<String> {
    generate_legal_moves(s).iter().map(|m| m.serialize().to_string()).collect()
}

/// Player 1 has explored the whole board (steps need explored tiles).
fn explore(s: &mut crate::states::GameState) {
    for t in s.tiles.values_mut() {
        t.explorers.insert(1);
    }
}

fn has(s: &crate::states::GameState, m: &dyn Move) -> bool {
    legal(s).contains(&m.serialize().to_string())
}

/// DIPLO-PEACE: an opponent without a capital is offered peace through one of its cities (6e1bf8e0 t11 #1676:
/// Cymanti offer Vengir, whose capital Luxidoor had taken, peace at the city Vengir had just captured).
#[test]
fn peace_offer_without_capital() {
    use crate::moves::abilities::diplomacy::PeaceTreatyMove;
    use crate::states::TechnologyState;
    let mut s = board();
    add_city(&mut s, 1, 2, 2);
    add_city(&mut s, 2, 8, 8);
    s.tribes.get_mut(&2).unwrap().relations.insert(1, Default::default());
    let t = s.tribes.get_mut(&1).unwrap();
    t.relations.insert(2, Default::default());
    t.known_players.insert(2);
    t.tech_vanilla.push(TechnologyState { tech_type: TechnologyType::Strategy, discovered: true, discovered_turn: 0 });
    assert!(has(&s, &PeaceTreatyMove::new(idx(8, 8), 2)));
}

/// ALGAE-MOVE (L3): Cymanti units move on through algae; other tribes' land units still stop on it.
/// af181c8f t16 #2293: a Cymanti Boomchi leaves its city at (25,15) over algae (25,14) onto water (26,13).
#[test]
fn cymanti_move_through_algae() {
    use crate::moves::step::StepMove;
    use crate::v123_tests::add_unit;
    let mut s = board();
    explore(&mut s);
    s.tribes.get_mut(&1).unwrap().tribe_type = TribeType::Cymanti;
    for (x, y) in [(5, 4), (6, 3)] {
        s.tiles.get_mut(&idx(x, y)).unwrap().terrain_type = TerrainType::Water;
    }
    s.tiles.get_mut(&idx(5, 4)).unwrap().effects.insert(TileEffect::Algae);
    add_city(&mut s, 1, 5, 5);
    add_unit(&mut s, 1, UnitType::Boomchi, 5, 5, 10.0);
    assert!(has(&s, &StepMove::new(idx(5, 5), idx(6, 3))));
    // the same unit of a non-Cymanti tribe stops on the algae
    s.tribes.get_mut(&1).unwrap().tribe_type = TribeType::Imperius;
    assert!(!has(&s, &StepMove::new(idx(5, 5), idx(6, 3))));
}
