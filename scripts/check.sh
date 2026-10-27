#!/bin/sh
# Smoke test: replay the two reference games and print how many units match the real saves.
# Baseline (README.md): Ankiian 27,33,39,43,51,59,66 exact; bot war 66/66, 90/92, 111/122; Misty Fields see README.; stars see README
set -e
D=$(cd "$(dirname "$0")/.." && pwd); cd "$D/engine"
echo "== Rule labels (every engine rule has a ledger id: tools/rule_levels.py)"
python3 -I ../tools/rule_levels.py --check
A=../saves/1bf60251-4e7a-4d43-9043-ffc90bf46c31
B=../saves/6e1bf8e0-1271-4f48-95c0-0fef5e449a63
echo "== Ankiian, turn by turn"
python3 replay.py ${A}_t7.json ${A}_t1.json ${A}_t2.json ${A}_t3.json ${A}_t4.json ${A}_t5.json ${A}_t6.json | grep "after"
echo "== Bot war (15 Crazy bots)"
python3 replay.py ${B}_t15.json ${B}_t5.json ${B}_t11.json | grep "after"
C=../saves/e15f392c-e542-4777-a16f-64a63932d141
echo "== Misty Fields, turn by turn (Hard, 16 players)"
python3 replay.py ${C}_t16.json $(for t in $(seq 1 15); do printf "${C}_t$t.json "; done) | grep "after"
G=$(ls ../saves/09a5bf1e-*_t*.json | sort -t t -k3 -n | tr '\n' ' ')
echo "== Cliff & Gods, turn by turn (Crazy, 16 players)"
python3 replay.py $(ls ../saves/09a5bf1e-*_t8.json) $(ls ../saves/09a5bf1e-*_t*.json | grep -v _t8.json | sort -t t -k3 -n) | grep "after"
echo "== Stars and income (engine/economy.py): player-turns with exact stars"
python3 economy.py ${A}_t1.json ${A}_t2.json ${A}_t3.json ${A}_t4.json ${A}_t5.json ${A}_t6.json ${A}_t7.json | tail -1
python3 economy.py ${B}_t5.json ${B}_t11.json ${B}_t15.json | tail -1
python3 economy.py $(for t in $(seq 1 16); do printf "${C}_t$t.json "; done) | tail -1
python3 economy.py $G | tail -1
echo "== Polyfish forward model (informational, not part of the baseline): tools/pf_miss.py"
python3 -I ../tools/pf_miss.py --accept 2>/dev/null | grep "^PF ACCEPT" || echo "pf_miss skipped (build sim/pfcore first)"
echo "== Polyfish forward-model acceptance (informational, not part of the baseline): tools/pf_accept.py"
python3 -I ../tools/pf_accept.py 2>/dev/null | grep "^FM ACCEPT" || echo "pf_accept skipped (build sim/pfcore first)"
echo "== What-if tool validation (informational, not part of the baseline): tools/whatif_validate.py"
python3 -I ../tools/whatif_validate.py --summary 2>/dev/null | grep "^WHATIF" || echo "whatif_validate skipped (build sim/pfcore first)"
echo "== Win-percentage playouts (informational, not part of the baseline): tools/winpct_eval.py smoke"
python3 -I ../tools/winpct_eval.py smoke 2>/dev/null | grep "^WINPCT SMOKE" || echo "winpct smoke skipped (build sim/pfcore first)"
