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
    let t = s.tiles.get_mut(&idx(x, y)).unwrap();
    t.owner = owner;
    t.ruling_city_coords = Some(Coords::from_xy(x, y, SIZE));
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

/// STOMP-ON-BOARDING (L3, n=1): 6e1bf8e0 t12 action 1549, Zebasi Giant 290 (38/40 HP) moved onto its port;
/// the full-HP Kickoo Warrior next to it was left at 4 HP (stomp floor(12/2) with Juggernaut attack 4).
#[test]
fn giant_boarding_stomps() {
    let mut s = board();
    s.tiles.get_mut(&idx(5, 5)).unwrap().terrain_type = TerrainType::Water;
    s.tiles.get_mut(&idx(5, 5)).unwrap().owner = 1;
    put_structure(&mut s, 5, 5, StructureType::Port);
    let g = add_unit(&mut s, 1, UnitType::Giant, 4, 5, 38.0);
    let w = add_unit(&mut s, 2, UnitType::Warrior, 6, 5, 10.0);
    step(&mut s, 1, g, 5, 5);
    assert_eq!(unit(&s, 2, w).health, 4.0);
}

/// FLOOD-ALGAE (L3): on Aquarion-flooded land a boat stays a boat (its passenger aboard); a city is plain land.
#[test]
fn boat_stays_boat_on_flooded_land() {
    let mut s = board();
    s.tiles.get_mut(&idx(4, 5)).unwrap().terrain_type = TerrainType::Water;
    s.tiles.get_mut(&idx(5, 5)).unwrap().effects.insert(TileEffect::Flooded);
    let b = add_unit(&mut s, 1, UnitType::Raft, 4, 5, 10.0);
    s.tribes.get_mut(&1).unwrap().units[b].passenger_type = Some(UnitType::Warrior);
    step(&mut s, 1, b, 5, 5);
    assert_eq!(unit(&s, 1, b).unit_type, UnitType::Raft);
    step(&mut s, 1, b, 6, 5);
    assert_eq!(unit(&s, 1, b).unit_type, UnitType::Warrior);
}

/// KILL-MOVE-IN (L3 + replay A/B), JUGGERNAUT-KILL-MOVE (L3): a Stiff melee unit (here a Moth) stays put
/// after a kill; a Juggernaut (Stiff boat) moves in and lands as its Giant.
#[test]
fn stiff_stays_after_kill_boats_move_in() {
    let mut s = board();
    let a = add_unit(&mut s, 1, UnitType::Moth, 4, 5, 10.0);
    add_unit(&mut s, 2, UnitType::Warrior, 5, 5, 1.0);
    attack(&mut s, a, 0);
    assert_eq!(unit(&s, 1, a).coords.idx, idx(4, 5));
    let mut s = board();
    s.tiles.get_mut(&idx(4, 5)).unwrap().terrain_type = TerrainType::Water;
    let j = add_unit(&mut s, 1, UnitType::Juggernaut, 4, 5, 40.0);
    s.tribes.get_mut(&1).unwrap().units[j].passenger_type = Some(UnitType::Giant);
    add_unit(&mut s, 2, UnitType::Warrior, 5, 5, 1.0);
    attack(&mut s, j, 0);
    assert_eq!(unit(&s, 1, j).coords.idx, idx(5, 5));
    assert_eq!(unit(&s, 1, j).unit_type, UnitType::Giant);
}

/// WATER-UNITS (L2, replay A/B): after a kill a water unit follows onto water, flooded land or a city, never
/// dry land. e15f392c t9: a Shark didn't follow a kill onto dry land.
#[test]
fn water_unit_kill_move() {
    for (city, moves_in) in [(false, false), (true, true)] {
        let mut s = board();
        s.tiles.get_mut(&idx(4, 5)).unwrap().terrain_type = TerrainType::Water;
        if city {
            add_city(&mut s, 2, 5, 5);
        }
        let a = add_unit(&mut s, 1, UnitType::Shark, 4, 5, 10.0);
        add_unit(&mut s, 2, UnitType::Warrior, 5, 5, 1.0);
        attack(&mut s, a, 0);
        assert_eq!(unit(&s, 1, a).coords.idx == idx(5, 5), moves_in);
    }
}

fn push_to(s: &GameState, owner: i32, i: usize) -> Option<(i32, i32)> {
    crate::functions::calculate_pushable_position(s, unit(s, owner, i)).map(|t| (t % SIZE, t / SIZE))
}

