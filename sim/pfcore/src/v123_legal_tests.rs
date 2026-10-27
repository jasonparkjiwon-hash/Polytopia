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

/// AMPHIBIOUS-WATER (L3 with Marine Life): a Mermaid leaves its city onto ocean. 6e1bf8e0 t5 #918: Aquarion
/// (techs 45, 47, 39, 46) Mermaid from (18,9) to (19,10). Without 46 the ocean stays closed unless the
/// amphibious_ocean_innate switch is on.
#[test]
fn mermaid_onto_ocean() {
    use crate::moves::step::StepMove;
    use crate::states::TechnologyState;
    use crate::v123_tests::add_unit;
    let mut s = board();
    explore(&mut s);
    s.tribes.get_mut(&1).unwrap().tribe_type = TribeType::Aquarion;
    s.tiles.get_mut(&idx(6, 6)).unwrap().terrain_type = TerrainType::Ocean;
    add_city(&mut s, 1, 5, 5);
    add_unit(&mut s, 1, UnitType::Mermaid, 5, 5, 10.0);
    assert!(!has(&s, &StepMove::new(idx(5, 5), idx(6, 6))));
    s.tribes.get_mut(&1).unwrap().tech_vanilla.push(TechnologyState { tech_type: TechnologyType::MarineLife, discovered: true, discovered_turn: 0 });
    assert!(has(&s, &StepMove::new(idx(5, 5), idx(6, 6))));
}

/// AQUARION-STRUCTURES (L3): with Aquaculture (39) an Aquarion city builds the Aqua Farm (49) on AquaCrop and the
/// Atoll (51) on water or flooded land. 3edee0ec t6 #393 Aqua Farm on AquaCrop water at (17,21); e15f392c t4 #259
/// Atoll on flooded field (25,12), right after researching 39.
#[test]
fn aquarion_aqua_farm_and_atoll() {
    use crate::moves::build::BuildMove;
    use crate::states::{ResourceState, TechnologyState};
    let t = |k| TechnologyState { tech_type: k, discovered: true, discovered_turn: 0 };
    let mut s = board();
    explore(&mut s);
    add_city(&mut s, 1, 5, 5);
    s.tribes.get_mut(&1).unwrap().cities[0]._territory = vec![idx(5, 5), idx(5, 4), idx(6, 4), idx(4, 4)];
    s.tiles.get_mut(&idx(5, 4)).unwrap().terrain_type = TerrainType::Water;
    s.resources.insert(idx(5, 4), Some(ResourceState { resource_type: ResourceType::AquaCrop }));
    s.tiles.get_mut(&idx(6, 4)).unwrap().effects.insert(TileEffect::Flooded);
    let tr = s.tribes.get_mut(&1).unwrap();
    tr.stars = 20;
    tr.tribe_type = TribeType::Aquarion;
    tr.tech_vanilla = vec![t(TechnologyType::AquaBase), t(TechnologyType::AquaFishing)];
    assert!(!has(&s, &BuildMove::new(idx(5, 4), StructureType::AquaFarm)));
    assert!(!has(&s, &BuildMove::new(idx(6, 4), StructureType::Atoll)));
    s.tribes.get_mut(&1).unwrap().tech_vanilla.push(t(TechnologyType::Aquaculture));
    assert!(has(&s, &BuildMove::new(idx(5, 4), StructureType::AquaFarm)));
    assert!(has(&s, &BuildMove::new(idx(5, 4), StructureType::Atoll)));
    assert!(has(&s, &BuildMove::new(idx(6, 4), StructureType::Atoll)));
    assert!(!has(&s, &BuildMove::new(idx(4, 4), StructureType::Atoll)), "dry land stays closed");
}

/// PORT-FLOODED (L3): a Port is built on Aquarion-flooded land. af181c8f t9 #961: player 8 (techs incl. Fishing)
/// builds a Port on the flooded field (6,26).
#[test]
fn port_on_flooded_land() {
    use crate::moves::build::BuildMove;
    use crate::states::TechnologyState;
    let t = |k| TechnologyState { tech_type: k, discovered: true, discovered_turn: 0 };
    let mut s = board();
    explore(&mut s);
    add_city(&mut s, 1, 5, 5);
    s.tribes.get_mut(&1).unwrap().cities[0]._territory = vec![idx(5, 5), idx(5, 4), idx(6, 4)];
    s.tiles.get_mut(&idx(5, 4)).unwrap().effects.insert(TileEffect::Flooded);
    let tr = s.tribes.get_mut(&1).unwrap();
    tr.stars = 20;
    tr.tech_vanilla = vec![t(TechnologyType::Basic), t(TechnologyType::Fishing)];
    assert!(has(&s, &BuildMove::new(idx(5, 4), StructureType::Port)));
    assert!(!has(&s, &BuildMove::new(idx(6, 4), StructureType::Port)), "dry land stays closed");
}

