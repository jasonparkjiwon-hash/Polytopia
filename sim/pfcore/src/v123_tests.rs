//! Tests for the v123 corrections (Polytopia repo, not upstream Polyfish).
//! Each test names the ledger id (verify/ledger.json) and, where there is one, the save case it comes from.
#![cfg(test)]

use crate::coords::Coords;
use crate::functions::{get_defense_bonus, get_unit_attack, get_unit_defense, get_unit_max_health};
use crate::actions::units::calculate_combat;
use crate::states::*;
use crate::types::*;

pub const SIZE: i32 = 11;

/// An 11x11 board of Field tiles, players 1 and 2, player 1 to move.
pub fn board() -> GameState {
    let mut s = GameState::default();
    s.settings.size = SIZE;
    s.settings.tile_count = SIZE * SIZE;
    s.settings.version = 123;
    s.settings.current_player_turn_id = 1;
    for idx in 0..SIZE * SIZE {
        let mut t = TileState::default();
        t.coords = Coords::from_index(idx, SIZE);
        t.terrain_type = TerrainType::Field;
        s.tiles.insert(idx, t);
        s.structures.insert(idx, None);
        s.resources.insert(idx, None);
    }
    for id in [1, 2] {
        let mut t = TribeState::default();
        t.id = id;
        t.tribe_type = if id == 1 { TribeType::Imperius } else { TribeType::Bardur };
        s.tribes.insert(id, t);
    }
    s
}

pub fn idx(x: i32, y: i32) -> i32 {
    y * SIZE + x
}

/// Put a unit on (x, y); returns its index in the owner's unit list.
pub fn add_unit(s: &mut GameState, owner: i32, ut: UnitType, x: i32, y: i32, hp: f32) -> usize {
    let mut u = UnitState::default();
    u.owner = owner;
    u.unit_type = ut;
    u.health = hp;
    u.coords = Coords::from_xy(x, y, SIZE);
    u.prev_coords = Coords::invalid();
    s.tiles.get_mut(&idx(x, y)).unwrap()._unit_owner_id = Some(owner);
    let t = s.tribes.get_mut(&owner).unwrap();
    t.units.push(u);
    t.units.len() - 1
}

pub fn unit(s: &GameState, owner: i32, i: usize) -> &UnitState {
    &s.tribes[&owner].units[i]
}

/// Damage a direct attack would deal (attacker owner/index -> defender owner/index).
pub fn damage(s: &GameState, a: (i32, usize), d: (i32, usize)) -> f32 {
    let au = unit(s, a.0, a.1);
    let du = unit(s, d.0, d.1);
    calculate_combat(
        get_unit_attack(s, au),
        au.health,
        get_unit_max_health(au),
        get_unit_defense(du),
        du.health,
        get_unit_max_health(du),
        get_defense_bonus(s, du),
    )
    .attack_damage
}

/// C7 (L3): poison halves defence, bonus included, nothing more.
/// e15f392c turn 11: a Raychi (atk 3) hits a poisoned full-HP Warrior (def 2) on open ground for exactly 10.
#[test]
fn poison_halves_defence() {
    let mut s = board();
    let a = add_unit(&mut s, 1, UnitType::Raychi, 4, 5, 10.0);
    let d = add_unit(&mut s, 2, UnitType::Warrior, 5, 5, 10.0);
    s.tribes.get_mut(&2).unwrap().units[d].effects.insert(UnitEffect::Poison);
    assert_eq!(get_unit_defense(unit(&s, 2, d)) * get_defense_bonus(&s, unit(&s, 2, d)), 1.0);
    // a 15 HP Warrior tells 10 (x0.5) from 11 (x0.35, the v115 rule)
    s.tribes.get_mut(&2).unwrap().units[d].health = 15.0;
    s.tribes.get_mut(&2).unwrap().units[d].veteran = true;
    assert_eq!(damage(&s, (1, a), (2, d)), 10.0);
}

/// Attack with player 1's unit a on player 2's unit d, as player 1's move.
pub fn attack(s: &mut GameState, a: usize, d: usize) {
    s.settings.current_player_turn_id = 1;
    let _ = crate::actions::units::attack_unit(s, 1, a, 2, Some(d));
}

/// FROZEN-NO-RETALIATION (L3): a Frozen unit doesn't retaliate.
/// 09a5bf1e turn 7: a Frozen Warrior took a hit and did not hit back.
#[test]
fn frozen_defender_no_retaliation() {
    let mut s = board();
    let a = add_unit(&mut s, 1, UnitType::Warrior, 4, 5, 10.0);
    let d = add_unit(&mut s, 2, UnitType::Warrior, 5, 5, 10.0);
    s.tribes.get_mut(&2).unwrap().units[d].effects.insert(UnitEffect::Frozen);
    attack(&mut s, a, d);
    assert_eq!(unit(&s, 1, a).health, 10.0);
    assert_eq!(unit(&s, 2, d).health, 5.0);
}