/// PUSH-DIRECTION, SAVE-UNIT-FACING, PUSH-NEVER-MOVED, PUSH-TIEBREAK, PUSH-PORT-FIRST (all L3; engine push_target).
#[test]
fn push_rule() {
    use crate::functions::round_dir;
    // 6e1bf8e0 t11 / e15f392c t13: a 2-tile move (-2,-1) pushes on (-1,0)
    assert_eq!(round_dir(-2, -1), (-1, 0));
    // a unit that never moved goes toward the centre, nearest of 8 by angle; 6e1bf8e0 t14: (-1,+13) -> (0,+1)
    let mut s = board();
    let u = add_unit(&mut s, 1, UnitType::Warrior, 6, 0, 10.0);
    assert_eq!(push_to(&s, 1, u), Some((6, 1)));
    // a unit that moved goes on the way it faces (its last move, kept across turns: af181c8f t4) ...
    let mut s = board();
    let w = add_unit(&mut s, 1, UnitType::Warrior, 2, 8, 10.0);
    step(&mut s, 1, w, 3, 7);
    assert_eq!(push_to(&s, 1, w), Some((4, 6)));
    // ... reversed for a unit of another player than the one acting
    s.settings.current_player_turn_id = 2;
    assert_eq!(push_to(&s, 1, w), Some((2, 8)));
    // blocked: counter-clockwise side first (the next entry of N, NE, E, ...); af181c8f t10
    s.settings.current_player_turn_id = 1;
    add_unit(&mut s, 2, UnitType::Warrior, 4, 6, 10.0);
    assert_eq!(push_to(&s, 1, w), Some((4, 7)));
    // a unit that was attacked and never moved is pushed toward its attacker (6e1bf8e0 t13)
    let mut s = board();
    let a = add_unit(&mut s, 1, UnitType::Archer, 3, 3, 10.0);
    let d = add_unit(&mut s, 2, UnitType::Defender, 5, 3, 15.0);
    s.tiles.get_mut(&idx(3, 3)).unwrap().explorers.insert(2);
    attack(&mut s, a, d);
    s.settings.current_player_turn_id = 2;
    assert_eq!(push_to(&s, 2, d), Some((4, 3)));
    // own port only as the first choice (af181c8f t15, t21); no open tile -> None (the unit is removed)
    let mut s = board();
    let p = add_unit(&mut s, 1, UnitType::Warrior, 5, 1, 10.0);
    for x in 4..=6 {
        for y in 0..=2 {
            if (x, y) != (5, 1) {
                s.tiles.get_mut(&idx(x, y)).unwrap().terrain_type = TerrainType::Water;
            }
        }
    }
    s.tiles.get_mut(&idx(6, 1)).unwrap().owner = 1;
    put_structure(&mut s, 6, 1, StructureType::Port);
    assert_eq!(push_to(&s, 1, p), None);
    s.tiles.get_mut(&idx(5, 2)).unwrap().owner = 1;
    put_structure(&mut s, 5, 2, StructureType::Port);
    assert_eq!(push_to(&s, 1, p), Some((5, 2)));
}

/// MOONI-FREEZE (L3: e15f392c 4/4 Warrior-on-ice cases; af181c8f ocean freezes too), MOONI-FREEZE-UNITS (L3):
/// after a Mooni moves, the water and ocean around it turn to ice, except under a unit; adjacent enemies are Frozen.
#[test]
fn mooni_freeze() {
    let mut s = board();
    for (x, t) in [(6, TerrainType::Water), (7, TerrainType::Ocean)] {
        for y in 4..=6 {
            s.tiles.get_mut(&idx(x, y)).unwrap().terrain_type = t;
        }
    }
    let m = add_unit(&mut s, 1, UnitType::Mooni, 5, 5, 10.0);
    add_unit(&mut s, 1, UnitType::Raft, 7, 4, 10.0);
    let e = add_unit(&mut s, 2, UnitType::Raft, 7, 6, 10.0);
    step(&mut s, 1, m, 6, 5);
    assert_eq!(s.tiles[&idx(5, 4)].terrain_type, TerrainType::Field);
    assert_eq!(s.tiles[&idx(6, 4)].terrain_type, TerrainType::Ice);
    assert_eq!(s.tiles[&idx(7, 5)].terrain_type, TerrainType::Ice);
    assert_eq!(s.tiles[&idx(7, 5)].frozen_from, Some(TerrainType::Ocean));
    assert_eq!(s.tiles[&idx(7, 4)].terrain_type, TerrainType::Ocean);
    assert_eq!(s.tiles[&idx(7, 6)].terrain_type, TerrainType::Ocean);
    assert!(unit(&s, 2, e).effects.contains(&UnitEffect::Frozen));
}

