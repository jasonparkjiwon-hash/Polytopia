//! Capital connection logic
//!
//! Handles detecting networks of cities connected by roads and ports.

use crate::actions::UndoCallback;
use crate::actions::chain_undos;
use crate::actions::city::add_population;
use crate::functions::get_capital_city;
use crate::states::GameState;
use crate::types::{StructureType, TerrainType, TribeType};
use std::collections::{HashSet, VecDeque};

/// Update capital connections for a tribe
///
/// Should be called after building roads or ports.
pub fn update_capital_connections(state: &mut GameState, tribe_id: i32) -> UndoCallback {
    use crate::functions::is_enemy;
    let _map_size = state.settings.size;

    // Find capital
    let capital_idx = if let Some(cap) = get_capital_city(state, tribe_id) {
        cap.idx
    } else {
        return Box::new(|_| {});
    };

    // Identify all cities
    let tribe = match state.tribes.get(&tribe_id) {
        Some(t) => t,
        None => return Box::new(|_| {}),
    };

    let city_indices: HashSet<i32> = tribe.cities.iter().map(|c| c.idx).collect();

    // BFS to find all connected tiles from Capital
    // Connectivity rules:
    // - Roads connect to adjacent Roads or Cities.
    // - Ports connect to other Ports via Water/Ocean.

    let mut connected_cities = HashSet::new();
    let mut visited = HashSet::new();
    let mut queue = VecDeque::new();

    // Start at capital
    queue.push_back(capital_idx);
    visited.insert(capital_idx);
    connected_cities.insert(capital_idx);

    while let Some(current_idx) = queue.pop_front() {
        let tribe_type = tribe.tribe_type;

        let is_port = has_port(state, current_idx);
        let current_has_road = has_road(state, current_idx)
            || city_indices.contains(&current_idx)
            || has_algae(state, current_idx)
            || is_port;
        let current_has_mycelium =
            has_mycelium(state, current_idx) || city_indices.contains(&current_idx);

        let neighbors = crate::functions::get_adjacent_indices(state, current_idx, 1);
        for n_idx in neighbors {
            if visited.contains(&n_idx) {
                continue;
            }

            let n_has_road =
                has_road(state, n_idx) || city_indices.contains(&n_idx) || has_port(state, n_idx);
            let n_has_algae = has_algae(state, n_idx);
            let n_has_mycelium = has_mycelium(state, n_idx);

            // Connections cannot pass through enemy-owned tiles
            let n_owner = state.tiles.get(&n_idx).map(|t| t.owner).unwrap_or(0);
            if n_owner != 0 && is_enemy(state, tribe_id, n_owner) {
                continue;
            }

            let mut connected = false;

            if tribe_type == TribeType::Cymanti {
                // Cymanti connections: Mycelium/Cities connect via Algae/Roads (if any) or adjacency
                // But specifically Mycelium has 4-range connection.
                if (current_has_mycelium || current_has_road || has_algae(state, current_idx))
                    && (n_has_road
                        || n_has_algae
                        || city_indices.contains(&n_idx)
                        || n_has_mycelium)
                {
                    connected = true;
                }
            } else if tribe_type == TribeType::Polaris {
                // v123 (ledger OUTPOST-NETWORK, pf-port): roads, cities and ports as usual, plus the tribe's
                // Outposts and any ice within 2 tiles (5x5) of one of them
                if polaris_net(state, tribe_id, current_idx, &city_indices)
                    && polaris_net(state, tribe_id, n_idx, &city_indices)
                {
                    connected = true;
                }
            } else {
                // Standard road connection
                if current_has_road && n_has_road {
                    connected = true;
                }
            }

            if connected {
                visited.insert(n_idx);
                queue.push_back(n_idx);
                if city_indices.contains(&n_idx) {
                    connected_cities.insert(n_idx);
                }
            }
        }

        // v123 (ledger ATOLL-NETWORK, pf-port): Aquarion Atoll long-range connection (3 radius),
        // Atoll-to-City/Atoll or City-to-Atoll, as Mycelium below
        if tribe_type == TribeType::Aquarion {
            let own_atoll = |i: i32| {
                state.tiles.get(&i).map_or(false, |t| t.owner == tribe_id)
                    && state.structures.get(&i).and_then(|s| s.as_ref()).map_or(false, |s| s.structure_type == StructureType::Atoll)
            };
            let from_atoll = own_atoll(current_idx);
            if from_atoll || city_indices.contains(&current_idx) {
                for target_idx in crate::functions::get_adjacent_indices(state, current_idx, 3) {
                    if visited.contains(&target_idx) {
                        continue;
                    }
                    let target_is_city = city_indices.contains(&target_idx);
                    if own_atoll(target_idx) || (from_atoll && target_is_city) {
                        visited.insert(target_idx);
                        queue.push_back(target_idx);
                        if target_is_city {
                            connected_cities.insert(target_idx);
                        }
                    }
                }
            }
        }

        // Cymanti Mycelium long-range connection (4 radius)
        if tribe_type == TribeType::Cymanti {
            let is_city = city_indices.contains(&current_idx);
            let is_mycelium = has_mycelium(state, current_idx);

            if is_city || is_mycelium {
                let radius_indices = crate::functions::get_adjacent_indices(state, current_idx, 4);
                for target_idx in radius_indices {
                    if visited.contains(&target_idx) {
                        continue;
                    }

                    let target_is_city = city_indices.contains(&target_idx);
                    let target_is_mycelium = has_mycelium(state, target_idx);

                    // Rule: Mycelium-to-City/Mycelium or City-to-Mycelium
                    // But NOT City-to-City directly at range 4
                    let can_connect = (is_mycelium && (target_is_city || target_is_mycelium))
                        || (is_city && target_is_mycelium);

                    if can_connect {
                        // Path check: through field, forest, or algae
                        if has_cymanti_path(state, state.settings.size, current_idx, target_idx) {
                            visited.insert(target_idx);
                            queue.push_back(target_idx);
                            if target_is_city {
                                connected_cities.insert(target_idx);
                            }
                        }
                    }
                }
            }
        }

        // v123 (ledger WATER-ROUTE): a port links over water (up to 5 steps, not through enemy tiles) to other
        // own ports and to own cities that have a port beside them
        if is_port && tribe_type != TribeType::Cymanti {
            for target_idx in water_route_targets(state, current_idx, tribe_id, &city_indices) {
                if visited.insert(target_idx) {
                    queue.push_back(target_idx);
                    if city_indices.contains(&target_idx) {
                        connected_cities.insert(target_idx);
                    }
                }
            }
        }
    }

    // Apply changes
    let mut undos = Vec::new();
    let mut capital_pop_gain = 0;

    // We need to borrow tribe mutably again.
    // BUFFER updates to avoid borrow conflict
    let mut city_pop_changes: Vec<(i32, i32)> = Vec::new();
    // (city tile idx, flag value before the flip) — for undo
    let mut updates: Vec<(i32, bool)> = Vec::new();

    if let Some(tribe) = state.tribes.get_mut(&tribe_id) {
        for (_idx, city) in tribe.cities.iter_mut().enumerate() {
            if city.idx == capital_idx {
                continue;
            }

            let is_connected_now = connected_cities.contains(&city.idx);
            if is_connected_now && !city.connected_to_capital {
                city.connected_to_capital = true;
                city_pop_changes.push((city.idx, 1));
                updates.push((city.idx, false));
                capital_pop_gain += 1;
            } else if !is_connected_now && city.connected_to_capital {
                // Connection lost
                city.connected_to_capital = false;
                city_pop_changes.push((city.idx, -1));
                updates.push((city.idx, true));
                capital_pop_gain -= 1;
            }
        }
    }

    // Apply population bonus for newly connected/disconnected cities
    for (city_tile_idx, amount) in city_pop_changes {
        undos.push(add_population(state, city_tile_idx, amount));
    }

    // Apply population bonus to Capital
    if capital_pop_gain != 0 {
        if let Some(cap) = crate::functions::get_capital_city(state, tribe_id) {
            undos.push(add_population(state, cap.idx, capital_pop_gain));
        }
    }

    // Restore each flipped city's flag to its pre-update value
    // (add_population undos handle the population side).
    undos.push(Box::new(move |s| {
        if let Some(t) = s.tribes.get_mut(&tribe_id) {
            for c in t.cities.iter_mut() {
                if let Some(&(_, old_flag)) = updates.iter().find(|(idx, _)| *idx == c.idx) {
                    c.connected_to_capital = old_flag;
                }
            }
        }
    }));

    chain_undos(undos)
}

