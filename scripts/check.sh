#!/bin/sh
# Smoke test: replay the two reference games and print how many units match the real saves.
# Baseline (README.md): Ankiian 27,33,39,43,51,59,66 exact; bot war 66/66, 85/92, 106/118.
set -e
D=$(cd "$(dirname "$0")/.." && pwd); cd "$D/engine"
A=../saves/1bf60251-4e7a-4d43-9043-ffc90bf46c31
B=../saves/6e1bf8e0-1271-4f48-95c0-0fef5e449a63
echo "== Ankiian, turn by turn"
python3 replay.py ${A}_t7.json ${A}_t1.json ${A}_t2.json ${A}_t3.json ${A}_t4.json ${A}_t5.json ${A}_t6.json | grep "after"
echo "== Bot war (15 Crazy bots)"
python3 replay.py ${B}_t15.json ${B}_t5.json ${B}_t11.json | grep "after"
