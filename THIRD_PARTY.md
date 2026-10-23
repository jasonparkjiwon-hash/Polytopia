# Third-party sources

These were used as references and are not committed. `scripts/fetch_third_party.sh` clones them into `ext/` at the commits used.

| Repo | Commit | Used for |
|---|---|---|
| HenBOMB/Polyfish | a9f90ab | Rules tables for the cross-check (`verify/parse_polyfish.py`); `sim/pfcore/` is copied from `polyfish-rs/src` (Apache-2.0) |
| GAIGResearch/Tribes | 270e7e5 | Older Java engine; history only |
| DylanHannaScience/polytopia_python | 97746bb | Older Python engine; history only |
| samuelyuan/polytopiamapmodelgo | d09f4e0 | Save reader the Go `state2json` tool is built on (MIT) |
| samuelyuan/PolytopiaSaveEditor | b20890f | Save format reference |
| samuelyuan/PolytopiaMapEditor | 440439b | Map format reference |
| samuelyuan/PolytopiaWorld | 021787e | Map rendering reference |
| Bibliofile/polytopia | 20a83b5 | Reference |
| JThh/polytopia-ext | 71788c3 | Reference |
| PolyModdingTeam/PolyMod | 7972052 | Mod loader (Polyfish's replay scraper runs on it) |
| amigobrewbrew/polytopiacalculatorfirebase-public | latest | Damage calculator; `src/config/v116.json` unit table copied into `engine/stats.py` |

`data/raw/` holds text extracted from PolyEnv (the C++ engine) for audit.

`sim/pfcore/` builds with `cargo build --release` (it fetches dependencies from crates.io). The offline build used vendored crates; `sim/vendor_list.txt` lists them.
