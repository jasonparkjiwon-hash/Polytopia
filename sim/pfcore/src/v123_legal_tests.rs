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

/// SKATE-MOVE (L3): a skater gets +1 movement leaving a city too. 09a5bf1e t1 #124: a Mooni (movement 1)
/// leaves its city at (26,19) 2 tiles onto ice.
#[test]
fn mooni_skates_two_from_city() {
    use crate::moves::step::StepMove;
    use crate::v123_tests::add_unit;
    let mut s = board();
    explore(&mut s);
    for (x, y) in [(5, 4), (5, 3), (5, 2)] {
        s.tiles.get_mut(&idx(x, y)).unwrap().terrain_type = TerrainType::Ice;
    }
    add_city(&mut s, 1, 5, 5);
    add_unit(&mut s, 1, UnitType::Mooni, 5, 5, 10.0);
    assert!(has(&s, &StepMove::new(idx(5, 5), idx(5, 3))));
    assert!(!has(&s, &StepMove::new(idx(5, 5), idx(5, 2))));
}

/// PORT-STEP (L3): a frozen enemy port is skated onto; an amphibious unit steps onto an enemy port on water;
/// a Warrior can't step onto an enemy port on water. af181c8f t12 #1424 (Battle Sled), t12 #1403 (Mermaid).
#[test]
fn enemy_port_step() {
    use crate::moves::step::StepMove;
    use crate::v123_tests::{add_unit, put_structure};
    let mut s = board();
    explore(&mut s);
    s.tiles.get_mut(&idx(5, 4)).unwrap().terrain_type = TerrainType::Water;
    s.tiles.get_mut(&idx(5, 4)).unwrap().owner = 2;
    put_structure(&mut s, 5, 4, StructureType::Port);
    s.tribes.get_mut(&1).unwrap().tech_vanilla.push(crate::states::TechnologyState { tech_type: TechnologyType::Fishing, discovered: true, discovered_turn: 0 });
    let w = add_unit(&mut s, 1, UnitType::Warrior, 5, 5, 10.0);
    assert!(!has(&s, &StepMove::new(idx(5, 5), idx(5, 4))));
    s.tribes.get_mut(&1).unwrap().units[w].unit_type = UnitType::Mermaid;
    assert!(has(&s, &StepMove::new(idx(5, 5), idx(5, 4))));
    s.tribes.get_mut(&1).unwrap().units[w].unit_type = UnitType::BattleSled;
    s.tiles.get_mut(&idx(5, 4)).unwrap().terrain_type = TerrainType::Ice;
    assert!(has(&s, &StepMove::new(idx(5, 5), idx(5, 4))));
}

/// WATER-UNITS-VILLAGE (L3): a water unit moves from water into a village on land. af181c8f t14 #1875: a Raychi
/// at (23,12) enters the unowned village at (24,11).
#[test]
fn raychi_enters_village() {
    use crate::moves::step::StepMove;
    use crate::v123_tests::{add_unit, put_structure};
    let mut s = board();
    explore(&mut s);
    s.tribes.get_mut(&1).unwrap().tribe_type = TribeType::Cymanti;
    s.tiles.get_mut(&idx(5, 5)).unwrap().terrain_type = TerrainType::Water;
    put_structure(&mut s, 6, 4, StructureType::Village);
    add_unit(&mut s, 1, UnitType::Raychi, 5, 5, 10.0);
    assert!(has(&s, &StepMove::new(idx(5, 5), idx(6, 4))));
    assert!(!has(&s, &StepMove::new(idx(5, 5), idx(6, 6))), "plain land stays closed");
}

/// EXPLODE-ANYTIME (L3): a Boomchi can explode with no enemy around, after moving. af181c8f t16 #2288.
#[test]
fn explode_without_enemy() {
    use crate::moves::abilities::explode::ExplodeMove;
    use crate::v123_tests::add_unit;
    let mut s = board();
    s.tribes.get_mut(&1).unwrap().tribe_type = TribeType::Cymanti;
    s.tiles.get_mut(&idx(5, 5)).unwrap().terrain_type = TerrainType::Ocean;
    let b = add_unit(&mut s, 1, UnitType::Boomchi, 5, 5, 15.0);
    s.tribes.get_mut(&1).unwrap().units[b].moved = true;
    assert!(has(&s, &ExplodeMove::new(idx(5, 5))));
}

