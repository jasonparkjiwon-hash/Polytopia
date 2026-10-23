#!/usr/bin/env python3
"""Builds the Polytopia knowledge base (JSON files) from hand-transcribed source facts.

Every fact carries:  src  = where it came from      (see SOURCES)
                     conf = high | med | low         (how much to trust it)
                     cid  = conflict id, if the sources disagree (see conflicts_and_gaps.md)

Run:  python3 build_dataset.py     ->  writes ../data/*.json  (this directory)
Then: python3 validate_dataset.py  ->  cross-checks the data against itself.
"""
import json, os, math

OUT = os.path.dirname(os.path.abspath(__file__))

def dump(name, obj):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
    print("wrote", name)

SOURCES = {
 "PE":  {"name": "PolyEnv engine source (FryOne2137, MIT, C++, Jan-Feb 2026)",
         "kind": "code", "reliability": "med-high",
         "note": "A fan RE-IMPLEMENTATION written against the wiki. Good for exact constants and edge cases, "
                 "but it is not the game's own code: it contains tuned values, stubs and deliberate deviations."},
 "WK":  {"name": "Polytopia fandom wiki (pages: Map Generation, Technology, Combat, Score, Tribes, tribe pages, Ruins, Singleplayer)",
         "kind": "community docs", "reliability": "med",
         "note": "Partly Discord-sourced; individual pages disagree with each other (see C1/C2). Map Generation page "
                 "says domain behaviour verified in v2.0.49 and terrain % enforced since 2.0.58."},
 "SC":  {"name": "Polytopia fandom wiki - Score page (incl. starting-score table)", "kind": "community docs", "reliability": "med-high",
         "note": "Numbers are checkable by arithmetic (see validate_dataset.py), which raises trust."},
 "DEV": {"name": "Polytopia staff (Zoythrus) Steam comment on difficulty, ~2019", "kind": "developer statement", "reliability": "high but old"},
 "DER": {"name": "Derived here by arithmetic from other facts", "kind": "derived", "reliability": "see conf"},
 "GA":  {"name": "GAIGResearch/Tribes (Java, 2019-2021)", "kind": "code", "reliability": "old ruleset",
         "note": "README only retrieved; numeric tables (terrainProbs.json) NOT retrieved. Do not use for current numbers."},
 "OLD": {"name": "pocketgamer 2018 article; community python generator; namu.moe mirror", "kind": "old/low", "reliability": "low",
         "note": "Pre-Moonrise or unverifiable. Used only as tie-breakers, never as primary."},
}

def f(v, src, conf="med", cid=None, note=None):
    d = {"v": v, "src": src, "conf": conf}
    if cid: d["cid"] = cid
    if note: d["note"] = note
    return d

# ============================================================================
# 1. MAP GENERATION
# ============================================================================
MAP_SIZES = {  # name: side
  "tiny": 11, "small": 14, "normal": 16, "large": 18, "huge": 20, "massive": 30}
RUINS = {121: 4, 196: 5, 256: 7, 324: 9, 400: 11, 900: 23}