/// A Polaris network tile (ledger OUTPOST-NETWORK): road, city, port, own Outpost, or ice within 2 of an own Outpost.
fn polaris_net(state: &GameState, tribe_id: i32, idx: i32, cities: &HashSet<i32>) -> bool {
    let own_outpost = |i: i32| {
        state.tiles.get(&i).map_or(false, |t| t.owner == tribe_id)
            && state.structures.get(&i).and_then(|s| s.as_ref()).map_or(false, |s| s.structure_type == StructureType::Outpost)
    };
    if has_road(state, idx) || cities.contains(&idx) || has_port(state, idx) || own_outpost(idx) {
        return true;
    }
    state.tiles.get(&idx).map_or(false, |t| t.is_frozen())
        && crate::functions::get_adjacent_indices(state, idx, 2).into_iter().any(own_outpost)
}

fn has_port(state: &GameState, idx: i32) -> bool {
    state
        .structures
        .get(&idx)
        .and_then(|s| s.as_ref())
        .map(|s| s.structure_type == StructureType::Port)
        .unwrap_or(false)
}

fn has_road(state: &GameState, idx: i32) -> bool {
    state.tiles.get(&idx).map(|t| t.has_road).unwrap_or(false)
        || state
            .structures
            .get(&idx)
            .and_then(|s| s.as_ref())
            .map(|s| s.structure_type == StructureType::Bridge)
            .unwrap_or(false)
}

