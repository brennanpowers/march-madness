#!/usr/bin/env python3
"""
Full setup for a tournament year: generate bracket data + download logos.

This is the one-stop script to run when setting up a new year. It:
  1. Runs the bracket generator (fetches teams, seeds, regions from ESPN)
  2. Downloads all team logos to img/logos/<espnId>.png
  3. Updates data/years.json to include the new year
  4. Downloads First Four team logos separately (since they may not be
     in the main bracket until their game is decided)

Usage:
    python3 scripts/setup_year.py [year]
    python3 scripts/setup_year.py 2026

After running:
  - data/<year>.json has the full bracket
  - img/logos/ has all team logo PNGs
  - data/years.json lists all available years
  - Open admin.html to assign draft rosters
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen, Request
from urllib.error import URLError
from pathlib import Path

# Import the bracket generator
sys.path.insert(0, str(Path(__file__).parent))
from generate_bracket import (
    CORE_API,
    HEADERS,
    ROUND_PATTERNS,
    build_team_directory,
    fetch_json,
    get_all_event_urls,
    collect_all_teams,
    build_regions,
    build_tournament_json,
    validate,
)

# Bracket seed order: 1v16, 8v9, 5v12, 4v13, 6v11, 3v14, 7v10, 2v15
BRACKET_ORDER = [1, 16, 8, 9, 5, 12, 4, 13, 6, 11, 3, 14, 7, 10, 2, 15]
ROUND_NAMES = ["round1", "round2", "sweet16", "elite8"]

def detect_ff_matchups(tournament, all_appearances):
    """Detect Final Four matchup pairings from event data.

    Each Final Four event has 2 competitors. We look up which region each
    team belongs to, then group them into semifinal pairs.
    """
    regions = tournament["regions"]
    team_to_region = {}
    for region_name, teams in regions.items():
        for t in teams:
            team_to_region[t["name"]] = region_name

    # Find Final Four games: pairs of teams in the same event
    # Group FF appearances by their event (consecutive pairs in all_appearances
    # with round=="finalFour" represent the two teams in one game)
    ff_teams = [t for t in all_appearances if t.get("round") == "finalFour"]

    # Group by pairing: FF teams from the same event share the same
    # (espnId-pair). Since we don't have event IDs, match by seed pairs.
    # Each FF game has one team from each of two regions.
    seen_pairs = []
    used_names = set()
    for t in ff_teams:
        name = t["name"]
        if name in used_names:
            continue
        region = team_to_region.get(name)
        if not region:
            continue
        # Find the opponent: another FF team from a different region
        for other in ff_teams:
            if other["name"] == name or other["name"] in used_names:
                continue
            other_region = team_to_region.get(other["name"])
            if other_region and other_region != region:
                pair = sorted([region, other_region])
                if pair not in seen_pairs:
                    seen_pairs.append(pair)
                    used_names.add(name)
                    used_names.add(other["name"])
                break

    if len(seen_pairs) == 2:
        tournament["finalFourMatchups"] = seen_pairs


def resolve_first_four(tournament, all_appearances):
    """For completed First Four games, set the winner and update region teams."""
    for ff in tournament.get("firstFour", []):
        if ff["winner"]:
            continue  # already resolved

        # Find the FF winner from all appearances
        for t in all_appearances:
            if (t["region"] == ff["region"] and t["seed"] == ff["seed"]
                    and t["round"] == "firstFour" and t.get("winner") is True):
                ff["winner"] = t["name"]
                # Update the region team entry
                for rt in tournament["regions"].get(ff["region"], []):
                    if rt["seed"] == ff["seed"] and rt["firstFour"]:
                        rt["name"] = t["name"]
                        rt["espnId"] = t["espnId"]
                        rt["abbrev"] = t["abbrev"]
                break


def backfill_results(tournament, all_appearances):
    """Populate results arrays from completed game data.

    Uses the winner boolean from ESPN event data to fill in results.
    Works round-by-round: round1 is mapped by seed position, later
    rounds are mapped by tracing the bracket tree.

    all_appearances is a flat list of every team entry from every event
    (not deduplicated — a team appears once per game they played in).
    """
    regions = tournament["regions"]
    results = tournament["results"]

    # Collect all winners grouped by (region, round)
    # Key: (region, round) → list of winner team entries
    winners_by_round = {}
    for t in all_appearances:
        if t.get("winner") is True and t.get("round"):
            key = (t["region"], t["round"])
            winners_by_round.setdefault(key, []).append(t)

    for region_name, region_teams in regions.items():
        teams_by_seed = {t["seed"]: t for t in region_teams}
        ordered = [teams_by_seed.get(s) for s in BRACKET_ORDER]
        teams_by_name = {t["name"]: t for t in region_teams}

        # Round 1: map by seed matchups
        r1_winners = winners_by_round.get((region_name, "round1"), [])
        for w in r1_winners:
            wt = teams_by_name.get(w["name"]) or teams_by_seed.get(w["seed"])
            if not wt:
                continue
            bracket_idx = BRACKET_ORDER.index(wt["seed"]) if wt["seed"] in BRACKET_ORDER else -1
            if bracket_idx == -1:
                continue
            slot = bracket_idx // 2
            results[region_name]["round1"][slot] = wt["name"]

        # Round 2+: map by finding which slot the winner feeds into
        for round_idx, round_name in enumerate(ROUND_NAMES[1:], 1):
            prev_round = ROUND_NAMES[round_idx - 1]
            prev_results = results[region_name][prev_round]
            round_results = results[region_name][round_name]
            rnd_winners = winners_by_round.get((region_name, round_name), [])

            for w in rnd_winners:
                wt = teams_by_name.get(w["name"]) or teams_by_seed.get(w["seed"])
                if not wt:
                    continue
                # Find which slot: check which pair of previous results contains this team
                for i in range(len(round_results)):
                    feeder1 = prev_results[i * 2] if i * 2 < len(prev_results) else None
                    feeder2 = prev_results[i * 2 + 1] if i * 2 + 1 < len(prev_results) else None
                    if wt["name"] in (feeder1, feeder2):
                        round_results[i] = wt["name"]
                        break

    # Final Four — winners might have region=None (national events)
    ff_winners = []
    for key, winners in winners_by_round.items():
        if key[1] == "finalFour":
            ff_winners.extend(winners)

    ff_matchups = tournament["finalFourMatchups"]
    for w in ff_winners:
        # Find which region this team belongs to
        for region_name, region_teams in regions.items():
            wt = next((t for t in region_teams if t["name"] == w["name"]), None)
            if wt:
                for i, pair in enumerate(ff_matchups):
                    if region_name in pair and results["finalFour"][i] is None:
                        results["finalFour"][i] = wt["name"]
                break

    # Championship
    champ_winners = []
    for key, winners in winners_by_round.items():
        if key[1] == "championship":
            champ_winners.extend(winners)

    for w in champ_winners:
        for region_teams in regions.values():
            wt = next((t for t in region_teams if t["name"] == w["name"]), None)
            if wt and results["championship"][0] is None:
                results["championship"][0] = wt["name"]
                break

    # Count filled results
    filled = sum(
        1 for r in ["South", "East", "Midwest", "West"]
        for rnd in ROUND_NAMES
        for v in results[r][rnd] if v is not None
    )
    filled += sum(1 for v in results["finalFour"] if v)
    filled += sum(1 for v in results["championship"] if v)
    return filled


def build_schedule(tournament, all_appearances):
    """Build a schedule object mirroring the results structure but with game datetimes.

    Each slot gets the ISO datetime of the game (e.g., "2026-03-19T18:50Z").
    Two competitors from the same game share the same datetime, so we
    deduplicate by taking one per matchup slot.
    """
    regions = tournament["regions"]
    schedule = {
        r: {
            "round1": [None] * 8,
            "round2": [None] * 4,
            "sweet16": [None] * 2,
            "elite8": [None],
        }
        for r in regions
    }
    schedule["finalFour"] = [None, None]
    schedule["championship"] = [None]

    for t in all_appearances:
        region = t.get("region")
        round_name = t.get("round")
        game_date = t.get("gameDate")
        if not game_date or not round_name:
            continue

        if round_name in ("finalFour", "championship"):
            # Map via team name → region
            team_region = None
            for rn, teams in regions.items():
                if any(rt["name"] == t["name"] for rt in teams):
                    team_region = rn
                    break

            if round_name == "finalFour" and team_region:
                for i, pair in enumerate(tournament["finalFourMatchups"]):
                    if team_region in pair and schedule["finalFour"][i] is None:
                        schedule["finalFour"][i] = game_date
                        break
            elif round_name == "championship":
                if schedule["championship"][0] is None:
                    schedule["championship"][0] = game_date
            continue

        if not region or region not in schedule:
            continue

        # Find the slot index using same logic as backfill_results
        teams_by_seed = {rt["seed"]: rt for rt in regions[region]}
        if round_name == "round1":
            bracket_idx = BRACKET_ORDER.index(t["seed"]) if t["seed"] in BRACKET_ORDER else -1
            if bracket_idx >= 0:
                slot = bracket_idx // 2
                if schedule[region]["round1"][slot] is None:
                    schedule[region]["round1"][slot] = game_date
        else:
            # Later rounds: find slot via bracket tree
            results = tournament["results"]
            round_idx = ROUND_NAMES.index(round_name) if round_name in ROUND_NAMES else -1
            if round_idx > 0:
                prev_round = ROUND_NAMES[round_idx - 1]
                prev_results = results[region][prev_round]
                round_schedule = schedule[region][round_name]
                for i in range(len(round_schedule)):
                    feeder1 = prev_results[i * 2] if i * 2 < len(prev_results) else None
                    feeder2 = prev_results[i * 2 + 1] if i * 2 + 1 < len(prev_results) else None
                    if t["name"] in (feeder1, feeder2) and round_schedule[i] is None:
                        round_schedule[i] = game_date
                        break

    return schedule


ESPN_LOGO_URL = "https://cdn.espn.com/i/teamlogos/ncaa/500/{espn_id}.png"
PROJECT_ROOT = Path(__file__).parent.parent


def download_logo(espn_id, output_dir):
    """Download a single team logo. Returns (espn_id, success)."""
    if not espn_id:
        return (espn_id, False)

    output_path = output_dir / f"{espn_id}.png"
    if output_path.exists() and output_path.stat().st_size > 0:
        return (espn_id, True)  # already cached

    url = ESPN_LOGO_URL.format(espn_id=espn_id)
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=15) as resp:
            data = resp.read()
            if len(data) > 100:  # sanity check - real PNGs are >100 bytes
                output_path.write_bytes(data)
                return (espn_id, True)
    except (URLError, TimeoutError) as e:
        print(f"  Warning: failed to download logo for {espn_id}: {e}", file=sys.stderr)
    return (espn_id, False)


def download_all_logos(tournament_data, output_dir):
    """Download logos for all teams in the tournament."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect all ESPN IDs (region teams + first four teams)
    espn_ids = set()
    for teams in tournament_data["regions"].values():
        for t in teams:
            if t.get("espnId"):
                espn_ids.add(t["espnId"])

    for ff in tournament_data.get("firstFour", []):
        if ff.get("team1EspnId"):
            espn_ids.add(ff["team1EspnId"])
        if ff.get("team2EspnId"):
            espn_ids.add(ff["team2EspnId"])

    print(f"\n  Downloading logos for {len(espn_ids)} teams...")
    succeeded = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {
            pool.submit(download_logo, eid, output_dir): eid
            for eid in espn_ids
        }
        for future in as_completed(futures):
            eid, ok = future.result()
            if ok:
                succeeded += 1
            else:
                failed += 1

    print(f"  Logos: {succeeded} downloaded, {failed} failed")
    if failed:
        print(f"  (Failed logos will fall back to ESPN CDN at runtime)")