map_generation = {
 "_about": "Everything needed to simulate/estimate a freshly generated map. Square grid, Chebyshev distance, "
           "coordinates (x,y), index = y*size+x. Tile counts are size*size.",
 "map_sizes": f(MAP_SIZES, "WK", "high", note="Perfection=normal 16x16; Domination: 1 opp tiny, 2 small, 3 normal, 4+ large. Tiny supports <=9 players, others <=16."),
 "map_types": {
   "implemented_in_PE": ["lakes", "drylands", "waterworld"],
   "named_in_WK": ["drylands", "lakes", "continents", "pangea", "archipelago", "water_world"],
   "note": "PE implements only 3 of the 6 wiki types; continents/pangea/archipelago pipelines are UNKNOWN (gap G1)."},
 "capital_placement": {
   "sector_grid": f("ceil(sqrt(players)) per side  ->  1-4 players: 2x2 (4 domains), 5-9: 3x3 (9), 10-16: 4x4 (16)", "PE+WK", "high",
                    note="PE formula and wiki table agree exactly."),
   "sector_assignment": f("players are assigned to a uniformly random permutation of the sector cells (extra sectors stay empty)", "PE", "med"),
   "base_span": f("size // grid ; leftover = size - base_span*grid is distributed as origin offsets: "
                  "origin(c)=c*base_span + min(leftover, max(1, min(leftover,c)-1))", "PE", "med", note="Wiki: 11x11 -> 5x5 domains, 14x14 -> 7x7 (both agree)"),
   "eligible_cells": f("inner margin = 2 if base_span>4 else 1; x,y in [max(2,origin+margin), min(size-2, origin+span-margin)) ; "
                       "wiki: capitals never within 2 tiles of a domain border", "PE+WK", "med"),
   "cell_weight": f("weight = max over ALL sector centres of max(1, base_span//2 - chebyshev(cell, centre))^3  (cubic pull towards a sector centre)", "PE", "med",
                    note="Wiki only says 'random within domain'. Cubic weighting is PE's reading of the reference generator."),
   "capital_guarantees": f("capital tile = City + Road. The 4 orthogonal neighbours of every capital are forced to Land.", "PE", "med"),
 },
 "villages": {
   "spacing": f("a village/suburb must be >2 (Chebyshev) from every city/village/capital, i.e. >=3 apart; never on map edge; "
                "<=1 per 3x3 area", "PE+WK", "high"),
   "suburbs": f({"per_capital_min": 1, "per_capital_max": 2, "radius": 4, "map_types": ["lakes (PE) ; wiki: all except drylands & water world"]},
                "PE+WK", "med", note="Suburbs are villages placed close to a capital: PE draws candidates in the 9x9 square around it. Wiki says 'all map types except Drylands and Water World' (so also continents etc.)"),
   "grid_slots": f("(size // 3)^2  (integer division first)", "PE", "med"),
   "pre_terrain_count": f("floor((grid_slots - capitals - suburbs) * density) ; density lakes=0.30, waterworld=0.10, drylands=0.0", "PE+WK", "high",
                          note="Wiki: ~30% of theoretical max placed before terrain (10% water world, 0% drylands)."),
   "post_terrain_target": f("PE: tries grid_slots - capitals - pre_terrain villages, placing on LAND cells with x,y in [2,size-3] and >2 from every city; stops when no candidate. "
                            "WIKI: 'about 60% after terrain' (80% drylands).", "PE vs WK", "low", cid="C9",
                            note="Real post-terrain village count is therefore uncertain. Empirically count villages in real games to fix this."),
 },
 "terrain": {
   "lakes": {
     "land_locked": "capitals, suburbs, pre-terrain villages and the 4 neighbours of each capital are forced land",
     "field": "uniform random noise, locked-land cells = 1.0, outside the map counts as 1.0 (dry edges), 2 passes of 3x3 mean smoothing",
     "water_fraction": f("water tiles = randint(ceil(0.25*N), floor(0.28*N)) lowest-field unlocked cells", "PE", "low",
                         note="0.25/0.28 are PE's tuned constants ('kLakesMinWaterFraction' etc.), not wiki facts."),
   },
   "waterworld": {"water_fraction": f(0.85, "PE", "low"), "smoothing_passes": 2, "outside_noise_value": 0.5,
                  "note": "Corners are NOT forced to land in water world (PE)."},
   "drylands": {"water": "none, except 2 fish water tiles beside Kickoo/Aquarion capitals", "src": "PE+WK", "conf": "high"},
   "shallow_vs_ocean": f("a water tile edge-adjacent (4-neighbour) to land/forest/mountain is 'shallow Water'; every other water tile is deep 'Ocean'. Diagonal-only contact = ocean.", "PE+WK", "high"),
   "corners": f("In non-waterworld maps the four corner tiles are forced Land with no resource/settlement; they are the 4 LIGHTHOUSE tiles.", "PE", "med"),
 },
 "biome_assignment": {
   "method": f("each capital claims land by alternating 4-directional border growth in a freshly shuffled player order each round; each claim picks a uniformly random tile among the claimant's whole current frontier. "
               "Disconnected land goes to the nearest capital by Chebyshev distance.", "PE", "med",
               note="Wiki: 'neighbouring tribes can influence capital terrain on 121-tile maps'."),
   "base_shares": f({"mountain": 0.14, "forest": 0.38, "field": 0.48}, "WK+PE", "high", note="Enforced as exact shares since update 2.0.58 per wiki (PE draws i.i.d., so counts are only approximate)."),
   "modifier_rule": f("mountain = 0.14*mod_m ; forest_before = 0.38 + (0.14-mountain)*(0.38/0.86) ; forest = min(forest_before*mod_f, 1-mountain) ; field = remainder", "PE+WK", "high",
                      note="Wiki: mountains applied first (affect forest+field), forest next (affects only field)."),
   "settlement_tiles_keep_land": True,
 },
 "resources": {
   "area": f("resources appear only within Chebyshev distance 2 of ANY city/village/capital; 'inner' = distance 1 (the 8 tiles around it)", "PE+WK", "high"),
   "rates": {
     "inner": {"fruit_on_field": 0.18, "crop_on_field": 0.18, "empty_field": 0.12, "animal_in_forest": 0.19, "empty_forest": 0.19, "metal_in_mountain": 0.11, "empty_mountain": 0.03},
     "outer": {"fruit_on_field": 0.06, "crop_on_field": 0.06, "empty_field": 0.36, "animal_in_forest": 0.06, "empty_forest": 0.32, "metal_in_mountain": 0.03, "empty_mountain": 0.11},
     "src": "WK+PE", "conf": "med", "cid": "C23",
     "note": "NUMBERS agree between wiki and PE, INTERPRETATION does not. PE reads them as P(resource | terrain), e.g. P(fruit|field,inner)=0.18. The wiki rows sum to the terrain total (18+18+12=48), i.e. they are shares of ALL tiles, which implies P(fruit|field,inner)=0.375. Expected resources in the 8-tile inner ring: PE ~2.1, wiki reading ~5.3. Settle with C23 test before trusting either. Multiply by tribe modifiers (fruit, crops, animals, metal)."},
   "fish": {"shallow": f("0.50 * tribe_fish_mod, only inside the resource area", "WK+PE", "high"),
            "ocean": f("0.10 * tribe_fish_mod inside the resource area", "PE", "low", note="PE: 'public docs do not define a numeric ocean rate' - 0.10 is a tuned guess. Wiki says fish can appear in ocean inside borders."),
            "water_tile_tribe": "water has no tribe; PE uses the nearest generated land biome's tribe for the fish modifier"},
   "excluded": "corner tiles and tiles that hold a settlement get no resource",
   "visibility_gates": f({"crop": "Organization (or Farming)", "metal": "Climbing", "starfish": "Fishing (WK) | Sailing (PE docs)"}, "WK", "med", cid="C8"),
   "capital_guarantee": {
     "PE_implements": {"Bardur": "2 animals in forest within ring 1", "Imperius": "2 fruit on land", "Kickoo": "2 fish on shallow water", "Zebasi": "1 crop"},
     "WK_says": "EVERY capital has >=2 identical resources within its ring: Xin-xi 2 metal, Oumaji 2 fruit, Hoodrick 2 animals; Bardur/Imperius/Kickoo/Zebasi/Elyrion/Cymanti tied to their start tech; all others 2 of a random tier-1 resource (fish, animal or fruit). Missing ones are force-spawned by replacing tiles.",
     "cid": "C10", "conf": "med",
     "use_for_fog": "STRONG PRIOR: the 3x3 ring around an unseen enemy capital contains >=2 of the same resource; for most tribes the type is known."},
 },
 "tribe_modifiers": {   # multipliers on the base rates above
   "_note": "Missing key = 1.0. fish/animals/fruit/crops/metal multiply the resource rates; forest/mountain feed biome_assignment.modifier_rule.",
   "Kickoo":   f({"fish": 1.5, "mountain": 0.5}, "PE+WK", "high", note="WK also lists 2.0x water, but water mods are NOT applied by the game (WK)."),
   "Aquarion": f({"forest": 0.5}, "PE+WK", "high", note="WK: 1.5x water exists in code but has no effect."),
   "Bardur":   f({"forest": 0.8, "crops": 0.0}, "PE", "low", cid="C11", note="WK instead says '1.5x fruit, 0x crop'. Unresolved."),
   "XinXi":    f({"mountain": 1.5, "metal": 1.5}, "PE+WK", "high"),
   "AiMo":     f({"mountain": 1.5, "crops": 0.1}, "PE+WK", "high"),
   "Oumaji":   f({"forest": 0.2, "mountain": 0.5, "animals": 0.2}, "PE+WK", "high", note="WK also 0.5x water (not applied)."),
   "Vengir":   f({"metal": 2.0, "animals": 0.1, "fruit": 0.1, "fish": 0.1}, "PE+WK", "high"),
   "Imperius": f({"fruit": 2.0, "animals": 0.5}, "PE+WK", "high"),
   "Hoodrick": f({"forest": 1.5, "mountain": 0.5}, "PE+WK", "high"),
   "Zebasi":   f({"forest": 0.5, "mountain": 0.5, "fruit": 0.5}, "PE+WK", "high"),
   "Quetzali": f({"fruit": 2.0, "crops": 0.1}, "PE+WK", "high"),
   "Yadakk":   f({"forest": 0.5, "mountain": 0.5, "fruit": 1.5}, "PE+WK", "high"),
   "Luxidoor": f({}, "PE+WK", "med", note="WK table: base rate. (Luxidoor page: '++fruit, -game' - unquantified, ignored.)"),
   "Elyrion":  f({"mountain": 0.5, "crops": 1.5}, "WK", "low", note="PE has NO modifiers for Elyrion."),
   "Polaris":  f({}, "WK", "low", note="WK: no own rates; land converts to Polaris terrain; mirror/mixed uses Imperius land."),
   "Cymanti":  f({"mountain": 1.2, "crops": 0.0, "spores": "replaces crops (rate unknown)"}, "WK", "low", note="PE has no modifiers for Cymanti."),
 },
 "ruins": {
   "count_by_tiles": f(RUINS, "PE", "med", note="Formula for other sizes: round(tiles*23/900). Wiki page gave no counts."),
   "placement": f("random non-corner tile with no settlement; PE requires no settlement within Chebyshev 2", "PE", "med"),
   "wiki_rule": "WK: cannot spawn on shallow water, nor next to a village, city or another ruin.",
 },
 "starfish": {"count": f("floor(water_tiles / 25)", "PE", "med"), "placement": "non-corner water tile with no resource and no settlement in its 3x3",
              "reward_stars": f(8, "PE", "med", note="collected when a unit enters the tile"),
              "wiki_flag": "WK marks 'no adjacent starfish' as possibly incorrect"},
 "known_version_notes": [
   "2.0.58 (Balance Pass 2): terrain percentages followed as exactly as possible.",
   "Water rules pre-date Path of the Ocean update and may be outdated (WK).",
   "Kickoo/Aquarion 'continents' 40%/30% water replacement is bugged and does nothing (WK)."],
}

