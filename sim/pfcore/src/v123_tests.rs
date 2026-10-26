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

/// TECH-TREE (L3): every base tech's tier and prerequisite as in data/tech_tree.json; Navigation needs Sailing.
#[test]
fn navigation_needs_sailing() {
    use crate::settings::technology::get_technology_setting;
    assert_eq!(get_technology_setting(TechnologyType::Navigation).requires, Some(TechnologyType::Sailing));
}

/// AQUARION-TECH-TIERS (L3 tiers): 47 tier 1, 39 and 46 tier 2, priced tier x cities + 4; 46 Marine Life unlocks
/// the Shark (UNIT-ID-53: all 29 Shark trainings come after 46). Only Aquarion can research them; 39 and 46 need 47.
#[test]
fn aquarion_techs() {
    use crate::settings::technology::{get_researchable_techs, get_unlocked_units};
    let mut t = TribeState::default();
    t.tribe_type = TribeType::Aquarion;
    let one_city = { let mut c = CityState::default(); c.idx = 0; c };
    t.cities.push(one_city);
    assert_eq!(crate::functions::get_tech_cost(&t, TechnologyType::AquaFishing), 5);
    assert_eq!(crate::functions::get_tech_cost(&t, TechnologyType::Aquaculture), 6);
    assert_eq!(get_unlocked_units(TechnologyType::MarineLife, TribeType::Aquarion), vec![UnitType::Shark]);
    let r = get_researchable_techs(&t.tech_vanilla, TribeType::Aquarion);
    assert!(r.contains(&TechnologyType::AquaFishing) && !r.contains(&TechnologyType::MarineLife));
    t.tech_vanilla.push(TechnologyState { tech_type: TechnologyType::AquaFishing, discovered: true, ..Default::default() });
    let r = get_researchable_techs(&t.tech_vanilla, TribeType::Aquarion);
    assert!(r.contains(&TechnologyType::MarineLife) && r.contains(&TechnologyType::Aquaculture));
    assert!(!get_researchable_techs(&[], TribeType::Imperius).contains(&TechnologyType::AquaFishing));
}

/// All tiles player 1's units may step to (from Polyfish's legal move list).
pub fn step_targets(s: &GameState) -> Vec<i32> {
    crate::moves::generate_legal_moves(s)
        .iter()
        .filter(|m| m.move_type() == MoveType::Step)
        .filter_map(|m| m.serialize().get("target").and_then(|v| v.as_i64()).map(|v| v as i32))
        .collect()
}

/// AMPHIBIOUS-WATER (L3, 11 save records): an Aquarion Mermaid steps onto shallow water and flooded land with
/// no water tech; not onto ocean.
#[test]
fn amphibious_on_water() {
    let mut s = board();
    s.tribes.get_mut(&1).unwrap().tribe_type = TribeType::Aquarion;
    s.tiles.get_mut(&idx(6, 5)).unwrap().terrain_type = TerrainType::Water;
    s.tiles.get_mut(&idx(4, 5)).unwrap().terrain_type = TerrainType::Ocean;
    s.tiles.get_mut(&idx(5, 6)).unwrap().effects.insert(TileEffect::Flooded);
    for t in s.tiles.values_mut() {
        t.explorers.insert(1);
    }
    add_unit(&mut s, 1, UnitType::Mermaid, 5, 5, 10.0);
    let t = step_targets(&s);
    assert!(t.contains(&idx(6, 5)) && t.contains(&idx(5, 6)) && !t.contains(&idx(4, 5)), "{t:?}");
}

