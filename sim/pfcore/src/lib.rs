//! Slim build of the Polyfish game engine (HenBOMB/Polyfish polyfish-rs, Apache-2.0):
//! engine modules only (no AI, network, replay or server), so it builds from GitHub sources alone.
pub mod actions;
pub mod belief;
pub mod api;
pub mod botpolicy;
pub mod botpolicy2;
pub mod coords;
pub mod dotnet_rng;
pub mod fog;
pub mod fow;
pub mod functions;
pub mod game;
pub mod hash;
pub mod mapgen;
pub mod memory;
pub mod moves;
pub mod prediction;
pub mod save_loader;
pub mod score;
pub mod settings;
pub mod states;
pub mod types;
pub mod version_sync;
pub mod whatif;
pub mod v123_flags;
pub use coords::Coords;
pub use game::Game;
pub use states::*;
pub use types::*;
mod v123_tests;
#[cfg(test)]
mod v123_legal_tests;
#[cfg(test)]
mod api_tests;
#[cfg(test)]
mod botpolicy2_tests;