# ============================================================================
# 2. TECH TREE
# ============================================================================
TECHS = [  # name, tier, prerequisite, unlocks (base tribes)
 ("Climbing",1,None,"Mountain movement + mountain defence bonus (x1.5); reveals metal"),
 ("Fishing",1,None,"Fishing action, Port, Raft (embark), water movement; reveals starfish (WK)"),
 ("Hunting",1,None,"Hunt animals action"),
 ("Organization",1,None,"Harvest fruit action; reveals crops"),
 ("Riding",1,None,"Rider"),
 ("Archery",2,"Hunting","Archer; forest defence bonus (x1.5)"),
 ("Ramming",2,"Fishing","Rammer (boat upgrade)"),
 ("Farming",2,"Organization","Farm"),
 ("Forestry",2,"Hunting","Lumber Hut; Clear Forest"),
 ("Free Spirit",2,"Riding","Temple; Disband"),
 ("Meditation",2,"Climbing","Mountain Temple; Pacifist task (Altar of Peace)"),
 ("Mining",2,"Climbing","Mine"),
 ("Roads",2,"Riding","Roads + Bridges; Network task"),
 ("Sailing",2,"Fishing","Scout (boat); ocean movement"),
 ("Strategy",2,"Organization","Defender; Peace Treaty"),
 ("Aquatism",3,"Ramming","Water Temple; defence bonus on water/ocean (x1.5)"),
 ("Chivalry",3,"Free Spirit","Knight; Destroy"),
 ("Construction",3,"Farming","Windmill; Burn Forest"),
 ("Diplomacy",3,"Strategy","Cloak, Embassy, Capital Vision"),
 ("Mathematics",3,"Forestry","Catapult; Sawmill"),
 ("Navigation",3,"Sailing","Bomber (boat); Starfish Harvesting"),
 ("Philosophy",3,"Meditation","Mind Bender; Literacy (-33% tech cost); Genius task"),
 ("Smithery",3,"Mining","Swordsman; Forge"),
 ("Spiritualism",3,"Archery","Forest Temple; Grow Forest"),
 ("Trade",3,"Roads","Market; Wealth task; (with 100 stars) Emperor's Tomb"),
]
tech_tree = {
 "_about": "25 base techs. Prerequisites verified from PE TechDB and consistent with the wiki branch structure. "
           "A tier-2/3 tech needs ITS ONE prerequisite (not all lower tiers).",
 "research_rule_2025": f("A tech is researchable if you own its prerequisite OR any tech it leads to ('backwards' research, e.g. Vengir Smithery -> Mining without Climbing).",
                         "2025 balance pass dev post", "medium-high",
                         note="PE may not implement this; matters for Vengir (Smithery) and Ai-Mo (Philosophy) starts. C25."),
 "cost_formula": f("tier * number_of_cities_owned + 4 ; with Literacy: ceil(base * 2/3)", "PE+WK", "high",
                   note="Wiki worked example (1 city): 5/6/7, with Literacy 4/4/5."),
 "literacy_source": f("Philosophy tech", "PE+WK", "high"),
 "ruin_tech_rule": "ruin 'Technology' reward picks uniformly among techs whose prerequisite you own (PE) ",
 "techs": {n: {"tier": t, "prerequisite": p, "unlocks": u, "src": "PE+WK", "conf": "high" if t==1 else "high"} for n, t, p, u in TECHS},
 "removed_from_game": ["Whaling (T2)", "Engineering (T3, Guard Tower)"],
 "special_tribe_trees": {
   "_note": "Special tribes REPLACE some techs. PE implements only the 25 base techs for every tribe, so these are NOT simulable with PE data.",
   "Aquarion": {"Fishing": "starfish sight + ocean movement", "Ramming": "->Aquaculture (Aqua Farm)", "Sailing": "->Marine Life (Shark)", "Navigation": "Jelly, Starfish Harvesting",
                "Riding": "Amphibian, water movement", "Roads": "->Waterways (Atoll, Flood)", "Chivalry": "->Spearing (Tridention, Destroy)", "Mathematics": "Puffer, Sawmill", "Free Spirit": "->Free Diving"},
   "Elyrion": {"Hunting": "->Forest Magic (Enchant Animal -> Polytaur)", "Forestry": "Sanctuary, Lumber Hut"},
   "Polaris": {"Fishing": "->Frostwork (Outpost, Mooni)", "Archery": "Ice Archer", "Ramming": "->Ice Fishing", "Sailing": "->Sledding (Battle Sled)", "Aquatism": "->Polarism (Ice Temple, Glide)",
               "Navigation": "->Polar Warfare (Ice Fortress)", "Trade": "Ice Bank, Wealth"},
   "Cymanti": {"Farming": "Fungi", "Archery": "Phychi", "Ramming": "->Hydrology (Algae)", "Sailing": "->Pescetism (Raychi)", "Strategy": "Kiton", "Riding": "Hexapod", "Roads": "Mycelium, Network",
               "Chivalry": "->Shock Tactics (Doomux)", "Construction": "->Recycling (Decompose)", "Mathematics": "Exida, Sawmill", "Philosophy": "Shaman, Literacy, Genius", "Trade": "Clathrus, Wealth",
               "Organization": "does NOT reveal crops", "Fishing": "no Ports or Rafts"},
   "src": "WK (Technology page)", "conf": "med"},
 "tribe_start_tech": "see tribes.json",
}