def update_years_json(year):
    """Add the year to data/years.json if not already present."""
    years_path = PROJECT_ROOT / "data" / "years.json"
    if years_path.exists():
        years = json.loads(years_path.read_text())
    else:
        years = []

    if year not in years:
        years.append(year)
        years.sort(reverse=True)

    years_path.write_text(json.dumps(years))
    print(f"\n  Updated years.json: {years}")


def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    print(f"=== Setting up March Madness {year} ===\n")

    # Step 1: Generate bracket data
    print("Step 1: Generating bracket data...")
    team_directory = build_team_directory()
    event_urls = get_all_event_urls(year)
    print(f"  Found {len(event_urls)} postseason events")

    if not event_urls:
        print("ERROR: No events found. Is the bracket set?", file=sys.stderr)
        sys.exit(1)

    all_teams, first_four_games, all_appearances, game_dates = collect_all_teams(event_urls, team_directory, year)
    print(f"  Found {len(all_teams)} unique team entries")
    print(f"  Game dates: {', '.join(game_dates[:5])}{'...' if len(game_dates) > 5 else ''} ({len(game_dates)} total)")

    regions = build_regions(all_teams, first_four_games)
    validate(regions, first_four_games)

    tournament = build_tournament_json(year, regions, first_four_games, game_dates)

    data_dir = PROJECT_ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    data_path = data_dir / f"{year}.json"

    # Step 1b: Resolve First Four and backfill results for completed games
    print("\n  Resolving First Four winners...")
    resolve_first_four(tournament, all_appearances)
    for ff in tournament.get("firstFour", []):
        if ff["winner"]:
            print(f"    {ff['team1']} vs {ff['team2']} → {ff['winner']}")
        else:
            print(f"    {ff['team1']} vs {ff['team2']} → TBD")

    print("\n  Detecting Final Four matchup pairings...")
    detect_ff_matchups(tournament, all_appearances)
    print(f"  Final Four: {tournament['finalFourMatchups']}")

    print("\n  Backfilling results from completed games...")
    filled = backfill_results(tournament, all_appearances)
    print(f"  Filled {filled}/63 game results")

    print("\n  Building game schedule...")
    tournament["schedule"] = build_schedule(tournament, all_appearances)
    sched_filled = sum(
        1 for r in list(regions) + ["finalFour", "championship"]
        for v in (tournament["schedule"][r] if isinstance(tournament["schedule"][r], list)
                  else [v for rnd in tournament["schedule"][r].values() for v in rnd])
        if v is not None
    )
    print(f"  Scheduled {sched_filled}/63 game times")

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(tournament, f, indent=2)
    print(f"\n  Written to {data_path}")

    # Step 2: Download logos
    print("\nStep 2: Downloading team logos...")
    logo_dir = PROJECT_ROOT / "img" / "logos"
    download_all_logos(tournament, logo_dir)

    # Step 3: Update years manifest
    print("\nStep 3: Updating years manifest...")
    update_years_json(year)

    print(f"\n=== Setup complete for {year} ===")
    print(f"\nNext steps:")
    print(f"  1. Open admin.html to set player names and assign draft rosters")
    print(f"  2. Export the JSON and save to data/{year}.json")
    print(f"  3. git add -A && git commit && git push")


if __name__ == "__main__":
    main()
