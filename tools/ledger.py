"""Edit verify/ledger.json and data/conflicts_and_gaps.md WITHOUT reading them into context.
  python3 -I tools/ledger.py ids                      list rule ids and levels (one line each)
  python3 -I tools/ledger.py get ID                   print one rule
  python3 -I tools/ledger.py add ID LEVEL VERSION "rule" "evidence"     append (or replace) a rule
  python3 -I tools/ledger.py ev ID "text" [LEVEL]     append " | text" to a rule's evidence (and set its level if given)
  python3 -I tools/ledger.py note "text"              append a bullet to data/conflicts_and_gaps.md"""
import sys, os, json
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
LP = os.path.join(ROOT, "verify", "ledger.json"); GP = os.path.join(ROOT, "data", "conflicts_and_gaps.md")
cmd = sys.argv[1]; L = json.load(open(LP))
if cmd == "ids":
    for r in L["rules"]: print(r["id"], "|", r["level"][:40])
elif cmd == "get":
    print(json.dumps([r for r in L["rules"] if r["id"] == sys.argv[2]], indent=1, ensure_ascii=False))
elif cmd == "add":
    _, _, i, lv, ver, rule, ev = sys.argv
    L["rules"] = [r for r in L["rules"] if r["id"] != i] + [{"id": i, "rule": rule, "level": lv, "game_version": ver, "evidence": ev}]
    json.dump(L, open(LP, "w"), indent=1, ensure_ascii=False); print("ok", i, len(L["rules"]), "rules")
elif cmd == "ev":
    r = next(r for r in L["rules"] if r["id"] == sys.argv[2]); r["evidence"] += " | " + sys.argv[3]
    if len(sys.argv) > 4: r["level"] = sys.argv[4]
    json.dump(L, open(LP, "w"), indent=1, ensure_ascii=False); print("ok", r["id"], "|", r["level"][:40])
elif cmd == "note":
    open(GP, "a").write("- " + sys.argv[2] + "\n"); print("ok")