/// AQUARION-UNIT-47 (L3): Aquarion train the Mermaid Archer (47), not the Archer, once they have Archery.
/// 05ade18c t4 #193: bot p5 trains unit 47 at (4,11) right after researching Archery.
#[test]
fn aquarion_trains_mermaid_archer() {
    use crate::moves::summon::SummonMove;
    use crate::states::TechnologyState;
    let t = |k| TechnologyState { tech_type: k, discovered: true, discovered_turn: 0 };
    let mut s = board();
    add_city(&mut s, 1, 5, 5);
    let tr = s.tribes.get_mut(&1).unwrap();
    tr.stars = 20;
    tr.tribe_type = TribeType::Aquarion;
    tr.tech_vanilla = vec![t(TechnologyType::AquaBase), t(TechnologyType::Hunting), t(TechnologyType::Archery)];
    assert!(!has(&s, &SummonMove::new(idx(5, 5), UnitType::Archer)));
    assert!(has(&s, &SummonMove::new(idx(5, 5), UnitType::MermaidArcher)));
}

/// MONUMENT-TERRAIN (L3): with the Killer task done, Aquarion build the Gate of Power on ocean (e15f392c t14
/// #1843 at (27,13)) and Polaris on ice (af181c8f t16 #2442 at (10,17)); other tribes still can't use ocean.
#[test]
fn gate_of_power_on_ocean_and_ice() {
    use crate::moves::build::BuildMove;
    let mut s = board();
    explore(&mut s);
    add_city(&mut s, 1, 5, 5);
    s.tribes.get_mut(&1).unwrap().cities[0]._territory = vec![idx(5, 5), idx(5, 4), idx(6, 4)];
    s.tiles.get_mut(&idx(5, 4)).unwrap().terrain_type = TerrainType::Ocean;
    s.tiles.get_mut(&idx(6, 4)).unwrap().terrain_type = TerrainType::Ice;
    let tr = s.tribes.get_mut(&1).unwrap();
    tr.stars = 20;
    tr.kills = 10;
    assert!(!has(&s, &BuildMove::new(idx(5, 4), StructureType::GateOfPower)));
    assert!(has(&s, &BuildMove::new(idx(6, 4), StructureType::GateOfPower)));
    s.tribes.get_mut(&1).unwrap().tribe_type = TribeType::Aquarion;
    assert!(has(&s, &BuildMove::new(idx(5, 4), StructureType::GateOfPower)));
}

/// SWIFT-MOVE (L3): a unit with Swift (save effect 6, from a Shaman's Swarm) moves one tile further, also on the
/// turn after the Swarm. 09a5bf1e t7 #838: a Warrior swarmed at t6 #674 moves 2 tiles, (15,17) -> (14,15).
#[test]
fn swift_warrior_moves_two() {
    use crate::moves::step::StepMove;
    use crate::v123_tests::add_unit;
    let mut s = board();
    explore(&mut s);
    let w = add_unit(&mut s, 1, UnitType::Warrior, 5, 5, 10.0);
    assert!(!has(&s, &StepMove::new(idx(5, 5), idx(5, 3))));
    s.tribes.get_mut(&1).unwrap().units[w].effects.insert(UnitEffect::Swift);
    assert!(has(&s, &StepMove::new(idx(5, 5), idx(5, 3))));
}