# ============================================================================
# 3. TRIBES
# ============================================================================
# start stars: only PE has them (unverified).  start score: three versions.
TRIBES = {
 #            id  kind      PE_stars PE_tech        PE_unit      PE_score  WK_score(SC)   wiki_tech
 "XinXi":    (1, "regular", 7, "Climbing",     "Warrior",   515, 515, "Climbing"),
 "Imperius": (2, "regular", 5, "Organization", "Warrior",   515, 515, "Organization"),
 "Bardur":   (3, "regular", 5, "Hunting",      "Warrior",   515, 515, "Hunting"),
 "Oumaji":   (4, "regular", 6, "Riding",       "Rider",     520, 520, "Riding"),
 "Kickoo":   (5, "regular", 5, "Fishing",      "Warrior",   515, 615, "Fishing"),
 "Hoodrick": (6, "regular", 7, "Archery",      "Archer",    620, 620, "Archery"),
 "Luxidoor": (7, "regular", 2, None,           "Warrior",   515, 465, None),
 "Vengir":   (8, "regular", 5, "Smithery",     "Swordsman", 730, 730, "Smithery"),
 "Zebasi":   (9, "regular", 5, "Farming",      "Warrior",   615, 615, "Farming"),
 "AiMo":     (10,"regular", 5, "Philosophy",   "MindBender",615, 615, "Meditation (Ai-Mo/Tribes pages, 2018 article) | Philosophy (Technology page)"),
 "Quetzali": (11,"regular", 7, "Strategy",     "Defender",  620, 620, "Strategy"),
 "Yadakk":   (12,"regular", 7, "Roads",        "Warrior",   615, 615, "Roads"),
 "Aquarion": (13,"special", 5, None,           "Mermaid",   415, None, None),
 "Elyrion":  (14,"special", 5, None,           "Warrior",   515, 515, "Forest Magic (replaces Hunting)"),
 "Polaris":  (15,"special", 5, None,           "Mooni",     630, 530, "Frostwork (replaces Fishing)"),
 "Cymanti":  (16,"special", 5, None,           "Shaman",    515, 630, "Farming"),
}
TRIBE_CONFLICT = {"AiMo": "C1", "Luxidoor": "C2", "Polaris": "C3", "Cymanti": "C4", "Kickoo": "C5"}
tribes = {
 "_about": "Per-tribe start state + terrain modifiers (map_generation.json holds the modifier numbers). "
           "'resolved' is MY best current belief given all evidence; 'PE'/'WK' are what each source says.",
 "tribes": {},
 "start_score_decomposition": {
   "formula": "city 100 + 50/level above 1 + 20/territory tile + 5/explored tile + 5*unit_cost + 100*tier(each tech)",
   "constants": "start: level-1 capital (100), territory 3x3 = 9 tiles (180), 5x5 = 25 explored tiles (125) -> 405 before unit/tech/level",
   "verified_by": "validate_dataset.py reproduces 14 of the 15 wiki start scores exactly from components (all except Kickoo, C5); the PE start packages for Ai-Mo/Luxidoor/Kickoo do not (C1,C2,C5).",
   "corner_rule": "SC: a capital whose 5x5 reveal contains a corner starts 5 points lower (corner tile not revealed).",
   "implication": "The REAL initial reveal around a capital is 5x5 (25 tiles). PE reveals only the 3x3 territory + unit radius 1 (C21).",
 },
 "start_conditions_common": {
   "units": f("exactly one unit in the capital", "WK", "high"),
   "capital_level": f(1, "SC(DER)", "med", note="except Luxidoor (see C2)"),
   "capital_income": f("level + 1 (capital bonus) -> 2 stars/turn at level 1", "PE+DEV", "high", note="DEV: bot baseline +2 stars/turn from capital"),
 },
}
for name, (tid, kind, stars, pe_tech, pe_unit, pe_score, wk_score, wk_tech) in TRIBES.items():
    tribes["tribes"][name] = {
        "id": tid, "kind": kind,
        "start_stars": f(stars, "PE+NM", "med-high", note="PE and NamuWiki agree for all 16 (XinXi/Hoodrick/Quetzali/Yadakk 7, Oumaji 6, Luxidoor 2 [Nov 2025], rest 5). Yadakk 5->7 in June 2025."),
        "start_tech_PE": pe_tech, "start_tech_WK": wk_tech, "start_unit_PE": pe_unit,
        "start_score_PE": pe_score, "start_score_WK": wk_score,
        "conflict": TRIBE_CONFLICT.get(name),
    }
