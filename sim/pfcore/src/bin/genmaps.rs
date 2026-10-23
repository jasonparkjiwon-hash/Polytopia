//! Generate maps with Polyfish's generator and write each GameState as JSON (one file per map).
//! usage: genmaps <out_dir> <n> <map_type 1..6> <size 0..5> <seed0> <tribe ids comma-separated, cycled 4 per map>
use polyfish::mapgen::{generate, MapGenSettings};
use polyfish::types::{MapSize, MapType, TribeType};
use std::fs;

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let out = &a[1];
    let n: usize = a[2].parse().unwrap();
    let mt = match a[3].as_str() { "1" => MapType::Drylands, "2" => MapType::Lakes, "3" => MapType::Continents, "4" => MapType::Archipelago, "5" => MapType::WaterWorld, _ => MapType::Pangea };
    let size = match a[4].as_str() { "0" => MapSize::Tiny, "1" => MapSize::Small, "2" => MapSize::Normal, "3" => MapSize::Large, "4" => MapSize::Huge, _ => MapSize::Massive };
    let seed0: i64 = a[5].parse().unwrap();
    let pool: Vec<TribeType> = a[6].split(',').map(|s| TribeType::from_repr(s.parse().unwrap()).unwrap()).collect();
    let per = if a.len() > 7 { a[7].parse().unwrap() } else { 4usize };
    fs::create_dir_all(out).unwrap();
    for i in 0..n {
        let tribes: Vec<TribeType> = (0..per).map(|k| pool[(i * per + k) % pool.len()]).collect();
        let st = generate(MapGenSettings { size, map_type: mt, tribes, seed: seed0 + i as i64, version: 115, symmetric: false });
        fs::write(format!("{}/map_{:05}.json", out, i), serde_json::to_string(&st).unwrap()).unwrap();
    }
    println!("wrote {} maps", n);
}