/// AQUARION-TECH-SLOTS (L3): Marine Life (46) fills Sailing's slot, so Aquarion research Navigation from it;
/// Aquaculture (39) fills Ramming's, so Aquatism follows. 09a5bf1e t6 #635 (Navigation with 46, no Sailing),
/// e15f392c t9 #891 (Aquatism with 39, no Ramming).
#[test]
fn aquarion_tech_slots_research() {
    use crate::moves::research::ResearchMove;
    use crate::states::TechnologyState;
    let t = |k| TechnologyState { tech_type: k, discovered: true, discovered_turn: 0 };
    let mut s = board();
    add_city(&mut s, 1, 5, 5);
    let tr = s.tribes.get_mut(&1).unwrap();
    tr.stars = 100;
    tr.tribe_type = TribeType::Aquarion;
    tr.tech_vanilla = vec![t(TechnologyType::Basic), t(TechnologyType::AquaBase), t(TechnologyType::AquaFishing)];
    assert!(!has(&s, &ResearchMove::new(TechnologyType::Navigation)));
    let tr = s.tribes.get_mut(&1).unwrap();
    tr.tech_vanilla.push(t(TechnologyType::MarineLife));
    tr.tech_vanilla.push(t(TechnologyType::Aquaculture));
    assert!(has(&s, &ResearchMove::new(TechnologyType::Navigation)));
    assert!(has(&s, &ResearchMove::new(TechnologyType::Aquatism)));
}

/// AQUARION-UNITS-49-52 (L3 ids by HP): Aquarion train the Mermaid Defender (49) with Strategy and the Scuba (50)
/// with Diplomacy, not the Defender and Cloak. 9906f7da t13 #898 (49 after Strategy), t16 #1227 (50 one turn
/// after researching Diplomacy at t15 #1109).
#[test]
fn aquarion_defender_and_scuba() {
    use crate::moves::summon::SummonMove;
    use crate::states::TechnologyState;
    let t = |k| TechnologyState { tech_type: k, discovered: true, discovered_turn: 0 };
    let mut s = board();
    add_city(&mut s, 1, 5, 5);
    let tr = s.tribes.get_mut(&1).unwrap();
    tr.stars = 20;
    tr.tribe_type = TribeType::Aquarion;
    tr.tech_vanilla = vec![
        t(TechnologyType::AquaBase),
        t(TechnologyType::Organization),
        t(TechnologyType::Strategy),
        t(TechnologyType::Diplomacy),
    ];
    assert!(has(&s, &SummonMove::new(idx(5, 5), UnitType::MermaidDefender)));
    assert!(has(&s, &SummonMove::new(idx(5, 5), UnitType::MermaidCloak)));
    assert!(!has(&s, &SummonMove::new(idx(5, 5), UnitType::Defender)));
    assert!(!has(&s, &SummonMove::new(idx(5, 5), UnitType::Cloak)));
}

/// CYMANTI-OCEANOLOGY-ID (L3 + Jason): Cymanti's Oceanology is saved as Navigation (14) and unlocks the Living
/// Island (57). 9906f7da t11 #637: Jason's Cymanti (techs 6, 7, 38, 10, 13, 14) train unit 57 at (2,27).
#[test]
fn cymanti_navigation_trains_living_island() {
    use crate::moves::summon::SummonMove;
    use crate::states::TechnologyState;
    let t = |k| TechnologyState { tech_type: k, discovered: true, discovered_turn: 0 };
    let mut s = board();
    add_city(&mut s, 1, 5, 5);
    s.tiles.get_mut(&idx(5, 4)).unwrap().terrain_type = TerrainType::Water;
    let tr = s.tribes.get_mut(&1).unwrap();
    tr.stars = 30;
    tr.tribe_type = TribeType::Cymanti;
    tr.tech_vanilla = vec![t(TechnologyType::Fishing), t(TechnologyType::Sailing)];
    assert!(!has(&s, &SummonMove::new(idx(5, 5), UnitType::LivingIsland)));
    s.tribes.get_mut(&1).unwrap().tech_vanilla.push(t(TechnologyType::Navigation));
    assert!(has(&s, &SummonMove::new(idx(5, 5), UnitType::LivingIsland)));
    s.tribes.get_mut(&1).unwrap().tribe_type = TribeType::Imperius;
    assert!(!has(&s, &SummonMove::new(idx(5, 5), UnitType::LivingIsland)));
}