fn has_mycelium(state: &GameState, idx: i32) -> bool {
    state
        .structures
        .get(&idx)
        .and_then(|s| s.as_ref())
        .map(|s| s.structure_type == StructureType::Mycelium)
        .unwrap_or(false)
}

fn has_algae(state: &GameState, idx: i32) -> bool {
    state
        .tiles
        .get(&idx)
        .map(|t| t.has_effect(crate::types::TileEffect::Algae))
        .unwrap_or(false)
}

/// Own ports and own port-side cities reachable from the port at `src` over water or ocean in at most 5 steps,
/// not through enemy-owned tiles (the HasWaterRoute tile flag in the saves marks these routes)
fn water_route_targets(state: &GameState, src: i32, tribe_id: i32, cities: &HashSet<i32>) -> Vec<i32> {
    use crate::functions::is_enemy;
    let mut seen: HashSet<i32> = HashSet::new();
    let mut out = Vec::new();
    let mut frontier = vec![src];
    seen.insert(src);
    for _ in 0..WATER_ROUTE_STEPS {
        let mut next = Vec::new();
        for curr in frontier {
            for n in crate::functions::get_adjacent_indices(state, curr, 1) {
                if !seen.insert(n) {
                    continue;
                }
                let tile = match state.tiles.get(&n) {
                    Some(t) => t,
                    None => continue,
                };
                if tile.owner != 0 && is_enemy(state, tribe_id, tile.owner) {
                    continue;
                }
                if tile.owner == tribe_id && has_port(state, n) {
                    out.push(n);
                    next.push(n);
                } else if cities.contains(&n) {
                    let port_beside = crate::functions::get_adjacent_indices(state, n, 1)
                        .into_iter()
                        .any(|a| has_port(state, a) && state.tiles.get(&a).map_or(false, |t| t.owner == tribe_id));
                    if port_beside {
                        out.push(n);
                    }
                } else if is_water(tile.terrain_type) {
                    next.push(n);
                }
            }
        }
        frontier = next;
    }
    out
}

const WATER_ROUTE_STEPS: i32 = 5;

fn is_water(terrain: TerrainType) -> bool {
    matches!(terrain, TerrainType::Water | TerrainType::Ocean)
}

fn has_cymanti_path(state: &GameState, size: i32, src: i32, dest: i32) -> bool {
    let sx = src % size;
    let sy = src / size;

    // BFS path check
    let mut visited = HashSet::new();
    let mut queue = VecDeque::new();
    queue.push_back(src);
    visited.insert(src);

    while let Some(curr) = queue.pop_front() {
        if curr == dest {
            return true;
        }

        let dist = (curr % size - sx).abs().max((curr / size - sy).abs());
        if dist >= 4 && curr != src {
            continue;
        } // Max radius 4

        let adj = crate::functions::get_adjacent_indices(state, curr, 1);
        for n in adj {
            if visited.contains(&n) {
                continue;
            }
            let tile = match state.tiles.get(&n) {
                Some(t) => t,
                None => continue,
            };

            // Path must be any land terrain or algae on water
            let valid_terrain = match tile.terrain_type {
                TerrainType::Field
                | TerrainType::Forest
                | TerrainType::Mountain
                | TerrainType::Ice => true,
                _ => has_algae(state, n),
            };

            if valid_terrain || n == dest {
                visited.insert(n);
                queue.push_back(n);
            }
        }
    }

    false
}