/// ACTION-18-BREAK-ICE (L3; Jason's in-game text, 91/92 uses had ice next to the unit): Break Ice turns all the
/// ice around the acting unit back to water or ocean, except under a unit.
#[test]
fn break_ice_around_unit() {
    use crate::moves::Move;
    let mut s = board();
    for (x, y, from) in [(4, 4, Some(TerrainType::Ocean)), (6, 6, None), (6, 4, None)] {
        let t = s.tiles.get_mut(&idx(x, y)).unwrap();
        t.terrain_type = TerrainType::Ice;
        t.frozen_from = from;
    }
    add_unit(&mut s, 1, UnitType::Warrior, 5, 5, 10.0);
    add_unit(&mut s, 2, UnitType::Warrior, 6, 4, 10.0);
    crate::moves::abilities::break_ice::BreakIceMove::new(idx(4, 4)).execute(&mut s).unwrap();
    assert_eq!(s.tiles[&idx(4, 4)].terrain_type, TerrainType::Ocean);
    assert_eq!(s.tiles[&idx(6, 6)].terrain_type, TerrainType::Water);
    assert_eq!(s.tiles[&idx(6, 4)].terrain_type, TerrainType::Ice);
}

/// POLARIS-CAPTURE-FREEZE (L3, n=1: af181c8f t13, a Battle Sled took a city and the water around it was ice the
/// same turn; 12 of 16 water tiles newly in Polaris territory were ice at the next save), MOONI-FREEZE (capture).
#[test]
fn polaris_capture_freezes() {
    use crate::moves::Move;
    let mut s = board();
    s.tribes.get_mut(&1).unwrap().tribe_type = TribeType::Polaris;
    put_structure(&mut s, 5, 5, StructureType::Village);
    for y in 4..=6 {
        s.tiles.get_mut(&idx(6, y)).unwrap().terrain_type = TerrainType::Water;
    }
    add_unit(&mut s, 1, UnitType::BattleSled, 5, 5, 15.0);
    add_unit(&mut s, 2, UnitType::Raft, 6, 6, 10.0);
    crate::moves::capture::CaptureMove::new(idx(5, 5)).execute(&mut s).unwrap();
    assert_eq!(s.tiles[&idx(6, 4)].terrain_type, TerrainType::Ice);
    assert_eq!(s.tiles[&idx(6, 5)].terrain_type, TerrainType::Ice);
    assert_eq!(s.tiles[&idx(6, 6)].terrain_type, TerrainType::Water);
}

/// IDLE-AUTO-RECOVER (L3: Jason in game + af181c8f t15, his idle wounded Rider was +4 by the next save; applying it
/// to AI players adds 57 replay misses): only the human's idle units heal at the end of the turn.
#[test]
fn idle_recover_human_only() {
    for bot in [false, true] {
        let mut s = board();
        s.tribes.get_mut(&1).unwrap().bot = bot;
        add_unit(&mut s, 1, UnitType::Rider, 5, 5, 5.0);
        let _ = crate::actions::process_end_turn_effects(&mut s, 1);
        assert_eq!(unit(&s, 1, 0).health, if bot { 5.0 } else { 7.0 }); // +2 outside its territory
    }
}

/// EXPLODE-DAMAGE (L3), EXPLODE-POISON (L3): an explosion hits each adjacent enemy for half the exploder's direct
/// damage (rounded, halved, floored) and poisons the survivors. 6e1bf8e0 t12: Moth 213 (3-9 HP) exploded and took
/// exactly 1 HP from each adjacent full-HP Swordsman (237, 344).
#[test]
fn explode_damage() {
    use crate::moves::Move;
    let mut s = board();
    add_unit(&mut s, 1, UnitType::Moth, 5, 5, 6.0);
    let a = add_unit(&mut s, 2, UnitType::Swordsman, 6, 5, 15.0);
    let b = add_unit(&mut s, 2, UnitType::Swordsman, 4, 4, 15.0);
    crate::moves::abilities::explode::ExplodeMove::new(idx(5, 5)).execute(&mut s).unwrap();
    for i in [a, b] {
        assert_eq!(unit(&s, 2, i).health, 14.0);
        assert!(unit(&s, 2, i).effects.contains(&UnitEffect::Poison));
    }
    assert!(s.tribes[&1].units.is_empty());
}

/// ECON-BOT-BONUS (L3): bots get DifficultyHandicap - 1 stars a turn (Crazy 4 -> +3, Hard 2 -> +1, human/Easy 1
/// -> 0), only while they hold their own capital with no enemy on it (A/B 2026-10-23: a besieged capital loses it).
#[test]
fn bot_bonus() {
    use crate::functions::get_bot_bonus;
    let mut s = board();
    add_city(&mut s, 1, 5, 5);
    s.tiles.get_mut(&idx(5, 5)).unwrap().capital_of = 1;
    s.tribes.get_mut(&1).unwrap().handicap = 4;
    assert_eq!(get_bot_bonus(&s, &s.tribes[&1]), 3);
    s.tribes.get_mut(&1).unwrap().handicap = 1;
    assert_eq!(get_bot_bonus(&s, &s.tribes[&1]), 0);
    s.tribes.get_mut(&1).unwrap().handicap = 2;
    add_unit(&mut s, 2, UnitType::Warrior, 5, 5, 10.0);
    assert_eq!(get_bot_bonus(&s, &s.tribes[&1]), 0);
}
