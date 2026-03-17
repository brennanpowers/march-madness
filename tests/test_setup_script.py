#!/usr/bin/env python3
"""
Tests for the setup script's core functions.

Tests bracket generation logic without making network calls by using
pre-built test fixtures.

Usage:
    python3 tests/test_setup_script.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from generate_bracket import ROUND_PATTERNS, PLAYER_COLORS
import setup_year as setup_mod

BRACKET_ORDER = setup_mod.BRACKET_ORDER

passed = 0
failed = 0


def check(condition, msg):
    global passed, failed
    if condition:
        passed += 1
        print(f"  \033[32mPASS\033[0m: {msg}")
    else:
        failed += 1
        print(f"  \033[31mFAIL\033[0m: {msg}")


def section(name):
    print(f"\n=== {name} ===")


def make_test_appearances():
    """Build fake all_appearances list simulating a completed tournament."""
    appearances = []
    regions = ["South", "East", "Midwest", "West"]

    for region in regions:
        # Round 1: 8 games, all higher seeds win
        for seed in BRACKET_ORDER:
            opp_idx = BRACKET_ORDER.index(seed)
            if opp_idx % 2 == 0:
                is_winner = True  # top seed in each pair wins
            else:
                is_winner = False
            appearances.append({
                "seed": seed,
                "name": f"{region[0]}{seed}",
                "espnId": f"{region[0].lower()}{seed}",
                "abbrev": f"{region[0]}{seed}",
                "region": region,
                "round": "round1",
                "winner": is_winner,
                "gameDate": "2025-03-20T16:00Z",
            })

        # Round 2: winners are seeds 1, 5, 6, 2 (from bracket order pairs)
        r2_winners = [1, 5, 6, 2]
        r2_losers = [8, 4, 3, 7]
        for seed in r2_winners:
            appearances.append({
                "seed": seed, "name": f"{region[0]}{seed}", "espnId": f"{region[0].lower()}{seed}",
                "abbrev": f"{region[0]}{seed}", "region": region, "round": "round2",
                "winner": True, "gameDate": "2025-03-22T16:00Z",
            })
        for seed in r2_losers:
            appearances.append({
                "seed": seed, "name": f"{region[0]}{seed}", "espnId": f"{region[0].lower()}{seed}",
                "abbrev": f"{region[0]}{seed}", "region": region, "round": "round2",
                "winner": False, "gameDate": "2025-03-22T16:00Z",
            })

        # Sweet 16: 1 and 2 win
        for seed, win in [(1, True), (5, False), (6, False), (2, True)]:
            appearances.append({
                "seed": seed, "name": f"{region[0]}{seed}", "espnId": f"{region[0].lower()}{seed}",
                "abbrev": f"{region[0]}{seed}", "region": region, "round": "sweet16",
                "winner": win, "gameDate": "2025-03-27T16:00Z",
            })

        # Elite 8: 1-seed wins
        for seed, win in [(1, True), (2, False)]:
            appearances.append({
                "seed": seed, "name": f"{region[0]}{seed}", "espnId": f"{region[0].lower()}{seed}",
                "abbrev": f"{region[0]}{seed}", "region": region, "round": "elite8",
                "winner": win, "gameDate": "2025-03-29T16:00Z",
            })

    # Final Four: South 1-seed and Midwest 1-seed win (no region in notes for FF)
    for region, win in [("South", True), ("East", False)]:
        appearances.append({
            "seed": 1, "name": f"{region[0]}1", "espnId": f"{region[0].lower()}1",
            "abbrev": f"{region[0]}1", "region": None, "round": "finalFour",
            "winner": win, "gameDate": "2025-04-05T16:00Z",
        })
    for region, win in [("Midwest", True), ("West", False)]:
        appearances.append({
            "seed": 1, "name": f"{region[0]}1", "espnId": f"{region[0].lower()}1",
            "abbrev": f"{region[0]}1", "region": None, "round": "finalFour",
            "winner": win, "gameDate": "2025-04-05T18:00Z",
        })

    # Championship: South 1-seed wins
    for name, win in [("S1", True), ("M1", False)]:
        appearances.append({
            "seed": 1, "name": name, "espnId": name.lower(),
            "abbrev": name, "region": None, "round": "championship",
            "winner": win, "gameDate": "2025-04-07T21:00Z",
        })

    return appearances


def make_test_tournament():
    """Build a tournament JSON structure for testing."""
    regions = {}
    for region in ["South", "East", "Midwest", "West"]:
        regions[region] = [
            {"seed": s, "name": f"{region[0]}{s}", "espnId": f"{region[0].lower()}{s}",
             "abbrev": f"{region[0]}{s}", "owner": None, "firstFour": False}
            for s in range(1, 17)
        ]
    return {
        "year": 9999,
        "title": "Test",
        "players": [{"name": f"P{i}", "color": c} for i, c in enumerate(PLAYER_COLORS)],
        "finalFourMatchups": [["South", "East"], ["Midwest", "West"]],
        "firstFour": [],
        "gameDates": [],
        "regions": regions,
        "results": {
            **{r: {"round1": [None]*8, "round2": [None]*4, "sweet16": [None]*2, "elite8": [None]}
               for r in ["South", "East", "Midwest", "West"]},
            "finalFour": [None, None],
            "championship": [None],
        },
    }


# ── Tests ──

section("Constants")
check(len(BRACKET_ORDER) == 16, "BRACKET_ORDER has 16 entries")
check(sorted(BRACKET_ORDER) == list(range(1, 17)), "BRACKET_ORDER contains seeds 1-16")
check(len(PLAYER_COLORS) == 8, "8 player colors defined")
check(all(c.startswith("#") and len(c) == 7 for c in PLAYER_COLORS), "all colors are valid hex")
check(len(set(PLAYER_COLORS)) == 8, "all player colors are unique")

section("ROUND_PATTERNS")
round_names = [rp[1] for rp in ROUND_PATTERNS]
for expected in ["firstFour", "round1", "round2", "sweet16", "elite8", "finalFour", "championship"]:
    check(expected in round_names, f"'{expected}' has a pattern")

section("backfill_results")
tournament = make_test_tournament()
appearances = make_test_appearances()
filled = setup_mod.backfill_results(tournament, appearances)
results = tournament["results"]
check(results["South"]["round1"][0] == "S1", "South R1 slot 0: 1-seed wins")
check(results["South"]["round1"][1] == "S8", "South R1 slot 1: 8-seed wins (8v9 matchup)")
check(results["South"]["round2"][0] == "S1", "South R2 slot 0: 1-seed advances")
check(results["South"]["sweet16"][0] == "S1", "South S16 slot 0: 1-seed advances")
check(results["South"]["elite8"][0] == "S1", "South E8: 1-seed wins region")
check(results["finalFour"][0] == "S1", "FF slot 0: South 1-seed wins (South vs East)")
check(results["finalFour"][1] == "M1", "FF slot 1: Midwest 1-seed wins (Midwest vs West)")
check(results["championship"][0] == "S1", "Championship: South 1-seed wins it all")

# Count total filled
regional_filled = sum(
    1 for r in ["South", "East", "Midwest", "West"]
    for rnd in ["round1", "round2", "sweet16", "elite8"]
    for v in results[r][rnd] if v is not None
)
ff_filled = sum(1 for v in results["finalFour"] if v) + sum(1 for v in results["championship"] if v)
total = regional_filled + ff_filled
check(total == 63, f"All 63 results filled (got {total})")

section("detect_ff_matchups")
tournament2 = make_test_tournament()
setup_mod.detect_ff_matchups(tournament2, appearances)
check(tournament2["finalFourMatchups"] == [["East", "South"], ["Midwest", "West"]] or
      tournament2["finalFourMatchups"] == [["South", "East"], ["Midwest", "West"]],
      f"FF matchups detected: {tournament2['finalFourMatchups']}")

section("build_schedule")
tournament3 = make_test_tournament()
# Need results filled first for later-round schedule mapping
setup_mod.backfill_results(tournament3, appearances)
schedule = setup_mod.build_schedule(tournament3, appearances)
check(schedule["South"]["round1"][0] is not None, "South R1 slot 0 has a game time")
check(schedule["championship"][0] is not None, "Championship has a game time")
sched_count = sum(
    1 for r in list(schedule)
    for v in (schedule[r] if isinstance(schedule[r], list)
              else [v for rnd in schedule[r].values() for v in rnd])
    if v is not None
)
check(sched_count == 63, f"All 63 game times scheduled (got {sched_count})")

section("resolve_first_four")
tournament4 = make_test_tournament()
tournament4["firstFour"] = [
    {"team1": "TeamA", "team1EspnId": "a1", "team1Abbrev": "TA",
     "team2": "TeamB", "team2EspnId": "b1", "team2Abbrev": "TB",
     "region": "South", "seed": 16, "winner": None},
]
tournament4["regions"]["South"][15] = {
    "seed": 16, "name": "TeamA / TeamB", "espnId": None, "abbrev": None,
    "owner": None, "firstFour": True,
}
ff_appearances = [
    {"seed": 16, "name": "TeamA", "espnId": "a1", "abbrev": "TA",
     "region": "South", "round": "firstFour", "winner": True, "gameDate": "2025-03-18T00:00Z"},
    {"seed": 16, "name": "TeamB", "espnId": "b1", "abbrev": "TB",
     "region": "South", "round": "firstFour", "winner": False, "gameDate": "2025-03-18T00:00Z"},
]
setup_mod.resolve_first_four(tournament4, ff_appearances)
check(tournament4["firstFour"][0]["winner"] == "TeamA", "FF winner resolved to TeamA")
check(tournament4["regions"]["South"][15]["name"] == "TeamA", "Region team name updated")
check(tournament4["regions"]["South"][15]["espnId"] == "a1", "Region team espnId updated")


section("update_year — owner preservation")
# Simulate what --update does: rebuild regions then restore owners
tournament5 = make_test_tournament()
# Assign owners
for region in ["South", "East", "Midwest", "West"]:
    for i, t in enumerate(tournament5["regions"][region]):
        t["owner"] = f"Player{i % 8 + 1}"

# Extract owners the way update_year does
owners = {}
for region_name, teams in tournament5["regions"].items():
    for t in teams:
        if t.get("owner"):
            owners[(region_name, t["seed"])] = t["owner"]

check(len(owners) == 64, f"extracted {len(owners)}/64 owners")

# Rebuild regions (simulates build_regions wiping owners)
from generate_bracket import build_regions
all_test_teams = {}
for region in ["South", "East", "Midwest", "West"]:
    for t in tournament5["regions"][region]:
        key = (region, t["seed"], t["espnId"])
        all_test_teams[key] = {
            "seed": t["seed"], "name": t["name"], "espnId": t["espnId"],
            "abbrev": t["abbrev"], "region": region, "round": "round1",
            "winner": None, "score": None, "gameDate": None,
        }

regions = build_regions(all_test_teams, [])
# Verify owners are gone after rebuild
rebuilt_owners = sum(1 for teams in regions.values() for t in teams if t.get("owner"))
check(rebuilt_owners == 0, "build_regions produces no owners (fresh rebuild)")

# Restore owners the way update_year does
for region_name, teams in regions.items():
    for t in teams:
        key = (region_name, t["seed"])
        if key in owners:
            t["owner"] = owners[key]

restored = sum(1 for teams in regions.values() for t in teams if t.get("owner"))
check(restored == 64, f"restored {restored}/64 owners after rebuild")

# Verify specific owners survived
check(regions["South"][0]["owner"] == "Player1", f"South seed 1 owner preserved: {regions['South'][0]['owner']}")
check(regions["East"][7]["owner"] == "Player8", f"East seed 8 owner preserved: {regions['East'][7]['owner']}")


section("update_year — FF matchup preservation")
# Verify that finalFourMatchups order is preserved through update logic
tournament6 = make_test_tournament()
tournament6["finalFourMatchups"] = [["Midwest", "West"], ["South", "East"]]
tournament6["results"]["finalFour"] = ["M1", "S1"]
tournament6["results"]["championship"] = ["M1"]

# backfill_results should not overwrite existing results
filled = setup_mod.backfill_results(tournament6, make_test_appearances())
check(tournament6["finalFourMatchups"] == [["Midwest", "West"], ["South", "East"]],
      "FF matchups unchanged after backfill")
check(tournament6["results"]["finalFour"] == ["M1", "S1"],
      "FF results unchanged (already filled)")


section("update_year — First Four two-pass resolution")
# Simulate the two-pass FF resolution from update_year
tournament7 = make_test_tournament()
tournament7["firstFour"] = [
    {"team1": "TeamA", "team1EspnId": "a1", "team1Abbrev": "TA",
     "team2": "TeamB", "team2EspnId": "b1", "team2Abbrev": "TB",
     "region": "South", "seed": 16, "winner": None},
]
tournament7["regions"]["South"][15] = {
    "seed": 16, "name": "TeamA / TeamB", "espnId": None, "abbrev": None,
    "owner": "Player3", "firstFour": True,
}

ff_apps = [
    {"seed": 16, "name": "TeamA", "espnId": "a1", "abbrev": "TA",
     "region": "South", "round": "firstFour", "winner": True, "score": 72, "gameDate": "2025-03-18T00:00Z"},
    {"seed": 16, "name": "TeamB", "espnId": "b1", "abbrev": "TB",
     "region": "South", "round": "firstFour", "winner": False, "score": 65, "gameDate": "2025-03-18T00:00Z"},
]

# Pass 1: resolve winner
setup_mod.resolve_first_four(tournament7, ff_apps)
check(tournament7["firstFour"][0]["winner"] == "TeamA", "Pass 1: FF winner resolved")
check(tournament7["regions"]["South"][15]["name"] == "TeamA", "Pass 1: region name updated")

# Simulate build_regions wiping the region entry (as update_year does)
tournament7["regions"]["South"][15] = {
    "seed": 16, "name": "TeamA / TeamB", "espnId": None, "abbrev": None,
    "owner": "Player3", "firstFour": True,
}

# Pass 2: re-resolve after rebuild
setup_mod.resolve_first_four(tournament7, ff_apps)
check(tournament7["regions"]["South"][15]["name"] == "TeamA",
      "Pass 2: region name re-patched after rebuild")
check(tournament7["regions"]["South"][15]["espnId"] == "a1",
      "Pass 2: espnId re-patched after rebuild")
check(tournament7["regions"]["South"][15]["owner"] == "Player3",
      "Owner survived both passes (not touched by resolve_first_four)")


# ── Summary ──
print(f"\n{'='*40}")
print(f"\033[{'32' if failed == 0 else '31'}m{passed} passed, {failed} failed\033[0m")
sys.exit(1 if failed else 0)