tribes["resolved"] = {
 "_note": "Best current belief; confidence reflects agreement between sources AND the arithmetic score check.",
 "AiMo":     f({"start_tech": "Philosophy", "start_unit": "MindBender", "start_score": 730}, "NM+PE", "med-high", cid="C1",
               note="NamuWiki: 2025 patch changed Ai-Mo from Meditation to Philosophy + Hypnotist(Mind Bender), -33% tech cost. Fandom Ai-Mo/Tribes pages and the 615 score are pre-patch. 730 = 405+25+300 by formula; PE's own commented table also says 730."),
 "Luxidoor": f({"start_tech": None, "start_unit": "Warrior", "capital_level": 3, "start_stars": 2, "start_score": 515}, "NM+PE", "med-high", cid="C2",
               note="NamuWiki: Apr 2021 capital cut to level 2; Nov 2025 patch cut stars to 2 and RESTORED level 3. Fandom score 465 (level 2) is pre-Nov-2025. Level 3 = 515 by formula = PE. Wall: unconfirmed. Namu guaranteed-near-capital list: 2 fruit, 2 animal, 1 crop, 2 fish, 1 iron (8 tiles)."),
 "Polaris":  f({"start_tech": "Frostwork", "start_unit": "Mooni", "start_score": 530}, "SC(DER)", "low-med", cid="C3", note="530 = 405+25(Mooni cost 5)+100(T1) by formula. Wiki Score page may be pre-2025; PE says 630. Unresolved - version drift possible."),
 "Cymanti":  f({"start_tech": "Farming", "start_unit": "Shaman", "start_score": 630}, "SC(DER)+WK+NM", "med", cid="C4", note="630 = 405+25(Shaman)+200(T2 Farming). NamuWiki also lists Farming (mushroom farming) and Shaman/Warrior ambiguity; PE has Shaman but no start tech."),
 "Kickoo":   f({"start_tech": "Fishing", "start_score": 515}, "PE+NM", "low-med", cid="C5", note="Fishing+Warrior = 515 by formula and NamuWiki lists nothing else. The fandom score 615 is unexplained and possibly from an older version. Lean 515."),
}
tribes["special_tribe_mechanics"] = {
 "Aquarion": ["no start tech; starts with Mermaid (amphibious)", "all units can move on water; land slow unless flooded", "can build on water & place monuments on ocean", "unique: Aqua Farm, Atoll, Flood/Fill, Tridention, Shark, Puffer, Jelly, Crab(super)"],
 "Elyrion":  ["start tech Forest Magic; Enchant Animal -> Polytaur; Sanctuary", "'at least 2 animals' guaranteed near capital (Strategies page)"],
 "Polaris":  ["terraforming instead of boats; captured territory turns to Polaris terrain and water freezes", "Gaami super unit freezes tiles", "Ice Bank (income, max level raised 8->10 in 2019 nerf), Outpost gives 1 pop (was 2)"],
 "Cymanti":  ["spores replace crops; >=2 spores guaranteed at start", "Shaman boost: +0.5 attack, +1 move until it acts (WK Combat)", "8 unique units, 6 unique skills, 4 unique buildings", "no Ports/Rafts; Organization doesn't reveal crops"],
 "src": "WK", "conf": "low-med (summaries only; PE has unit stats but not these mechanics)",
}

