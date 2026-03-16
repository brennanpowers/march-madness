#!/usr/bin/env python3
"""
Data integrity tests for tournament JSON files.

Validates that each year's JSON conforms to the expected schema,
has correct bracket structure, consistent owner assignments, and
valid results.

Usage:
    python3 tests/test-data-integrity.py
"""

import json
import sys
from pathlib import Path

import jsonschema

PROJECT_ROOT = Path(__file__).parent.parent
YEARS_SCHEMA = json.loads((PROJECT_ROOT / "data" / "years.schema.json").read_text())
TOURNAMENT_SCHEMA = json.loads((PROJECT_ROOT / "data" / "tournament-year.schema.json").read_text())
BRACKET_ORDER = [1, 16, 8, 9, 5, 12, 4, 13, 6, 11, 3, 14, 7, 10, 2, 15]
ROUND_SIZES = {"round1": 8, "round2": 4, "sweet16": 2, "elite8": 1}
REGIONS = ["South", "East", "Midwest", "West"]

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


def test_year(year, data):
    print(f"\n=== {year} ===")

    # JSON Schema validation
    try:
        jsonschema.validate(data, TOURNAMENT_SCHEMA)
        check(True, "JSON Schema valid")
    except jsonschema.ValidationError as e:
        check(False, f"JSON Schema: {e.message} (at {'/'.join(str(p) for p in e.absolute_path)})")

    # Semantic checks
    check(data.get("year") == year, f"year field is {year}")
    check(isinstance(data.get("title"), str) and len(data["title"]) > 0, "title is non-empty string")
    check(isinstance(data.get("players"), list) and len(data["players"]) == 8, "8 players defined")
    check(isinstance(data.get("gameDates"), list) and len(data["gameDates"]) > 0, f"gameDates has {len(data.get('gameDates', []))} entries")
    check(isinstance(data.get("firstFour"), list), "firstFour is a list")
    check(isinstance(data.get("finalFourMatchups"), list) and len(data["finalFourMatchups"]) == 2, "2 Final Four matchup pairs")
    check(isinstance(data.get("schedule"), dict), "schedule object exists")

    # Players
    for i, p in enumerate(data["players"]):
        check("name" in p and "color" in p, f"player {i+1} has name and color")
        check(p["color"].startswith("#") and len(p["color"]) == 7, f"player {i+1} color is valid hex")

    # Player names are unique
    names = [p["name"] for p in data["players"]]
    check(len(names) == len(set(names)), "player names are unique")

    # Regions
    check(set(data.get("regions", {}).keys()) == set(REGIONS), "all 4 regions present")

    all_teams = []
    for region_name in REGIONS:
        teams = data["regions"].get(region_name, [])
        check(len(teams) == 16, f"{region_name}: 16 teams")

        seeds = [t["seed"] for t in teams]
        check(sorted(seeds) == list(range(1, 17)), f"{region_name}: seeds 1-16 present")

        for t in teams:
            check(all(k in t for k in ["seed", "name", "espnId", "abbrev", "owner", "firstFour"]),
                  f"{region_name} seed {t['seed']}: all required fields present")
            check(isinstance(t["firstFour"], bool), f"{region_name} seed {t['seed']}: firstFour is bool")
            if t["owner"]:
                check(t["owner"] in names, f"{region_name} {t['name']}: owner '{t['owner']}' is a valid player")
            all_teams.append(t)

    # Team names are unique across entire tournament
    team_names = [t["name"] for t in all_teams]
    check(len(team_names) == len(set(team_names)), f"all {len(team_names)} team names are unique")

    # Owner counts (if any assigned)
    owner_counts = {}
    for t in all_teams:
        if t["owner"]:
            owner_counts[t["owner"]] = owner_counts.get(t["owner"], 0) + 1
    if owner_counts:
        for name, count in owner_counts.items():
            check(count == 8, f"{name} has {count}/8 teams")

    # Results structure
    results = data.get("results", {})
    for region_name in REGIONS:
        rr = results.get(region_name, {})
        for round_name, expected_size in ROUND_SIZES.items():
            arr = rr.get(round_name, [])
            check(len(arr) == expected_size, f"{region_name}.{round_name}: {len(arr)}/{expected_size} slots")
            for v in arr:
                if v is not None:
                    check(v in team_names, f"{region_name}.{round_name}: winner '{v}' exists in bracket")

    check(isinstance(results.get("finalFour"), list) and len(results["finalFour"]) == 2, "finalFour has 2 slots")
    check(isinstance(results.get("championship"), list) and len(results["championship"]) == 1, "championship has 1 slot")

    # Results consistency: later-round winners must have won previous round
    for region_name in REGIONS:
        rr = results[region_name]
        for ri in range(1, len(list(ROUND_SIZES.keys()))):
            round_name = list(ROUND_SIZES.keys())[ri]
            prev_round = list(ROUND_SIZES.keys())[ri - 1]
            for i, winner in enumerate(rr.get(round_name, [])):
                if winner is None:
                    continue
                feeder1 = rr[prev_round][i * 2] if i * 2 < len(rr[prev_round]) else None
                feeder2 = rr[prev_round][i * 2 + 1] if i * 2 + 1 < len(rr[prev_round]) else None
                check(winner in (feeder1, feeder2),
                      f"{region_name}.{round_name}[{i}]: winner '{winner}' came from previous round ({feeder1}, {feeder2})")

    # Schedule structure mirrors results
    schedule = data.get("schedule", {})
    for region_name in REGIONS:
        ss = schedule.get(region_name, {})
        for round_name, expected_size in ROUND_SIZES.items():
            arr = ss.get(round_name, [])
            check(len(arr) == expected_size, f"schedule.{region_name}.{round_name}: {len(arr)}/{expected_size} slots")

    check(isinstance(schedule.get("finalFour"), list) and len(schedule["finalFour"]) == 2, "schedule.finalFour has 2 slots")
    check(isinstance(schedule.get("championship"), list) and len(schedule["championship"]) == 1, "schedule.championship has 1 slot")

    # Final Four matchups reference valid regions
    for pair in data["finalFourMatchups"]:
        for r in pair:
            check(r in REGIONS, f"FF matchup region '{r}' is valid")

    # gameDates are sorted and YYYYMMDD format
    dates = data.get("gameDates", [])
    check(dates == sorted(dates), "gameDates are sorted")
    for d in dates:
        check(len(d) == 8 and d.isdigit(), f"gameDate '{d}' is YYYYMMDD format")