/// TRIBE-TECH-TIERS (L3, n=1-2 each): tribe techs cost tier x cities + 4 at the tier of the base tech they replace
/// (Ice Fishing 2, Sledding 2, Polar Warfare 3, Spearing 3, Polarism 3, Oceantology 3), and need what it needs.
#[test]
fn tribe_tech_tiers() {
    use crate::settings::technology::get_researchable_techs;
    let mut t = TribeState::default();
    t.tribe_type = TribeType::Polaris;
    t.cities.push(CityState::default());
    for (tech, cost) in [
        (TechnologyType::IceFishing, 6),
        (TechnologyType::Sledding, 6),
        (TechnologyType::PolarWarfare, 7),
        (TechnologyType::Polarism, 7),
        (TechnologyType::Spearing, 7),
        (TechnologyType::Oceantology, 7),
    ] {
        assert_eq!(crate::functions::get_tech_cost(&t, tech), cost, "{tech:?}");
    }
    let have = |v: &[TechnologyType]| -> Vec<TechnologyState> {
        v.iter().map(|&x| TechnologyState { tech_type: x, discovered: true, ..Default::default() }).collect()
    };
    let r = get_researchable_techs(&have(&[TechnologyType::Frostwork]), TribeType::Polaris);
    assert!(r.contains(&TechnologyType::Sledding) && r.contains(&TechnologyType::IceFishing), "{r:?}");
    let r = get_researchable_techs(&have(&[TechnologyType::Frostwork, TechnologyType::Sledding]), TribeType::Polaris);
    assert!(r.contains(&TechnologyType::PolarWarfare), "{r:?}");
}

/// ACTION-18-BREAK-ICE (L3: "a Dash unit can move onto ice and break it the same turn"): a Warrior that has
/// moved is still offered Break Ice.
#[test]
fn dash_unit_breaks_ice_after_moving() {
    use crate::moves::Move;
    let mut s = board();
    s.tiles.get_mut(&idx(6, 5)).unwrap().terrain_type = TerrainType::Ice;
    let i = add_unit(&mut s, 1, UnitType::Warrior, 5, 5, 10.0);
    s.tribes.get_mut(&1).unwrap().units[i].moved = true;
    let brk = crate::moves::abilities::break_ice::BreakIceMove::new(idx(6, 5)).serialize();
    assert!(crate::moves::generate_legal_moves(&s).iter().any(|m| m.serialize() == brk));
}

/// TECH-COST (L2; the discount itself not yet seen in a save): Philosophy cuts a tech to ceil(cost x 2/3),
/// as engine/economy.py tech_cost (x0.66 differs at 50, 100, ...).
#[test]
fn philosophy_discount() {
    use crate::settings::technology::get_tech_cost;
    assert_eq!(get_tech_cost(2, 3, true), 7); // 10 -> 6.67 -> 7
    assert_eq!(get_tech_cost(23, 2, true), 34); // 50 -> 33.3 -> 34 (x0.66 gives 33)
}

/// Starfish (pf-port count: all 32 harvests in the saves came with Navigation, Polaris's with Polar Warfare):
/// the tribe's version of Navigation is enough to gather Starfish (+8, ECON-PRICES-V123).
#[test]
fn polaris_gathers_starfish() {
    use crate::moves::Move;
    let mut s = board();
    s.tribes.get_mut(&1).unwrap().tribe_type = TribeType::Polaris;
    s.tribes.get_mut(&1).unwrap().tech_vanilla.push(TechnologyState {
        tech_type: TechnologyType::PolarWarfare,
        discovered: true,
        ..Default::default()
    });
    s.resources.insert(idx(5, 5), Some(ResourceState { resource_type: ResourceType::Starfish }));
    s.tiles.get_mut(&idx(5, 5)).unwrap().terrain_type = TerrainType::Water;
    add_unit(&mut s, 1, UnitType::Raft, 5, 5, 10.0);
    let cap = crate::moves::capture::CaptureMove::new(idx(5, 5)).serialize();
    assert!(crate::moves::generate_legal_moves(&s).iter().any(|m| m.serialize() == cap));
    let stars = s.tribes[&1].stars;
    crate::moves::capture::CaptureMove::new(idx(5, 5)).execute(&mut s).unwrap();
    assert_eq!(s.tribes[&1].stars, stars + 8);
}

/// ECON-PRICES-V123 (L3, 5/5 star checks): Enchant Animal costs 3.
#[test]
fn enchant_animal_costs_3() {
    let s = board();
    assert_eq!(crate::version_sync::get_polytaur_cost(&s), 3);
}

/// Outpost (engine/economy.py BUILD 33: 5 stars, star rows exact): buildable for 5; its effect is not modelled yet.
#[test]
fn outpost_buildable() {
    use crate::settings::structures::{get_structure_setting, unimplemented_reason};
    assert!(unimplemented_reason(StructureType::Outpost).is_none());
    assert_eq!(get_structure_setting(StructureType::Outpost).cost, Some(5));
}