/// CLOAK-DAGGER-RETALIATION (L3, Jason in game): a Cloak never takes retaliation; a Dagger retaliates when attacked.
#[test]
fn hidden_attacker_no_retaliation() {
    let mut s = board();
    let a = add_unit(&mut s, 1, UnitType::Cloak, 4, 5, 5.0);
    let d = add_unit(&mut s, 2, UnitType::Warrior, 5, 5, 10.0);
    attack(&mut s, a, d);
    assert_eq!(unit(&s, 1, a).health, 5.0);
    let mut s = board();
    let a = add_unit(&mut s, 1, UnitType::Warrior, 4, 5, 10.0);
    let d = add_unit(&mut s, 2, UnitType::Dagger, 5, 5, 10.0);
    attack(&mut s, a, d);
    assert!(unit(&s, 1, a).health < 10.0);
}

/// C20 (L3, Jason's in-game test): an Archer shooting from a tile the target's tribe can't see draws no return fire;
/// from an explored tile it does.
#[test]
fn unseen_attacker_no_retaliation() {
    let mut s = board();
    let a = add_unit(&mut s, 1, UnitType::Archer, 3, 5, 10.0);
    let d = add_unit(&mut s, 2, UnitType::Archer, 5, 5, 10.0);
    attack(&mut s, a, d);
    assert_eq!(unit(&s, 1, a).health, 10.0);
    let mut s = board();
    let a = add_unit(&mut s, 1, UnitType::Archer, 3, 5, 10.0);
    let d = add_unit(&mut s, 2, UnitType::Archer, 5, 5, 10.0);
    s.tiles.get_mut(&idx(3, 5)).unwrap().explorers.insert(2);
    attack(&mut s, a, d);
    assert!(unit(&s, 1, a).health < 10.0);
}

pub fn add_city(s: &mut GameState, owner: i32, x: i32, y: i32) {
    let mut c = CityState::default();
    c.idx = idx(x, y);
    c.owner = owner;
    c.level = 1;
    s.tiles.get_mut(&idx(x, y)).unwrap().owner = owner;
    s.tribes.get_mut(&owner).unwrap().cities.push(c);
}

/// DEF-BONUS (L2, replay A/B): 1.5 for a Fortify unit in its own city; none in another tribe's city, even at peace.
#[test]
fn city_bonus_own_city_only() {
    let mut s = board();
    add_city(&mut s, 1, 5, 5);
    add_city(&mut s, 2, 7, 7);
    let mut rel = DiplomacyRelationState::default();
    rel.state = 1;
    s.tribes.get_mut(&1).unwrap().relations.insert(2, rel.clone());
    s.tribes.get_mut(&2).unwrap().relations.insert(1, rel);
    let own = add_unit(&mut s, 1, UnitType::Warrior, 5, 5, 10.0);
    let ally = add_unit(&mut s, 1, UnitType::Warrior, 7, 7, 10.0);
    assert_eq!(get_defense_bonus(&s, unit(&s, 1, own)), 1.5);
    assert_eq!(get_defense_bonus(&s, unit(&s, 1, ally)), 1.0);
}

/// SPLASH (L2: Polyfish + e15f392c turn 13 + replay A/B): each enemy next to the target takes half
/// the damage a direct hit would deal it, floored. A Bomber's direct hit on a full Defender is 7, so splash is 3.
#[test]
fn splash_is_floored() {
    let mut s = board();
    let a = add_unit(&mut s, 1, UnitType::Bomber, 2, 5, 10.0);
    let d = add_unit(&mut s, 2, UnitType::Warrior, 5, 5, 10.0);
    let n = add_unit(&mut s, 2, UnitType::Defender, 5, 6, 15.0);
    assert_eq!(damage(&s, (1, a), (2, n)), 7.0);
    attack(&mut s, a, d);
    assert_eq!(unit(&s, 2, n).health, 12.0);
}

/// UNIT-STATS-UI (L3, v123 info cards): Cloak attack 2, Stiff.
/// MOTH-V123 (L3, n=1 fit): 6e1bf8e0 t11-12, Moth 213 attacked a poisoned Warrior in a city and took no
/// retaliation, then survived a full-HP Swordsman's hit on a mountain: defence >= 1.6 (engine uses 2).
#[test]
fn v123_unit_cards() {
    use crate::settings::units::get_unit_setting;
    let c = get_unit_setting(UnitType::Cloak);
    assert_eq!((c.attack, c.defense, c.health), (2.0, 0.5, 5.0));
    assert!(c.skills.contains(&SkillType::Stiff));
    let mut s = board();
    let a = add_unit(&mut s, 1, UnitType::Moth, 4, 5, 10.0);
    let d = add_unit(&mut s, 2, UnitType::Warrior, 5, 5, 10.0);
    attack(&mut s, a, d);
    assert_eq!(unit(&s, 1, a).health, 10.0);
    let mut s = board();
    s.tiles.get_mut(&idx(4, 5)).unwrap().terrain_type = TerrainType::Mountain;
    let m = add_unit(&mut s, 2, UnitType::Moth, 4, 5, 10.0);
    let sw = add_unit(&mut s, 1, UnitType::Swordsman, 5, 5, 15.0);
    assert!(damage(&s, (1, sw), (2, m)) < 10.0);
}

