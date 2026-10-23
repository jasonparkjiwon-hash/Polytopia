//! Speed check for the simulator comparison (gate F): random legal moves on a generated map.
//! usage: bench <moves> <map size 0..5> <tribes>
use polyfish::game::Game;
use polyfish::mapgen::{generate, MapGenSettings};
use polyfish::types::{MapSize, MapType, TribeType};
use std::time::Instant;

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let n: usize = a.get(1).map(|s| s.parse().unwrap()).unwrap_or(20000);
    let size = match a.get(2).map(|s| s.as_str()) { Some("5") => MapSize::Massive, Some("3") => MapSize::Large, _ => MapSize::Normal };
    let k: usize = a.get(3).map(|s| s.parse().unwrap()).unwrap_or(4);
    let tribes: Vec<TribeType> = (1..=k as i8).map(|i| TribeType::from_repr(i).unwrap()).collect();
    let state = generate(MapGenSettings { size, map_type: MapType::Continents, tribes, seed: 7, version: 115, symmetric: false });
    let mut game = Game { state };
    game.post_load();
    let mut rng: u64 = 0x9E3779B97F4A7C15;
    let t = Instant::now();
    let (mut played, mut gen_calls) = (0usize, 0usize);
    while played < n && !game.is_game_over() {
        let moves = game.legal_moves(); gen_calls += 1;
        if moves.is_empty() { break; }
        rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17;
        game.play_move(moves[(rng % moves.len() as u64) as usize].as_ref());
        played += 1;
    }
    let dt = t.elapsed().as_secs_f64();
    let t2 = Instant::now();
    for _ in 0..200 { let _c = game.clone_game(); }
    let clone_ms = t2.elapsed().as_secs_f64() / 200.0 * 1000.0;
    println!("{} random moves ({} move generations) in {:.2}s -> {:.0} moves/s; turn {}; clone {:.3} ms",
             played, gen_calls, dt, played as f64 / dt, game.turn(), clone_ms);
}