/// CAPTURE-TERRITORY (L2, replay A/B): capturing a city gives the captor the city tile and the 8 around it (unowned
/// or the old owner's), nothing further. e15f392c t15: player 3 took (28,16); the port (28,18), two tiles away and
/// ruled by the old owner's other city, stayed the old owner's, and a Swordsman then boarded there.
#[test]
fn capture_takes_3x3() {
    use crate::moves::Move;
    let mut s = board();
    add_city(&mut s, 2, 5, 5);
    put_structure(&mut s, 5, 5, StructureType::Village);
    for k in crate::functions::get_square_indices(idx(5, 5), 2, SIZE) {
        s.tiles.get_mut(&k).unwrap().owner = 2;
    }
    s.tribes.get_mut(&2).unwrap().cities[0]._territory = crate::functions::get_square_indices(idx(5, 5), 2, SIZE);
    add_city(&mut s, 2, 1, 1); // the old owner keeps a city
    add_unit(&mut s, 1, UnitType::Warrior, 5, 5, 10.0);
    crate::moves::capture::CaptureMove::new(idx(5, 5)).execute(&mut s).unwrap();
    assert_eq!(s.tiles[&idx(5, 6)].owner, 1);
    assert_eq!(s.tiles[&idx(5, 7)].owner, 2);
}

/// Captured capital (save count: 33 captured capitals keep the old owner's Capital id; no tribe holds two): the
/// captor gets no capital star and no bot bonus from it (ECON-INCOME, ECON-BOT-BONUS).
#[test]
fn captured_capital_stays_old_owners() {
    use crate::moves::Move;
    let mut s = board();
    add_city(&mut s, 2, 5, 5);
    put_structure(&mut s, 5, 5, StructureType::Village);
    s.tiles.get_mut(&idx(5, 5)).unwrap().capital_of = 2;
    add_city(&mut s, 2, 1, 1);
    s.tribes.get_mut(&1).unwrap().handicap = 4;
    add_unit(&mut s, 1, UnitType::Warrior, 5, 5, 10.0);
    crate::moves::capture::CaptureMove::new(idx(5, 5)).execute(&mut s).unwrap();
    assert_eq!(s.tiles[&idx(5, 5)].capital_of, 2);
    assert_eq!(crate::functions::get_bot_bonus(&s, &s.tribes[&1]), 0);
}

/// ECON-MARKET-CLATHRUS (L3, n=1: af181c8f p14 t25->26, a Market next to a Windmill with 3 Farms paid +3):
/// a Market earns the level of each adjacent Windmill/Sawmill/Forge.
#[test]
fn market_pays_by_level() {
    let mut s = board();
    add_city(&mut s, 1, 5, 5);
    s.tribes.get_mut(&1).unwrap().cities[0]._territory = crate::functions::get_square_indices(idx(5, 5), 2, SIZE);
    put_structure(&mut s, 6, 6, StructureType::Market);
    put_structure(&mut s, 7, 6, StructureType::Windmill);
    for (x, y) in [(8, 5), (8, 6), (8, 7)] {
        put_structure(&mut s, x, y, StructureType::Farm);
    }
    // a second city whose territory overlaps: the Market (ruled by the first city) still counts once
    add_city(&mut s, 1, 7, 7);
    s.tribes.get_mut(&1).unwrap().cities[1]._territory = crate::functions::get_square_indices(idx(7, 7), 2, SIZE);
    s.tiles.get_mut(&idx(6, 6)).unwrap().ruling_city_coords = Some(Coords::from_xy(5, 5, SIZE));
    let total = |t: &GameState| -> i32 {
        t.tribes[&1].cities.iter().map(|c| crate::functions::get_city_production(t, c)).sum()
    };
    let base = { let mut t = s.clone(); t.structures.insert(idx(6, 6), None); total(&t) };
    assert_eq!(total(&s) - base, 3);
}