# ============================================================================
# 4. FOG / VISION
# ============================================================================
fog_vision = {
 "_about": "How reveal works (PE VisionSystem/MovementSystem/CitySystem) plus what that means for inference. "
           "WK Fog-of-War page was unreachable (client error) so these rules are PE-only unless marked.",
 "geometry": f("square (Chebyshev) disk of radius r around the unit: all tiles with max(|dx|,|dy|)<=r", "PE", "med"),
 "unit_vision": f("r = unit.visionRange (1 for most; 2 for Scout skill units: Cloak, Scuba, Scout boat, BabyDragon, FireDragon, IceFortress, Dinghy... ) ; a unit standing on a MOUNTAIN gets max(r,2)", "PE+WK", "high",
                  note="WK Combat page: 'Mountains give a two-tile sight radius; Scout units see two tiles in every direction.'"),
 "persistence": f("reveal is permanent for the game (a per-player bit is set and never cleared).", "PE", "low",
                  note="PE only ADDS visibility. Whether the real game shows STALE or LIVE info for previously-seen-but-out-of-vision tiles is UNKNOWN (G3) - matters a lot for belief tracking."),
 "movement_reveal": f("reveals along the whole traversed path (using the best vision seen during the move), plus final tile; mountain destination -> radius 2", "PE", "med"),
 "must_end_on_visible_tile": f("a unit may only END its move on a tile that is revealed to its player", "PE", "med"),
 "initial_reveal": {
   "real_game_5x5": f("start score arithmetic needs 25 explored tiles (5x5 around capital); SC: capital near a corner scores 5 less because the corner tile isn't revealed", "DER+SC", "med", cid="C21"),
   "PE": "territory radius-1 (3x3) tiles revealed + the start unit's radius-1 vision; corners are skipped on Initial reveal",
 },
 "explorer": {
   "source": "Level-2 city reward 'Explorer' (Luxidoor can't take it in capital) and ruin reward",
   "algorithm": f("15 steps. Each step: BFS (8-neighbour) dist<=4 over tiles the owner may enter (mountain needs Climbing, shallow water Sailing, ocean Navigation); "
                  "score tile = 183 - 10*fog_tiles_cleared (plus-shape of 5 tiles, capped at 4) minus 33 if it clears a lighthouse; propagate +100 per BFS layer (3 layers); "
                  "step to the best adjacent tile, -tie random, +5 penalty for stepping straight back; reveal a plus (centre+4 orthogonal) at every step", "PE", "med",
                  note="A mirror site says 'up to 20 moves' (OLD, low). PE's 15 and wiki-derived scoring constants agree with each other."),
   "tie_break_rng": "seeded from turn, player, start position",
   "reveals_ruin_area": "ruin 'Explorer' reward only offered if some tile of the 5x5 around the ruin is still hidden",
 },
 "lighthouses": {
   "positions": "the four map corners", "reward": f("first time a player reveals a corner: +1 population in capital (else best city)", "PE", "med"),
   "monument": "Eye of God after discovering all 4",
   "fog_use": "Corner tiles are KNOWN: land, no resource, no settlement (non-waterworld). Don't spend belief mass there.",
 },
 "tech_gated_visibility": f({"crop": "Organization|Farming", "metal": "Climbing", "starfish": "Fishing (WK) / Sailing (PE docs)"}, "WK", "med", cid="C8",
                            note="Before the tech, those resources are not displayed. So 'no crop seen' without Organization carries NO information."),
 "enemy_visibility": {
   "units_cities": "visible only while inside current vision (playerIsCurrentlyVisibleTo checks live tiles)",
   "hide_skill": "Cloak/Dinghy/Scuba with Hide are invisible to others AFTER they have moved this turn (lastMoveDir != 0); then not targetable and don't project ZoC",
   "retaliation_blind": f("defender cannot retaliate if it cannot see the attacker (WK). PE ignores this.", "WK", "low", cid="C20"),
 },
 "meeting_reward": f("first time you SEE any unit/city of tribe X: +stars = min(11, 1 + 2*ceil(score_of_X/1000))", "PE", "low", cid="C18",
                     note="resolved at start of your turn and at end of an opponent's turn from live vision; non-Initial reveals trigger it immediately. Real values not verified."),
 "player_visibility_state": "PE stores a 16-bit mask per tile (bit i = player i has seen it).",
 "inference_hooks": [
   "unseen tile ∈ {prior from map_generation} conditioned on: distance to nearest known settlement, tribe of nearest capital, shallow/deep water, tech gates",
   "every known city/village excludes all unseen cells within Chebyshev<=2 for NEW villages (spacing >=3)",
   "capital ring has >=2 identical resources (C10) -> sharp posterior for rival capital surroundings",
   "map edge tiles never hold villages; corners are lighthouses",
   "number of villages is bounded by (size//3)^2 - capitals, giving a total budget to allocate over unseen area"],
}

