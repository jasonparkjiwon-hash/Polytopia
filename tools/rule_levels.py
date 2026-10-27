"""Label every rule the engine applies with its ledger id and evidence level.
  python3 -I tools/rule_levels.py           write data/rule_levels.json (rule -> ledger id, level, file:line, unverified)
  python3 -I tools/rule_levels.py --check   exit 1 if an engine rule has no ledger id, or its id is not in the ledger
Rules found automatically: RULES switches in engine/replay.py (incl. RULES.get), ECON_RULES in engine/economy.py,
upper-case module constants in both files, and the action handlers in replay.apply. Hand-listed: the formula functions.
A new switch or constant fails --check until it gets a line in MAP below (and a ledger entry via tools/ledger.py).
'unverified' = below L1, or a rule no save has tested yet (UNTESTED below): a simulation should flag moves that rely on it."""
import sys, os, re, json
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FILES = {"replay": "engine/replay.py", "economy": "engine/economy.py"}
SKIP = {"HERE", "ROOT", "LOG", "EVENTS", "TEMP", "RUIN", "ORACLE", "RUIN_SEEN", "PREV", "RULES", "ECON_RULES", "FMT_", "E", "STATS"}   # bookkeeping, not rules

MAP = {   # rule name -> ledger id
    # replay.py RULES switches
    "replay.RULES.infiltrate": "INFILTRATE",
    "replay.RULES.retaliation_uses_bonus": "C6",
    "replay.RULES.melee_moves_in_on_kill": "KILL-MOVE-IN",
    "replay.RULES.t18_disband": "ACTION-18-BREAK-ICE",          # the old reading of action 18, kept off
    "replay.RULES.t18_break_ice": "ACTION-18-BREAK-ICE",
    "replay.RULES.t24_explode": "EXPLODE-DAMAGE",
    "replay.RULES.t38_swarm": "ACTION-TYPES-V123",
    "replay.RULES.t38_attack_boost": "ACTION-TYPES-V123",
    "replay.RULES.mooni_freezes_units": "MOONI-FREEZE-UNITS",
    "replay.RULES.retaliation_needs_sight": "C20",
    "replay.RULES.frozen_no_retaliation": "FROZEN-NO-RETALIATION",
    "replay.RULES.freeze_on_hit": "FROZEN-NO-RETALIATION",
    "replay.RULES.tribe_super_unit": "SUPER-UNIT-BY-TRIBE",
    "replay.RULES.bridge_is_land": "BRIDGE-LAND",
    "replay.RULES.stomp": "STOMP",
    "replay.RULES.summon_promotion": "RUIN-UNIT-SPAWN",
    "replay.RULES.peace_spares_area_damage": "PEACE-AREA-DAMAGE",
    "replay.RULES.stiff_moves_in": "JUGGERNAUT-KILL-MOVE",
    "replay.RULES.explode_poison": "EXPLODE-POISON",
    "replay.RULES.t4_heal": "ACTION-4-HEAL",
    "replay.RULES.stomp_poison": "STOMP",
    "replay.RULES.port_boards": "PORT-BOARDS",
    "replay.RULES.t17_freeze_area": "ACTION-17-FREEZE-AREA",
    "replay.RULES.explode_round": "EXPLODE-DAMAGE",
    "replay.RULES.explode_round_by_type": "EXPLODE-DAMAGE",
    "replay.RULES.hidden_attacker_no_retaliation": "CLOAK-DAGGER-RETALIATION",
    "replay.RULES.algae_is_land": "FLOOD-ALGAE",
    "replay.RULES.flood_keeps_form": "FLOOD-ALGAE",
    "replay.RULES.resync_terrain": "ENGINE-RESYNC",
    "replay.RULES.resync_territory": "ENGINE-RESYNC",
    "replay.RULES.recover_lost_defender": "ENGINE-RESYNC",
    "replay.RULES.kill_move_lands": "KILL-MOVE-IN",
    "replay.RULES.push_polyfish": "PUSH-DIRECTION",
    "replay.RULES.push_needs_climbing": "PUSH-TERRAIN",
    "replay.RULES.ruin_unit": "RUIN-UNIT-SPAWN",
    "replay.RULES.mooni_freeze": "MOONI-FREEZE",
    "replay.RULES.mooni_freezes": "MOONI-FREEZE",
    "replay.RULES.water_units_stay": "WATER-UNITS",
    "replay.RULES.shaman_convert": "SHAMAN",
    "replay.RULES.shaman_damage": "SHAMAN",
    "replay.RULES.poison": "C7",
    "replay.RULES.attack_splash": "SPLASH",
    "replay.RULES.poison_recover_cures": "C7",
    "replay.RULES.freezers": "GAAMI-FREEZE",
    "replay.RULES.giant_juggernaut": "GIANT-JUGGERNAUT",
    "replay.RULES.port_kill_embark": "PORT-KILL-EMBARK",
    "replay.RULES.algae_keeps_boats": "ALGAE-KEEPS-BOATS",
    "replay.RULES.push_onto_port": "PUSH-ONTO-PORT",
    "replay.RULES.no_cities_no_units": "NO-CITIES-NO-UNITS",
    "replay.RULES.territory": "CAPTURE-TERRITORY",
    "replay.RULES.boat_new_id": "BOAT-IDS",
    "replay.RULES.peace_break_disbands": "DIPLO-BREAK-DISBAND",
    "replay.RULES.break_ice_after_move_needs_dash": "ACTION-18-AFTER-MOVE",
    "replay.RULES.ruin_unseen_swordsman": "RUIN-UNIT-UNSEEN",
    "replay.RULES.kill_move_needs_climbing": "KILL-MOVE-CLIMBING",
    "replay.RULES.stiff_boat_lands": "JUGGERNAUT-KILL-MOVE",
    "replay.RULES.stomp_on_kill_move": "JUGGERNAUT-KILL-MOVE",
    "replay.RULES.move_blocked_by_hidden": "MOVE-BLOCKED-HIDDEN",
    "replay.RULES.stomp_after_boarding": "STOMP-ON-BOARDING",
    "replay.RULES.ruin_boat_passenger": "RUIN-BOAT-PASSENGER",
    "replay.RULES.push_port_first_only": "PUSH-PORT-FIRST",
    "replay.RULES.push_toward_attacker": "PUSH-NEVER-MOVED",
    "replay.RULES.push_centre_round": "PUSH-NEVER-MOVED",
    "replay.RULES.push_dir_persists": "PUSH-DIRECTION",
    "replay.RULES.polaris_capture_freezes": "POLARIS-CAPTURE-FREEZE",
    "replay.RULES.idle_auto_recover": "IDLE-AUTO-RECOVER",
    "replay.RULES.explode_poison_halves": "EXPLODE-POISON-DEFENCE",
    "replay.RULES.push_saved_facing": "SAVE-UNIT-FACING",
    "replay.RULES.push_ccw_first": "PUSH-TIEBREAK",
    "replay.RULES.push_no_room_removes": "PUSH-TIEBREAK",
    "replay.RULES.push_dir_round": "PUSH-DIRECTION",
    # economy.py ECON_RULES switches
    "economy.ECON_RULES.embassy_income": "ECON-EMBASSY",
    "economy.ECON_RULES.market_income": "ECON-MARKET-CLATHRUS",
    "economy.ECON_RULES.clathrus_income": "ECON-MARKET-CLATHRUS",
    "economy.ECON_RULES.aquarion51_price": "ECON-PRICES-V123",
    # module constants
    "replay.FMT": "SAVE-FORMAT",
    "replay.LAND_UNITS": "BOAT-RECORD",
    "replay.WATER_UNITS": "WATER-UNITS",
    "replay.DIRS": "PUSH-DIRECTION",
    "replay.POISON": "ENUM-IDS",
    "replay.FROZEN": "ENUM-IDS",
    "replay.SWIFT": "ENUM-IDS",
    "replay.INVISIBLE": "ENUM-IDS",
    "replay.SUPER_UNIT": "SUPER-UNIT-BY-TRIBE",
    "replay.DASH": "ACTION-18-AFTER-MOVE",
    "economy.UNIT_COST": "UNIT-STATS-UI",
    "economy.BUILD": "C19-COSTS",
    "economy.UPGRADE_COST": "C19-COSTS",
    "economy.TIER": "TECH-COST",
    "economy.AQUARION_TIERS": "AQUARION-TECH-TIERS",
    "economy.REWARD_STARS": "CITY-REWARDS",
    "economy.ADJ_INCOME": "ECON-MARKET-CLATHRUS",
    "economy.EMBASSY_COST": "ECON-EMBASSY",
    "economy.EMBASSY_STEP": "ECON-EMBASSY",
    "economy.EMBASSY_INCOME": "ECON-EMBASSY",
    "economy.REWARD_INCOME": "CITY-REWARDS",
    "economy.RUIN_STARS": "ECON-RUIN-STARS",
    "economy.PEACE": "DIPLO-PEACE",
    "economy.WAR": "DIPLO-PEACE",
    "economy.BONUS_NEEDS_CAPITAL": "ECON-BOT-BONUS",
    "economy.BONUS_NEEDS_FREE_CAPITAL": "ECON-BOT-BONUS",
    "economy.NEG_POP": "ECON-INCOME",
    "economy.PAID_AT_TURN_START": "ECON-SAVE-TIMING",
    "economy.ROUND_START_PAID": "ROUND-START-INCOME",
    "economy.LEVEL_FROM_REWARD": "CITY-LEVEL-BY-REWARD",
    "economy.MARKET_BY_LEVEL": "ECON-MARKET-CLATHRUS",
    "economy.EMBASSY_ACTION30": "EMBASSY-ACTION",
    "economy.EMBASSY_BUILDER_PAID": "EMBASSY-INCOME-NEUTRAL",
    "economy.EMBASSY_FROM_SAVE": "EMBASSY-INCOME-NEUTRAL",
    "economy.EMBASSY_COMBAT_DESTROYS": "EMBASSY-DESTROYED-BY-COMBAT",
    "economy.SANCTUARY_INCOME": "SANCTUARY-V123",
    "economy.EMBASSY_STEP_OTHER_HOSTS": "ECON-EMBASSY",
    "economy.TRACK_PEACE": "EMBASSY-ACTION",
    # action handlers in replay.apply (what the engine does with each logged action)
    "replay.action.1": "ACTION-TYPES-V123",     # Build: only Enchant Animal spawns a unit
    "replay.action.2": "COMBAT-FORMULA",
    "replay.action.3": "HEAL-TERRITORY",
    "replay.action.4": "ACTION-4-HEAL",
    "replay.action.5": "SAVE-UNIT-IDS",
    "replay.action.6": "SAVE-FORMAT",
    "replay.action.7": "CAPTURE-TERRITORY",
    "replay.action.8": "TECH-TREE",
    "replay.action.11": "CITY-REWARDS",
    "replay.action.13": "PROMOTE-HP",
    "replay.action.14": "RUIN-UNIT-SPAWN",
    "replay.action.15": "FROZEN-NO-RETALIATION",  # end of turn: thaw, Fungi poison (C7)
    "replay.action.16": "BOAT-IDS",
    "replay.action.17": "ACTION-17-FREEZE-AREA",
    "replay.action.18": "ACTION-18-BREAK-ICE",
    "replay.action.24": "EXPLODE-DAMAGE",
    "replay.action.28": "DIPLO-PEACE",
    "replay.action.29": "DIPLO-PEACE",
    "replay.action.38": "ACTION-TYPES-V123",
}
FUNCS = {   # formula functions: rule name -> (file key, def name, ledger id)
    "replay.fight": ("replay", "fight", "COMBAT-FORMULA"),
    "replay.fight.retaliation": ("replay", "fight", "C6"),
    "replay.fight.range": ("replay", "fight", "RET-RANGE"),
    "replay.defence_bonus": ("replay", "defence_bonus", "DEF-BONUS"),
    "replay.sees": ("replay", "sees", "C20"),
    "replay.push_target": ("replay", "push_target", "PUSH-DIRECTION"),
    "replay.enter": ("replay", "enter", "BOAT-IDS"),
    "replay.stomp": ("replay", "stomp", "STOMP"),
    "replay.mooni_freeze": ("replay", "mooni_freeze", "MOONI-FREEZE"),
    "economy.tech_cost": ("economy", "tech_cost", "TECH-COST"),
    "economy.meet_stars": ("economy", "meet_stars", "ECON-MEET"),
    "economy.Books.income": ("economy", "income", "ECON-INCOME"),
    "economy.Books.income.siege": ("economy", "income", "ECON-SIEGE"),
}
UNTESTED = {   # rules the engine applies that no save has exercised yet (they change no replay score either way)
    "economy.EMBASSY_STEP",   # no tribe built a second embassy in any save
    # market_income and clathrus_income left this set 2026-10-26: Jason's games 1-5 test both (ECON-MARKET-CLATHRUS)
}