/// EMBASSY-ACTION (L3, n=2: 09a5bf1e t7, 6e1bf8e0 t13): an embassy costs the builder a net 4 (+2 for each one it
/// already has, ECON-EMBASSY); the host earns 2 a turn (4 at peace); the builder earns nothing while neutral, 4 at peace.
#[test]
fn embassy_cost_and_income() {
    use crate::functions::{get_embassy_cost, get_embassy_income};
    use crate::moves::Move;
    let mut s = board();
    add_city(&mut s, 2, 8, 8);
    s.tiles.get_mut(&idx(8, 8)).unwrap().capital_of = 2;
    for (a, b) in [(1, 2), (2, 1)] {
        s.tribes.get_mut(&a).unwrap().relations.insert(b, DiplomacyRelationState::default());
    }
    s.tribes.get_mut(&1).unwrap().stars = 10;
    assert_eq!(get_embassy_cost(&s.tribes[&1]), 4);
    crate::moves::abilities::diplomacy::EstablishEmbassyMove::new(idx(8, 8), 2).execute(&mut s).unwrap();
    assert_eq!(s.tribes[&1].stars, 6);
    assert_eq!(get_embassy_cost(&s.tribes[&1]), 6);
    assert_eq!((get_embassy_income(&s, &s.tribes[&1]), get_embassy_income(&s, &s.tribes[&2])), (0, 2));
    for (a, b) in [(1, 2), (2, 1)] {
        s.tribes.get_mut(&a).unwrap().relations.get_mut(&b).unwrap().state = 1;
    }
    assert_eq!((get_embassy_income(&s, &s.tribes[&1]), get_embassy_income(&s, &s.tribes[&2])), (4, 4));
}

/// SHAMAN (L3, n=1: e15f392c t9, Shaman 14 converted Scoutship 161, which ended Cymanti with 6 HP): a Shaman's
/// convert also deals its normal damage and takes no retaliation.
#[test]
fn shaman_converts_and_damages() {
    use crate::moves::Move;
    let mut s = board();
    let a = add_unit(&mut s, 1, UnitType::Shaman, 4, 5, 10.0);
    add_unit(&mut s, 2, UnitType::Warrior, 5, 5, 10.0);
    crate::moves::abilities::convert::ConvertMove::new(idx(4, 5), idx(5, 5)).execute(&mut s).unwrap();
    let w = s.tribes[&1].units.iter().find(|u| u.coords.idx == idx(5, 5)).unwrap();
    assert_eq!((w.unit_type, w.health), (UnitType::Warrior, 8.0)); // 1/(1+2) x 1 x 4.5 = 1.5 -> 2
    assert_eq!(unit(&s, 1, a).health, 10.0);
}

/// MOVE-BLOCKED-HIDDEN (L3, n=1: 6e1bf8e0 t11, a move onto a hidden Cloak stopped and the mover then attacked it
/// from where it stood): the move reveals the unit and the mover may still attack.
#[test]
fn move_onto_hidden_unit() {
    use crate::moves::Move;
    let mut s = board();
    let w = add_unit(&mut s, 1, UnitType::Warrior, 4, 5, 10.0);
    let c = add_unit(&mut s, 2, UnitType::Cloak, 5, 5, 5.0);
    s.tribes.get_mut(&2).unwrap().units[c].effects.insert(UnitEffect::Invisible);
    crate::moves::step::StepMove::new(idx(4, 5), idx(5, 5)).execute(&mut s).unwrap();
    assert_eq!(unit(&s, 1, w).coords.idx, idx(4, 5));
    assert!(!unit(&s, 2, c).effects.contains(&UnitEffect::Invisible));
    assert!(!unit(&s, 1, w).attacked);
}

/// DIPLO-BREAK-DISBAND (L3 for the disband, Jason in game 2026-10-23): breaking peace disbands the breaker's units
/// inside the ex-ally's territory; units elsewhere stay.
#[test]
fn break_peace_disbands() {
    use crate::moves::Move;
    let mut s = board();
    for (a, b) in [(1, 2), (2, 1)] {
        let mut r = DiplomacyRelationState::default();
        r.state = 1;
        s.tribes.get_mut(&a).unwrap().relations.insert(b, r);
    }
    s.tiles.get_mut(&idx(7, 7)).unwrap().owner = 2;
    add_unit(&mut s, 1, UnitType::Warrior, 7, 7, 10.0);
    add_unit(&mut s, 1, UnitType::Warrior, 2, 2, 10.0);
    crate::moves::abilities::diplomacy::BreakPeaceMove::new(2).execute(&mut s).unwrap();
    assert_eq!(s.tribes[&1].units.len(), 1);
    assert_eq!(unit(&s, 1, 0).coords.idx, idx(2, 2));
}