/// MOTH-V123 (L3): a Moth can explode. 6e1bf8e0 t11 #1674: Moth 213 explodes on (9,3).
#[test]
fn moth_explodes() {
    use crate::moves::abilities::explode::ExplodeMove;
    use crate::v123_tests::add_unit;
    let mut s = board();
    s.tribes.get_mut(&1).unwrap().tribe_type = TribeType::Cymanti;
    add_unit(&mut s, 1, UnitType::Moth, 5, 5, 3.0);
    assert!(has(&s, &ExplodeMove::new(idx(5, 5))));
}

/// CONVERT-ATTACK (L3): a Mind Bender's attack is a ConvertMove; a Scoutship carrying one attacks normally.
/// 09a5bf1e t5 #523 (Shaman converts), e15f392c t9 #1007 (Scoutship with a Mind Bender attacks).
#[test]
fn converter_attack_is_convert() {
    use crate::moves::abilities::convert::ConvertMove;
    use crate::moves::attack::AttackMove;
    use crate::v123_tests::add_unit;
    let mut s = board();
    let m = add_unit(&mut s, 1, UnitType::MindBender, 5, 5, 10.0);
    add_unit(&mut s, 2, UnitType::Warrior, 6, 5, 10.0);
    assert!(has(&s, &ConvertMove::new(idx(5, 5), idx(6, 5))));
    assert!(!has(&s, &AttackMove::new(idx(5, 5), idx(6, 5))));
    let u = &mut s.tribes.get_mut(&1).unwrap().units[m];
    u.unit_type = UnitType::Scoutship;
    u.passenger_type = Some(UnitType::MindBender);
    assert!(has(&s, &AttackMove::new(idx(5, 5), idx(6, 5))));
}


/// TRIBE-TECH-TIERS / RESEARCH-BACKWARD (L3): Polaris with Frostwork can research Sledding (09a5bf1e t1 #126);
/// Vengir with Smithery can research Mining without Climbing (09a5bf1e t1 #114).
#[test]
fn research_tribe_tree_and_backward() {
    use crate::moves::research::ResearchMove;
    use crate::states::TechnologyState;
    let t = |k| TechnologyState { tech_type: k, discovered: true, discovered_turn: 0 };
    let mut s = board();
    add_city(&mut s, 1, 5, 5);
    let tr = s.tribes.get_mut(&1).unwrap();
    tr.stars = 100;
    tr.tribe_type = TribeType::Polaris;
    tr.tech_vanilla = vec![t(TechnologyType::Basic), t(TechnologyType::Frostwork)];
    assert!(has(&s, &ResearchMove::new(TechnologyType::Sledding)));
    let tr = s.tribes.get_mut(&1).unwrap();
    tr.tribe_type = TribeType::Vengir;
    tr.tech_vanilla = vec![t(TechnologyType::Basic), t(TechnologyType::Smithery)];
    assert!(has(&s, &ResearchMove::new(TechnologyType::Mining)));
}

/// METAL-WITH-MINING (L3): Vengir with Mining but no Climbing can build a Mine. 09a5bf1e t2 #190: (25,4).
#[test]
fn mine_with_mining_no_climbing() {
    use crate::moves::build::BuildMove;
    use crate::states::{ResourceState, TechnologyState};
    let t = |k| TechnologyState { tech_type: k, discovered: true, discovered_turn: 0 };
    let mut s = board();
    explore(&mut s);
    add_city(&mut s, 1, 5, 5);
    s.tribes.get_mut(&1).unwrap().cities[0]._territory = vec![idx(5, 5), idx(5, 4)];
    s.tiles.get_mut(&idx(5, 4)).unwrap().terrain_type = TerrainType::Mountain;
    s.resources.insert(idx(5, 4), Some(ResourceState { resource_type: ResourceType::Metal }));
    let tr = s.tribes.get_mut(&1).unwrap();
    tr.stars = 20;
    tr.tribe_type = TribeType::Vengir;
    tr.tech_vanilla = vec![t(TechnologyType::Basic), t(TechnologyType::Smithery), t(TechnologyType::Mining)];
    assert!(has(&s, &BuildMove::new(idx(5, 4), StructureType::Mine)));
}