def discover():
    """rule name -> 'file:line' for every rule-like name in the engine source."""
    out = {}
    for key, rel in FILES.items():
        lines = open(os.path.join(ROOT, rel)).read().split("\n")
        block = None
        for n, ln in enumerate(lines, 1):
            m = re.match(r"^((?:[A-Z][A-Z0-9_]*\s*,\s*)*[A-Z][A-Z0-9_]*)\s*=", ln)
            if m:
                for name in re.split(r"\s*,\s*", m.group(1)):
                    if name not in SKIP: out.setdefault(f"{key}.{name}", f"{rel}:{n}")
                block = m.group(1) if m.group(1) in ("RULES", "ECON_RULES") and re.search(r"=\s*\{", ln) else None
                continue
            if block:
                if ln.startswith("}"): block = None; continue
                k = re.match(r"\s*'([a-z0-9_]+)'\s*:", ln)
                if k: out.setdefault(f"{key}.{block}.{k.group(1)}", f"{rel}:{n}")
            for g in re.findall(r'RULES\.get\("([a-z0-9_]+)"', ln): out.setdefault(f"{key}.RULES.{g}", f"{rel}:{n}")
            if key == "replay":
                a = re.match(r"\s*(?:el)?if t == (\d+)\b", ln)
                if a: out.setdefault(f"replay.action.{a.group(1)}", f"{rel}:{n}")
    for name, (key, fn, _) in FUNCS.items():
        rel = FILES[key]
        for n, ln in enumerate(open(os.path.join(ROOT, rel)).read().split("\n"), 1):
            if re.match(rf"\s*def {fn}\(", ln): out[name] = f"{rel}:{n}"; break
    return out

