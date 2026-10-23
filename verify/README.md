# verify/: checking the dataset without screenshots

| File | What it does |
|---|---|
| `run_all.sh` | Rebuilds the dataset and runs every check below. |
| `parse_polyfish.py` | Turns the Polyfish engine's Rust rule tables into `polyfish_tables.json`. |
| `crosscheck.py` | Compares our dataset with Polyfish field by field and writes `crosscheck_polyfish.md`. |
| `extract_enums.py` | Extracts the game's numeric ids (terrain, resource, building, unit, tribe, tech) into `game_enums.json`. |
| `state2json/` | Go tool that converts a real `.state` save into JSON. It is built on samuelyuan/polytopiamapmodelgo (MIT). |
| `analyze_map.py` | Measures real maps (`state2json` exports or Polyfish JSON states) against each open conflict. |
| `c23_models.py` | Pre-registered test for C23. It simulates three generator models and scores observations by Bayes factor. |

## Real save to report

```
state2json/state2json game.state game.json
python3 -I analyze_map.py game_enums.json game.json more.json --out report.json
```

## Scoring capital counts from the test sheet

1. Write the counts as a JSON list:

   ```json
   [{"tribe": "Imperius", "visible_total": 3}, {"tribe": "Bardur", "full_total": 5}]
   ```

   Use `full_total` only when every resource is visible, either from a save or because the tribe already has the right techs.

2. Run the scorer on that file:

   ```
   python3 -I c23_models.py obs.json
   ```

## Build notes

- The cloud workspace cannot reach crates.io, pypi or proxy.golang.org.
- Go dependencies build with `GOPROXY=direct GOSUMDB=off GOFLAGS=-mod=mod`, which fetches them from GitHub.
- Polyfish's Rust engine cannot be built here until crates.io is allowed.

## The one sample tested

The analyser was tested on Polyfish's `saved_state.json` (game version 115, turn 11).

This file is a pipeline test only, not evidence: harvested resources are already gone by turn 11, and the file may be a simulator game.
