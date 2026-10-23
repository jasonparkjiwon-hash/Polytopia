#!/bin/sh
# Rebuild saves/ (decoded JSON + index.json) from the raw .state files kept in saves_raw/. Takes about a minute. Run once per new session.
set -e
D=$(cd "$(dirname "$0")/.." && pwd); mkdir -p "$D/saves"
python3 -I "$D/verify/ingest_saves.py" "$D/saves" "$D"/saves_raw/*.state > /dev/null
echo "restored $(ls "$D"/saves/*.json | wc -l) json files in saves/"