def level_rank(lv):
    m = re.match(r"L(\d)", lv or ""); return int(m.group(1)) if m else -1   # 'tool', 'decision', 'data' -> -1

def build():
    ledger = {r["id"]: r for r in json.load(open(os.path.join(ROOT, "verify", "ledger.json")))["rules"]}
    found = discover(); ids = dict(MAP, **{k: v[2] for k, v in FUNCS.items()})
    rows, errors = {}, []
    for name, where in sorted(found.items()):
        lid = ids.get(name)
        if lid is None: errors.append(f"{name} ({where}) has no ledger id: add it to MAP in tools/rule_levels.py"); continue
        r = ledger.get(lid)
        if r is None: errors.append(f"{name} ({where}) -> {lid}: not in verify/ledger.json (tools/ledger.py add ...)"); continue
        lv = r["level"]; tool = lv.startswith("tool")
        rows[name] = {"ledger": lid, "level": lv, "source": where,
                      "unverified": (not tool and level_rank(lv) < 1) or name in UNTESTED}
    stale = sorted(set(ids) - set(found))
    return rows, errors, stale

if __name__ == "__main__":
    rows, errors, stale = build()
    for s in stale: print("note: mapped but not found in the engine (renamed or removed?):", s)
    if "--check" in sys.argv:
        for e in errors: print("FAIL:", e)
        try: old = json.load(open(os.path.join(ROOT, "data", "rule_levels.json")))["rules"]
        except (OSError, ValueError, KeyError): old = None
        if old != rows: print("note: data/rule_levels.json is out of date: re-run python3 -I tools/rule_levels.py and commit it")
        print(f"rule labels: {len(rows)} engine rules labelled, {sum(r['unverified'] for r in rows.values())} unverified, {len(errors)} missing")
        sys.exit(1 if errors else 0)
    for e in errors: print("missing:", e)
    json.dump({"_about": "Generated by tools/rule_levels.py: every rule the engine applies -> ledger id, level, source line. "
               "unverified = below L1 or not yet tested by any save; simulations should flag moves that depend on these.",
               "rules": rows}, open(os.path.join(ROOT, "data", "rule_levels.json"), "w"), indent=1, ensure_ascii=False)
    print(f"wrote data/rule_levels.json: {len(rows)} rules, {sum(r['unverified'] for r in rows.values())} unverified, {len(errors)} missing")