def main():
    global passed, failed

    years_path = PROJECT_ROOT / "data" / "years.json"
    if not years_path.exists():
        print("ERROR: data/years.json not found")
        sys.exit(1)

    years = json.loads(years_path.read_text())
    try:
        jsonschema.validate(years, YEARS_SCHEMA)
        check(True, "years.json JSON Schema valid")
    except jsonschema.ValidationError as e:
        check(False, f"years.json JSON Schema: {e.message}")
    check(isinstance(years, list) and len(years) > 0, f"years.json has {len(years)} years")
    check(years == sorted(years, reverse=True), "years.json sorted newest-first")

    for year in years:
        path = PROJECT_ROOT / "data" / f"{year}.json"
        check(path.exists(), f"data/{year}.json exists")
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        test_year(year, data)

    # Logo spot checks
    logos_dir = PROJECT_ROOT / "img" / "logos"
    check(logos_dir.exists(), "img/logos/ directory exists")
    if logos_dir.exists():
        png_count = len(list(logos_dir.glob("*.png")))
        check(png_count >= 64, f"img/logos/ has {png_count} PNGs (need at least 64)")

    print(f"\n{'='*40}")
    print(f"\033[{'32' if failed == 0 else '31'}m{passed} passed, {failed} failed\033[0m")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