/// C29b (L3): neither the Mooni nor the Shaman has Static (they can become veterans).
#[test]
fn mooni_shaman_not_static() {
    use crate::settings::units::get_unit_setting;
    for ut in [UnitType::Mooni, UnitType::Shaman] {
        assert!(!get_unit_setting(ut).skills.contains(&SkillType::Static));
    }
}

/// AQUARION-UNIT (L3), UNIT-ID-48 (L3), UNIT-ID-53 (L2): v123 ids 46 Mermaid (start unit), 48 Swordsmaid
/// (af181c8f: all 45 belong to Aquarion, trained after Smithery, 15 HP), 53 Shark; stats from the v123 cards.
#[test]
fn aquarion_units() {
    use crate::settings::technology::get_unlocked_units;
    use crate::settings::units::get_unit_setting;
    assert_eq!(UnitType::from(46), UnitType::Mermaid);
    assert_eq!(UnitType::from(48), UnitType::Swordsmaid);
    assert_eq!(UnitType::from(53), UnitType::Shark);
    assert_eq!(get_unit_setting(UnitType::Swordsmaid).health, 15.0);
    assert_eq!(get_unit_setting(UnitType::Shark).attack, 3.5);
    let basic = get_unlocked_units(TechnologyType::Basic, TribeType::Aquarion);
    assert_eq!(basic, vec![UnitType::Mermaid]);
    let smith = get_unlocked_units(TechnologyType::Smithery, TribeType::Aquarion);
    assert_eq!(smith, vec![UnitType::Swordsmaid]);
    assert_eq!(get_unlocked_units(TechnologyType::Smithery, TribeType::Imperius), vec![UnitType::Swordsman]);
}

pub fn put_structure(s: &mut GameState, x: i32, y: i32, st: StructureType) {
    s.structures.insert(
        idx(x, y),
        Some(StructureState { structure_type: st, level: 1, founded: 0 }),
    );
}

/// Move player 1's unit i to (x, y) as a voluntary step.
pub fn step(s: &mut GameState, owner: i32, i: usize, x: i32, y: i32) {
    s.settings.current_player_turn_id = owner;
    let _ = crate::actions::units::step_unit(s, owner, i, idx(x, y), false);
}

/// GIANT-JUGGERNAUT (L3, af181c8f: 19/19 Juggernauts carry a Giant): a Giant boarding at a port becomes a
/// Juggernaut carrying the Giant, and lands as a Giant.
#[test]
fn giant_boards_as_juggernaut_and_lands() {
    let mut s = board();
    s.tiles.get_mut(&idx(5, 5)).unwrap().terrain_type = TerrainType::Water;
    s.tiles.get_mut(&idx(5, 5)).unwrap().owner = 1;
    s.tiles.get_mut(&idx(6, 5)).unwrap().terrain_type = TerrainType::Water;
    put_structure(&mut s, 5, 5, StructureType::Port);
    let g = add_unit(&mut s, 1, UnitType::Giant, 4, 5, 40.0);
    step(&mut s, 1, g, 5, 5);
    assert_eq!(unit(&s, 1, g).unit_type, UnitType::Juggernaut);
    assert_eq!(unit(&s, 1, g).passenger_type, Some(UnitType::Giant));
    step(&mut s, 1, g, 6, 5);
    step(&mut s, 1, g, 7, 5);
    assert_eq!(unit(&s, 1, g).unit_type, UnitType::Giant);
    assert_eq!(unit(&s, 1, g).passenger_type, None);
}

/// PORT-BOARDS (L3): a land unit boards only at its own tribe's port; a frozen-over port is walked on foot.
/// e15f392c t12: a Hoodrick Warrior crossed its own port after a Mooni froze it and stayed on foot.
#[test]
fn own_port_boards() {
    let mut s = board();
    for (x, owner) in [(5, 2), (6, 1)] {
        s.tiles.get_mut(&idx(x, 5)).unwrap().terrain_type = TerrainType::Water;
        s.tiles.get_mut(&idx(x, 5)).unwrap().owner = owner;
        put_structure(&mut s, x, 5, StructureType::Port);
    }
    let w = add_unit(&mut s, 1, UnitType::Warrior, 5, 4, 10.0);
    step(&mut s, 1, w, 5, 5);
    assert_eq!(unit(&s, 1, w).unit_type, UnitType::Warrior);
    s.tiles.get_mut(&idx(6, 5)).unwrap().terrain_type = TerrainType::Ice;
    let w2 = add_unit(&mut s, 1, UnitType::Warrior, 6, 4, 10.0);
    step(&mut s, 1, w2, 6, 5);
    assert_eq!(unit(&s, 1, w2).unit_type, UnitType::Warrior);
    s.tiles.get_mut(&idx(6, 5)).unwrap().terrain_type = TerrainType::Water;
    let w3 = add_unit(&mut s, 1, UnitType::Warrior, 7, 4, 10.0);
    step(&mut s, 1, w2, 6, 6);
    step(&mut s, 1, w3, 6, 5);
    assert_eq!(unit(&s, 1, w3).unit_type, UnitType::Raft);
}