/// AQUARION-LOST-CITY (L3 n=1 + wiki): an Aquarion ocean ruin gives a level-3 city whose two level-up rewards
/// are still to choose. 9906f7da t11: Mermaid 62 examines (10,27) at #692, then takes Workshop (#694) and City
/// Wall (#698) there; the t12 save shows level 3, rewards [3, 1].
#[test]
fn aquarion_lost_city_rewards_pending() {
    use crate::moves::reward::RewardMove;
    use crate::moves::Move;
    use crate::v123_tests::{add_unit, put_structure};
    let mut s = board();
    s.tribes.get_mut(&1).unwrap().tribe_type = TribeType::Aquarion;
    s.tiles.get_mut(&idx(5, 5)).unwrap().terrain_type = TerrainType::Ocean;
    put_structure(&mut s, 5, 5, StructureType::Ruin);
    add_unit(&mut s, 1, UnitType::Mermaid, 5, 5, 10.0);
    crate::moves::capture::CaptureMove::with_reward(idx(5, 5), RuinsRewardType::City).execute(&mut s).unwrap();
    let c = s.tribes[&1].cities.iter().find(|c| c.idx == idx(5, 5)).expect("Lost City");
    assert_eq!((c.level, c.rewards.len()), (3, 0));
    assert!(has(&s, &RewardMove::new(idx(5, 5), CityRewardType::Workshop)));
    // the Mermaid that found it is now homed there (9906f7da t12: Mermaid 62 home (10,27))
    assert_eq!(s.tribes[&1].units[0].home_coords.as_ref().map(|c| c.idx), Some(idx(5, 5)));
}

/// AQUARION-AQUA-FARM-WATER (L3 n=5): the Aqua Farm also goes on plain ocean or water and makes the AquaCrop.
/// 9906f7da t12 #787/#789/#792/#794: p9 builds 49 on empty ocean (7,27), (4,18), (5,27), (6,18); the t13 save
/// shows imp49 with resource 9 on each. One move per tile (an AquaCrop tile isn't offered it twice).
#[test]
fn aqua_farm_on_plain_ocean() {
    use crate::moves::build::BuildMove;
    use crate::states::{ResourceState, TechnologyState};
    let t = |k| TechnologyState { tech_type: k, discovered: true, discovered_turn: 0 };
    let mut s = board();
    explore(&mut s);
    add_city(&mut s, 1, 5, 5);
    s.tribes.get_mut(&1).unwrap().cities[0]._territory = vec![idx(5, 5), idx(5, 4), idx(6, 4), idx(4, 4)];
    s.tiles.get_mut(&idx(5, 4)).unwrap().terrain_type = TerrainType::Ocean;
    s.tiles.get_mut(&idx(6, 4)).unwrap().terrain_type = TerrainType::Water;
    s.resources.insert(idx(6, 4), Some(ResourceState { resource_type: ResourceType::AquaCrop }));
    let tr = s.tribes.get_mut(&1).unwrap();
    tr.stars = 20;
    tr.tribe_type = TribeType::Aquarion;
    tr.tech_vanilla = vec![t(TechnologyType::AquaBase), t(TechnologyType::Aquaculture)];
    assert!(has(&s, &BuildMove::new(idx(5, 4), StructureType::AquaFarm)));
    let farm = BuildMove::new(idx(6, 4), StructureType::AquaFarm).serialize().to_string();
    assert_eq!(legal(&s).iter().filter(|m| **m == farm).count(), 1);
    assert!(!has(&s, &BuildMove::new(idx(4, 4), StructureType::AquaFarm)), "dry land stays closed");
}

/// CLATHRUS-ON-LAND (L3 n=2): Cymanti build the Clathrus (41) on land next to an own Fungi, not on water next to
/// Algae. 9be1198d t5 #288 on Forest (19,5), t6 #351 on Field (20,5); both earn +1 per adjacent Fungi next turn.
#[test]
fn clathrus_on_land_next_to_fungi() {
    use crate::moves::build::BuildMove;
    use crate::states::TechnologyState;
    use crate::v123_tests::put_structure;
    let t = |k| TechnologyState { tech_type: k, discovered: true, discovered_turn: 0 };
    let mut s = board();
    explore(&mut s);
    add_city(&mut s, 1, 5, 5);
    s.tribes.get_mut(&1).unwrap().cities[0]._territory = vec![idx(5, 5), idx(5, 4), idx(6, 4), idx(4, 4)];
    s.tiles.get_mut(&idx(6, 4)).unwrap().terrain_type = TerrainType::Forest;
    s.tiles.get_mut(&idx(4, 4)).unwrap().terrain_type = TerrainType::Water;
    let tr = s.tribes.get_mut(&1).unwrap();
    tr.stars = 20;
    tr.tribe_type = TribeType::Cymanti;
    tr.tech_vanilla = vec![t(TechnologyType::Roads), t(TechnologyType::Trade)];
    assert!(!has(&s, &BuildMove::new(idx(6, 4), StructureType::Clathrus)), "needs a Fungi next to it");
    put_structure(&mut s, 5, 4, StructureType::Fungi);
    for (x, y) in [(5, 4), (6, 4), (4, 4)] {
        s.tiles.get_mut(&idx(x, y)).unwrap().owner = 1;
    }
    assert!(has(&s, &BuildMove::new(idx(6, 4), StructureType::Clathrus)));
    assert!(!has(&s, &BuildMove::new(idx(4, 4), StructureType::Clathrus)), "not on water");
}

