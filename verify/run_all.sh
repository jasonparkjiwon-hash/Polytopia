#!/bin/sh
# Rebuild the dataset, then run every check. Exit non-zero if a hard check fails.
set -e
D=$(cd "$(dirname "$0")/.." && pwd)
python3 -I "$D/data/build_dataset.py" > /dev/null
python3 -I "$D/data/validate_dataset.py" | tail -3
PF="$D/ext/HenBOMB_Polyfish/polyfish-rs/src"
if [ -d "$PF" ]; then
  python3 -I "$D/verify/parse_polyfish.py" "$PF" "$D/verify/polyfish_tables.json"
  python3 -I "$D/verify/crosscheck.py" "$D/data" "$D/verify/polyfish_tables.json" "$D/verify/crosscheck_polyfish.md" "$D/verify/crosscheck_polyfish.json" | head -1
fi
python3 -I "$D/verify/c23_models.py" | head -17 > "$D/verify/c23_summary.txt"
echo "all checks ran"