# ============================================================================
# 5. COMBAT
# ============================================================================
combat = {
 "damage": {
   "attackForce": "attack * hp/maxHp",
   "defenseForce": "defense * hp/maxHp * defenseBonus",
   "total": "attackForce + defenseForce",
   "attackResult": "round(attackForce/total * attack * 4.5)   (damage dealt)",
   "defenseResult_WK": "round(defenseForce/total * defense * 4.5)   (bonus INCLUDED)",
   "defenseResult_PE": "round(retaliationForce/(attackForce+retaliationForce) * defense * 4.5) with retaliationForce = defense*hp/maxHp  (bonus EXCLUDED)",
   "cid": "C6", "conf": "med", "src": "WK+PE",
   "rounding": "PE: std::llround = round half away from zero; WK unspecified",
   "note": "Attacker's defense and defender's attack are not used in the main hit. Verified against PE CombatSystem.cpp."},
 "retaliation_rules": {
   "none_if_target_dies": True,
   "only_if_attacker_within_defender_range": f("chebyshev(defender, attacker) <= defender.range", "PE", "med"),
   "blocked_by": ["attacker has Surprise", "defender has Stiff"], "src": "PE"},
 "defence_bonus": {
   "none": 1.0, "terrain": 1.5, "city_fortify": 1.5, "city_wall": 4.0,
   "terrain_rules": "Forest needs Archery; Mountain needs Climbing; shallow Water and Ocean need Aquatism (all x1.5, owner's tech)",
   "city_rules": "only for the city's OWNER and only units with Fortify; wall adds +2.5 (total 4.0); city bonus replaces terrain bonus if larger; invaders in an enemy city get none; Giant has no Fortify",
   "poisoned_PE": "bonus<=1 -> 0.5 ; <=1.5 -> 0.7 ; else 2.0",
   "poisoned_WK": "defence reduced by 30%, bonuses blocked",
   "cid": "C7", "src": "PE+WK", "conf": "med"},
 "healing": {
   "idle_recovery": f("a unit that neither moved nor attacked heals 2 HP, or 4 HP on tiles of its own city territory", "PE+WK", "high"),
   "heal_skill": f("Heal action (Mind Bender, Siren): +4 HP to every adjacent friendly; consumes the action; no-op if nobody is hurt", "PE+WK", "high"),
   "poison_halves_healing_WK": "WK only; not seen in PE heal()"},
 "veteran": f("3 kills -> veteran: +5 max HP and full heal; not for StaticSkill units (Giants, boats, special units)", "PE", "high", note="Also granted by ruin 'veteran unit' reward; Warrior vet = 15 HP."),
 "attack_flow": {
   "after_moving": "only units with Dash may attack after moving; Escape lets a unit move after attacking; Persist lets it attack again after a kill",
   "advance_on_kill": "melee (range 1) and Rammer step into the killed unit's tile if legal",
   "splash": "Splash: half the main damage (floor) to every enemy adjacent to the target",
   "stomp": "Stomp units hit all adjacent enemies for floor(mainHit/2) per step moved, no retaliation",
   "convert": "Convert replaces damage: target changes owner, keeps HP/vet, can't act next turn; Bunny/Bunta unconvertible; counts as an attack",
   "infiltrate": "Cloak/Dinghy/Scuba adjacent to enemy city: steals that city's next income, deals base-attack damage to unit inside, spawns Daggers/Pirates = city level (cap 5); infiltrator is consumed",
   "src": "PE", "conf": "med"},
 "zone_of_control": f("entering a tile adjacent (8-neighbour) to a visible enemy unit forces a stop; Creep ignores ZoC; Hide units don't project it", "PE", "med"),
 "movement": {
   "grid": "8-neighbour square grid", "base_cost": "1 move point", "road_cost": "0.5 when both tiles are road/bridge/city/village AND neither is enemy territory",
   "terminal_tiles": "Mountain and Forest (without road) end the move (Creep exempt)",
   "tech_gates": "mountain: Climbing ; land->water via owned Port: Fishing ; Bridge on water: none ; ocean: Sailing (PE movement) vs Navigation (PE Explorer)",
   "embark": "land unit stepping onto an OWN Port becomes Raft (Giant -> Juggernaut), keeps HP; disembark onto land restores type; both end the unit's turn",
   "water_units_on_land": "may enter coastal land only, then must stop",
   "cid": "C8", "src": "PE", "conf": "med"},
 "skills_read_from_code": ["Dash","Fortify","Escape","Hide","Creep","Infiltrate","Stiff","Scout","Persist","Surprise","Independent","WaterOnly","Carry","Splash","Stomp","Convert","Heal","Amphibious","StaticSkill"],
 "skills_NOT_yet_read": ["Tentacles","Drench","Grow","Air","Freeze","Skate","AutoFreeze","FreezeArea","Poison","Sneak","DoubleAttack","Swarm","Explode","Algae","AutoFlood"],
}