/// ECON-INCOME (L3): a city earns level + 1 per Workshop or Park (+1 own capital); a Workshop picked during play
/// adds exactly 1 (Polyfish raised production and also counted the reward).
#[test]
fn workshop_counts_once() {
    use crate::moves::Move;
    let mut s = board();
    add_city(&mut s, 1, 5, 5);
    put_structure(&mut s, 5, 5, StructureType::Village);
    {
        let c = &mut s.tribes.get_mut(&1).unwrap().cities[0];
        c.level = 2;
        c.production = 2;
    }
    let before = crate::functions::get_city_production(&s, &s.tribes[&1].cities[0]);
    crate::moves::reward::RewardMove::new(idx(5, 5), CityRewardType::Workshop).execute(&mut s).unwrap();
    assert_eq!(crate::functions::get_city_production(&s, &s.tribes[&1].cities[0]) - before, 1);
}

/// WATER-UNITS (L2) / KILL-MOVE-IN: a water unit follows a kill onto water. e15f392c t8 action 843: Raychi 147 killed
/// Luxidoor unit 122 on (2,14) and stood there at t9.
#[test]
fn water_unit_follows_kill_on_water() {
    let mut s = board();
    for x in 4..=5 {
        s.tiles.get_mut(&idx(x, 5)).unwrap().terrain_type = TerrainType::Water;
    }
    let a = add_unit(&mut s, 1, UnitType::Raychi, 4, 5, 10.0);
    add_unit(&mut s, 2, UnitType::Raft, 5, 5, 1.0);
    attack(&mut s, a, 0);
    assert_eq!(unit(&s, 1, a).coords.idx, idx(5, 5));
}

/// RUIN-UNIT-CYMANTI (L3, n=2): a Cymanti water ruin gives a veteran Boomchi (af181c8f t15: (14,7), 15 HP).
#[test]
fn cymanti_water_ruin_boomchi() {
    use crate::moves::Move;
    let mut s = board();
    s.tribes.get_mut(&1).unwrap().tribe_type = TribeType::Cymanti;
    s.tiles.get_mut(&idx(5, 5)).unwrap().terrain_type = TerrainType::Ocean;
    put_structure(&mut s, 5, 5, StructureType::Ruin);
    add_unit(&mut s, 1, UnitType::Raychi, 5, 5, 10.0);
    crate::moves::capture::CaptureMove::with_reward(idx(5, 5), RuinsRewardType::Swordsman).execute(&mut s).unwrap();
    let b = s.tribes[&1].units.iter().find(|u| u.unit_type == UnitType::Boomchi).expect("Boomchi");
    assert_eq!((b.coords.idx, b.health, b.veteran), (idx(5, 5), 15.0, true));
}

/// Fishing by tribe version (pf-port save count: Aquarion's Fishing builds all came with 47, 14/14; Polaris's with
/// Frostwork, 13/13): either tech offers the fish harvest.
#[test]
fn fishing_with_tribe_tech() {
    use crate::moves::Move;
    for (tribe, tech) in [(TribeType::Aquarion, TechnologyType::AquaFishing), (TribeType::Polaris, TechnologyType::Frostwork)] {
        let mut s = board();
        s.tribes.get_mut(&1).unwrap().tribe_type = tribe;
        s.tribes.get_mut(&1).unwrap().stars = 5;
        s.tribes.get_mut(&1).unwrap().tech_vanilla.push(TechnologyState { tech_type: tech, discovered: true, ..Default::default() });
        add_city(&mut s, 1, 5, 5);
        s.tribes.get_mut(&1).unwrap().cities[0]._territory = crate::functions::get_square_indices(idx(5, 5), 1, SIZE);
        s.tiles.get_mut(&idx(6, 6)).unwrap().terrain_type = TerrainType::Water;
        s.resources.insert(idx(6, 6), Some(ResourceState { resource_type: ResourceType::Fish }));
        for t in s.tiles.values_mut() {
            t.explorers.insert(1);
        }
        let h = crate::moves::HarvestMove::new(idx(6, 6)).serialize();
        assert!(crate::moves::generate_legal_moves(&s).iter().any(|m| m.serialize() == h), "{tribe:?}");
    }
}