/// EXPLODE-WATER-SPORES (L3 n=1): a Boomchi exploding on water leaves algae with Spores, so a Fungi can follow.
/// af181c8f t16: Boomchi 354 explodes on water (13,9) at #2288; Fungi (37) built there at #2502; the t18 save
/// shows algae (flood 4) with resource 7 under it.
#[test]
fn explode_on_water_leaves_spores() {
    use crate::moves::abilities::explode::ExplodeMove;
    use crate::moves::Move;
    use crate::v123_tests::add_unit;
    let mut s = board();
    s.tribes.get_mut(&1).unwrap().tribe_type = TribeType::Cymanti;
    s.tiles.get_mut(&idx(5, 5)).unwrap().terrain_type = TerrainType::Water;
    add_unit(&mut s, 1, UnitType::Boomchi, 5, 5, 15.0);
    ExplodeMove::new(idx(5, 5)).execute(&mut s).unwrap();
    assert!(s.tiles[&idx(5, 5)].is_algae());
    assert_eq!(s.resources.get(&idx(5, 5)).cloned().flatten().map(|r| r.resource_type), Some(ResourceType::Spores));
}

/// AQUARION-FREE-SPIRIT (L3): Aquarion research the base Free Spirit after Riding, not Free Diving (25).
/// af181c8f t3: p4 Aquarion (techs 0, 20, 45) researches Riding (#208) then Free Spirit (#209); no Aquarion
/// player in any save holds 25.
#[test]
fn aquarion_research_free_spirit() {
    use crate::moves::research::ResearchMove;
    use crate::states::TechnologyState;
    let t = |k| TechnologyState { tech_type: k, discovered: true, discovered_turn: 0 };
    let mut s = board();
    add_city(&mut s, 1, 5, 5);
    let tr = s.tribes.get_mut(&1).unwrap();
    tr.stars = 100;
    tr.tribe_type = TribeType::Aquarion;
    tr.tech_vanilla = vec![t(TechnologyType::Basic), t(TechnologyType::AquaBase), t(TechnologyType::Climbing), t(TechnologyType::Riding)];
    assert!(has(&s, &ResearchMove::new(TechnologyType::FreeSpirit)));
    assert!(!has(&s, &ResearchMove::new(TechnologyType::FreeDiving)));
}

/// FLOOD-ALGAE (L3): flooded land is walkable for any land unit, no water tech needed. b2448ead t2 #173: Yadakk
/// Warrior (techs 0, 4, 6) steps from (24,17) onto the flooded village (24,16), then (t4 #349) onto flooded forest.
#[test]
fn warrior_walks_onto_flooded_land() {
    use crate::v123_tests::{add_unit, step_targets};
    let mut s = board();
    explore(&mut s);
    s.tiles.get_mut(&idx(5, 4)).unwrap().effects.insert(TileEffect::Flooded);
    s.tiles.get_mut(&idx(6, 4)).unwrap().terrain_type = TerrainType::Forest;
    s.tiles.get_mut(&idx(6, 4)).unwrap().effects.insert(TileEffect::Flooded);
    add_unit(&mut s, 1, UnitType::Warrior, 5, 5, 10.0);
    let t = step_targets(&s);
    assert!(t.contains(&idx(5, 4)) && t.contains(&idx(6, 4)));
}