# ============================================================================
# 6. ECONOMY / CITIES / BUILDINGS / SCORE
# ============================================================================
economy = {
 "stars": {
   "income_per_turn": f("sum over own cities: (level + base + 1 if capital + 1 if workshop + parks + min(0,population)) + market income; besieged city = 0; infiltrated city loses only its normal income once", "PE", "high"),
   "turn_start": "income is applied at the START of your turn (not on turn 0)",
   "siege": "an enemy unit standing on the city centre tile",
 },
 "city": {
   "level_up": f("population >= level+1 ; then population -= level+1 ; level+=1 ; reward choice is mandatory", "PE", "high", note="WK Score page consistent: 50 pts per level."),
   "unit_capacity": f("level + 1 units supported", "PE", "high"),
   "rewards": {"2": ["Workshop (+1 star/turn)", "Explorer"], "3": ["City Wall", "Resources (+5 stars now)"], "4": ["Population Growth (+3 pop)", "Border Growth (claim radius 2)"], "5+": ["Park (+1 star/turn, +250 score)", "Super Unit (Giant)"]},
   "territory": "capital/city claims radius 1 (3x3) on founding; Border Growth claims free tiles to radius 2",
   "capture": "unit must START the turn on the city tile; consumes the unit's turn; supported units lose their origin city",
   "village_to_city": "unit starting turn on village; consumes turn; becomes level-1 city (pop 0)",
   "src": "PE", "conf": "high"},
 "tile_actions": {
   "hunt": {"cost": 2, "tech": "Hunting", "effect": "+1 pop, removes animal"},
   "harvest_fruit": {"cost": 2, "tech": "Organization", "effect": "+1 pop, removes fruit"},
   "fish": {"cost": 2, "tech": "Fishing", "effect": "+1 pop, removes fish"},
   "clear_forest": {"cost": 0, "tech": "Forestry", "effect": "forest->field, +1 star (PE); wiki Forestry page says +2 stars, undated - C19"},
   "burn_forest": {"cost": 3, "tech": "Construction", "effect": "forest->field with crop", "src": "2025 balance pass dev post (PE had 5, stale)"},
   "grow_forest": {"cost": 5, "tech": "Spiritualism", "effect": "empty field->forest"},
   "road": {"cost": 3, "tech": "Roads", "effect": "road on land/forest, own or neutral territory; wiki Roads page says 2, undated - C19"},
   "bridge": {"cost": 5, "tech": "Roads", "effect": "bridge on shallow water between two land tiles (N-S or E-W)"},
   "destroy": {"cost": 0, "tech": "Chivalry (Construction for bridges)", "effect": "remove building/resource; roads not destroyable"},
   "disband_unit": {"tech": "Free Spirit", "effect": "refund floor(cost/2) stars; Giant/Juggernaut 5"},
   "all actions require own territory (except road: neutral ok)": True,
   "src": "PE", "conf": "med"},
 "buildings": {
   "Farm":      {"cost": 5, "tech": "Farming",      "on": "Field with Crops", "pop": 2},
   "Mine":      {"cost": 5, "tech": "Mining",       "on": "Mountain with Metal", "pop": 2, "note": "PE header comment says 'Mine = 1' but code sets 2 (code trusted)"},
   "LumberHut": {"cost": 3, "tech": "Forestry",     "on": "Forest", "pop": 1},
   "Port":      {"cost": 7, "tech": "Fishing",      "on": "Shallow water", "pop": 1},
   "Forge":     {"cost": 5, "tech": "Smithery",     "on": "Field", "pop": "+2 per adjacent own Mine", "limit": "1 per city"},
   "Sawmill":   {"cost": 5, "tech": "Mathematics",  "on": "Field", "pop": "+1 per adjacent own Lumber Hut", "limit": "1 per city"},
   "Windmill":  {"cost": 5, "tech": "Construction", "on": "Field", "pop": "+1 per adjacent own Farm", "limit": "1 per city"},
   "Market":    {"cost": 5, "tech": "Trade",        "on": "Field adjacent to own Forge/Sawmill/Windmill", "income": "stars/turn = sum of adjacent booster levels (cap 8)"},
   "booster_level": "Forge = adjacent own Mines, Sawmill = adjacent Lumber Huts, Windmill = adjacent Farms (0..8)",
   "not_modelled_in_PE": ["Temples (all kinds)", "Outpost", "Embassy", "Ice Bank", "Atoll", "Aqua Farm", "Clathrus", "Sanctuary", "Guard Tower"],
   "src": "PE", "conf": "med-high"},
 "monuments": {
   "AltarOfPeace": "5 consecutive turns with no attack + Meditation",
   "EmperorsTomb": ">=100 stars + Trade",
   "EyeOfGod": "discover all 4 lighthouses",
   "GateOfPower": "10 kills",
   "GrandBazaar": "5 non-capital cities connected to capital",
   "ParkOfFortune": "a city reaches level 5",
   "TowerOfWisdom": "own all techs",
   "build": "cost 0, +3 pop, +400 score, one of each per player", "src": "PE", "conf": "med"},
 "score": {
   "per_explored_tile": 5, "per_territory_tile": 20, "per_unit_cost_star": 5, "per_super_unit": 50,
   "per_tech_tier": 100, "per_park": 250, "per_monument": 400,
   "city": "100 + 50 per level above 1 + 5 per current population",
   "embarked_unit_counts_as_land_unit": True,
   "src": "PE+SC", "conf": "high",
   "pe_caveat": "PE ScoreSystem.startingScore() is stubbed to 0 (commented-out table disagrees with Tribe.cpp). Use tribes.json for starting scores."},
 "ruins": {
   "action": "unit must START its turn on the ruin; uses the unit's turn; ruin disappears",
   "PE_reward_pool": "uniform pick from the AVAILABLE pool: Stars(+10), Tech (random obtainable), Population(+3 to capital, if capital owned), Explorer (if hidden tile in 5x5), VeteranUnit (Swordsman 20HP vet, or Rammer 15HP on water)",
   "WK_reward_names": ["Battleship (Navalon)", "Explorer", "Population Growth", "Stars", "Super Unit", "Technology"],
   "cid": "C14", "conf": "low", "src": "PE vs WK",
   "note": "Real probabilities unknown (G4). PE uses worldSeed+position hash, i.e. NOT the real RNG."},
}

# ============================================================================
# 7. MODES + BOTS
# ============================================================================
modes_bots = {
 "modes": {
   "Perfection": "singleplayer, 30 turns, maximise score; 3-star ~50k (WK)",
   "Domination": "singleplayer, defeat all tribes in as few turns as possible; up to 10 opponents",
   "Glory": "multiplayer; first to 10,000 points and hold the lead one turn",
   "Might": "multiplayer; capture enemy capitals",
   "src": "WK", "conf": "med"},
 "bot_difficulty": {
   "capital_income_per_turn": f({"Easy": 1, "Normal": 2, "Hard": 3, "Crazy": 5}, "DEV+WK", "medium-high", note="TOTAL starting capital income, not a bonus on top: wiki Game Modes says 'Normal 2 (same as humans)'. So Easy bots earn LESS than a human (C24)."),
   "aggression": "higher ratings on higher difficulty (no numbers)",
   "vision_cheating": "NOT stated anywhere found (G5)",
   "implication": "bots win by income handicap, not by planning; their decision policy is undocumented. Needs black-box observation (replay logs)."},
}

# ============================================================================
dump("sources.json", SOURCES)
dump("map_generation.json", map_generation)
dump("tech_tree.json", tech_tree)
dump("tribes.json", tribes)
dump("fog_vision.json", fog_vision)
dump("combat.json", combat)
dump("economy.json", economy)
dump("modes_bots.json", modes_bots)