/// CYMANTI-TECHS (L3, save counts): Cymanti research the base Sailing/Navigation/Diplomacy; Raychi come with
/// Sailing (21/21), Boomchi with Ramming (35/35).
#[test]
fn cymanti_techs() {
    use crate::settings::technology::{get_unlocked_units, resolve_tech_for_tribe};
    assert_eq!(resolve_tech_for_tribe(TechnologyType::Sailing, TribeType::Cymanti), TechnologyType::Sailing);
    assert_eq!(resolve_tech_for_tribe(TechnologyType::Navigation, TribeType::Cymanti), TechnologyType::Navigation);
    assert!(get_unlocked_units(TechnologyType::Sailing, TribeType::Cymanti).contains(&UnitType::Raychi));
    assert!(get_unlocked_units(TechnologyType::Ramming, TribeType::Cymanti).contains(&UnitType::Boomchi));
    assert!(!get_unlocked_units(TechnologyType::Ramming, TribeType::Imperius).contains(&UnitType::Boomchi));
}

/// DIPLO-PEACE (L3): offering peace (action 27) needs Strategy and a met tribe; the other tribe may then accept
/// or decline (action 28); one pending offer per pair; breaking peace leaves RelationState 3 on the breaker's side.
#[test]
fn peace_offer_and_reply() {
    use crate::moves::Move;
    let mut s = board();
    add_city(&mut s, 2, 8, 8);
    s.tiles.get_mut(&idx(8, 8)).unwrap().capital_of = 2;
    add_city(&mut s, 1, 2, 2);
    s.tiles.get_mut(&idx(2, 2)).unwrap().capital_of = 1;
    for (a, b) in [(1, 2), (2, 1)] {
        s.tribes.get_mut(&a).unwrap().relations.insert(b, DiplomacyRelationState::default());
        s.tribes.get_mut(&a).unwrap().known_players.insert(b);
    }
    let offer = crate::moves::abilities::diplomacy::PeaceTreatyMove::new(idx(8, 8), 2).serialize();
    let has = |s: &GameState, m: &serde_json::Value| crate::moves::generate_legal_moves(s).iter().any(|x| &x.serialize() == m);
    assert!(!has(&s, &offer)); // no Strategy
    s.tribes.get_mut(&1).unwrap().tech_vanilla.push(TechnologyState { tech_type: TechnologyType::Strategy, discovered: true, ..Default::default() });
    assert!(has(&s, &offer));
    crate::moves::abilities::diplomacy::PeaceTreatyMove::new(idx(8, 8), 2).execute(&mut s).unwrap();
    assert!(!has(&s, &offer)); // pending
    s.settings.current_player_turn_id = 2;
    let accept = crate::moves::abilities::diplomacy::PeaceRequestResponse::new(1, 1);
    assert!(has(&s, &accept.serialize()));
    accept.execute(&mut s).unwrap();
    assert!(crate::functions::is_at_peace(&s, 1, 2) && crate::functions::is_at_peace(&s, 2, 1));
    crate::moves::abilities::diplomacy::BreakPeaceMove::new(1).execute(&mut s).unwrap();
    assert_eq!((s.tribes[&2].relations[&1].state, s.tribes[&1].relations[&2].state), (3, 0));
}