/// WATER-UNIT-PORT-PASS (L3 n=2): a Shark (Water skill) sails on through an own port. e15f392c t12 #1416:
/// Shark 170 goes from its city (19,10) through the port (18,9) to (18,8); 6e1bf8e0 t11 #1786 likewise via (15,8).
#[test]
fn shark_passes_through_own_port() {
    use crate::v123_tests::{add_unit, put_structure};
    let mut s = board();
    explore(&mut s);
    for (x, y) in [(5, 5), (5, 4), (5, 3)] {
        s.tiles.get_mut(&idx(x, y)).unwrap().terrain_type = TerrainType::Water;
    }
    put_structure(&mut s, 5, 4, StructureType::Port);
    s.tiles.get_mut(&idx(5, 4)).unwrap().owner = 1;
    s.tribes.get_mut(&1).unwrap().tribe_type = TribeType::Aquarion;
    add_unit(&mut s, 1, UnitType::Shark, 5, 5, 15.0);
    assert!(crate::v123_tests::step_targets(&s).contains(&idx(5, 3)));
}

/// MOONI-CAPTURE-NO-UNIT-FREEZE (L3 n=1, 2 units): a Mooni capturing a village freezes the water around it but not
/// the enemy units next to it. e15f392c t5: Mooni 20 captures (16,10) at #371; Hoodrick Warrior 22 next to it then
/// moves (#397) and breaks ice (#398), and unit 23 moves and attacks (#403, #404).
#[test]
fn mooni_capture_leaves_units_unfrozen() {
    use crate::moves::capture::CaptureMove;
    use crate::moves::Move;
    use crate::v123_tests::{add_unit, put_structure};
    let mut s = board();
    s.tribes.get_mut(&1).unwrap().tribe_type = TribeType::Polaris;
    put_structure(&mut s, 5, 5, StructureType::Village);
    add_unit(&mut s, 1, UnitType::Mooni, 5, 5, 10.0);
    let w = add_unit(&mut s, 2, UnitType::Warrior, 5, 4, 10.0);
    s.tiles.get_mut(&idx(6, 5)).unwrap().terrain_type = TerrainType::Water;
    CaptureMove::new(idx(5, 5)).execute(&mut s).unwrap();
    assert!(!s.tribes[&2].units[w].effects.contains(&UnitEffect::Frozen));
    assert_eq!(s.tiles[&idx(6, 5)].terrain_type, TerrainType::Ice);
}

/// CITY-UNITS-OWN-ONLY (L3 n=4): a city's unit limit counts only its owner's units; units another tribe homed
/// there before the city changed hands don't. b2448ead t5 #457: p11 trains in its level-1 city (24,16)
/// with a p9 unit still homed there and one own unit.
#[test]
fn city_limit_counts_own_units_only() {
    use crate::coords::Coords;
    use crate::moves::summon::SummonMove;
    use crate::v123_tests::add_unit;
    let mut s = board();
    add_city(&mut s, 1, 5, 5);
    s.tribes.get_mut(&1).unwrap().stars = 20;
    let home = Some(Coords::from_xy(5, 5, s.settings.size));
    let a = add_unit(&mut s, 1, UnitType::Warrior, 3, 3, 10.0);
    s.tribes.get_mut(&1).unwrap().units[a].home_coords = home.clone();
    let b = add_unit(&mut s, 2, UnitType::Warrior, 7, 7, 10.0);
    s.tribes.get_mut(&2).unwrap().units[b].home_coords = home;
    assert!(has(&s, &SummonMove::new(idx(5, 5), UnitType::Warrior)));
}

/// ATOLL-ON-ALGAE (L3 n=1): the Atoll can be built on algae-covered water. 9906f7da t18 #1494: Aquarion build 51
/// at (3,27), Water with Cymanti algae (flood 4), in the city (2,27) they took that turn.
#[test]
fn atoll_on_algae() {
    use crate::moves::build::BuildMove;
    use crate::states::TechnologyState;
    let t = |k| TechnologyState { tech_type: k, discovered: true, discovered_turn: 0 };
    let mut s = board();
    explore(&mut s);
    add_city(&mut s, 1, 5, 5);
    s.tribes.get_mut(&1).unwrap().cities[0]._territory = vec![idx(5, 5), idx(5, 4)];
    s.tiles.get_mut(&idx(5, 4)).unwrap().terrain_type = TerrainType::Water;
    s.tiles.get_mut(&idx(5, 4)).unwrap().effects.insert(TileEffect::Algae);
    let tr = s.tribes.get_mut(&1).unwrap();
    tr.stars = 20;
    tr.tribe_type = TribeType::Aquarion;
    tr.tech_vanilla = vec![t(TechnologyType::AquaBase), t(TechnologyType::Aquaculture)];
    assert!(has(&s, &BuildMove::new(idx(5, 4), StructureType::Atoll)));
}