/// ECON-MARKET-CLATHRUS (L3): Clathrus +1 per adjacent Fungi (v123 card), not Algae (upstream).
/// 9be1198d t7->8, player 1 (Cymanti): level 2 capital (18,4) with a Workshop, Fungi (19,4), Clathrus (19,5) and
/// (20,5) both next to it: 2 + 1 + 1 + 2 = 6 from that city.
#[test]
fn clathrus_counts_fungi() {
    use crate::functions::get_city_production;
    let mut s = board();
    add_city(&mut s, 1, 5, 5);
    s.tiles.get_mut(&idx(5, 5)).unwrap().capital_of = 1;
    for (x, y) in [(6, 5), (6, 6), (7, 6), (8, 6)] {
        let t = s.tiles.get_mut(&idx(x, y)).unwrap();
        t.owner = 1;
        t.ruling_city_coords = Some(Coords::from_xy(5, 5, SIZE));
        s.tribes.get_mut(&1).unwrap().cities[0]._territory.push(idx(x, y));
    }
    {
        let c = &mut s.tribes.get_mut(&1).unwrap().cities[0];
        c.level = 2; c.production = 2; c.rewards.push(CityRewardType::Workshop);
    }
    let st = |t| Some(StructureState { structure_type: t, level: 1, founded: 0 });
    s.structures.insert(idx(6, 5), st(StructureType::Fungi));
    s.structures.insert(idx(6, 6), st(StructureType::Clathrus));
    s.structures.insert(idx(7, 6), st(StructureType::Clathrus));
    s.tiles.get_mut(&idx(8, 6)).unwrap().effects.insert(TileEffect::Algae);   // next to one Clathrus: not counted
    assert_eq!(get_city_production(&s, &s.tribes[&1].cities[0]), 6);
}

/// CITY-LEVEL-BY-REWARD (L3): the turn's income is paid before Fungi growth, so a level that growth brings counts
/// from the next turn (the level is the CityReward's, chosen after the income).
/// e15f392c turn 5, player 14 (Cymanti, Hard): level 2 capital with a Workshop and Fungi next to it gets 5 stars
/// (2 + capital 1 + Workshop 1 + bot bonus 1), then takes its level-3 CityReward; Polyfish paid 6.
#[test]
fn income_before_fungi_growth() {
    use crate::moves::EndTurnMove;
    let mut s = board();
    s.settings.turn = 4;
    s.settings._max_tribe_count = 2;
    add_city(&mut s, 2, 5, 5);
    {
        let c = &mut s.tribes.get_mut(&2).unwrap().cities[0];
        c.level = 2; c.production = 2; c.progress = 2; c.population = 4;
    }
    s.tiles.get_mut(&idx(5, 4)).unwrap().owner = 2;
    s.tiles.get_mut(&idx(5, 4)).unwrap().ruling_city_coords = Some(Coords::from_xy(5, 5, SIZE));
    s.structures.insert(idx(5, 4), Some(StructureState { structure_type: StructureType::Fungi, level: 1, founded: 2 }));
    let mut g = crate::game::Game { state: s };
    let before = g.state.tribes[&2].stars;
    g.play_move(&EndTurnMove).unwrap();
    assert_eq!(g.state.settings.current_player_turn_id, 2);
    assert_eq!(g.state.tribes[&2].cities[0].level, 3, "Fungi growth still levels the city");
    assert_eq!(g.state.tribes[&2].stars - before, 2, "income from the level before growth");
}

/// PERSIST-KILL-MOVE (L3): a Persist unit that kills moves in and may attack again the same turn.
/// af181c8f t17 #2381-2382: Knight 369 (moved first) kills a 10 HP Warrior, moves onto its tile, attacks again.
#[test]
fn persist_attacks_again_after_kill() {
    let mut s = board();
    let a = add_unit(&mut s, 1, UnitType::Knight, 4, 5, 10.0);
    s.tribes.get_mut(&1).unwrap().units[a].moved = true;
    add_unit(&mut s, 2, UnitType::Warrior, 5, 5, 10.0);
    add_unit(&mut s, 2, UnitType::Defender, 6, 6, 15.0);
    attack(&mut s, a, 0);
    let u = unit(&s, 1, a);
    assert_eq!(s.tribes[&2].units.len(), 1, "the Warrior dies");
    assert_eq!(u.coords.idx, idx(5, 5), "moves in");
    assert!(!u.attacked, "may attack again");
    attack(&mut s, a, 0);
    assert!(unit(&s, 1, a).attacked, "no kill: turn over");
}
