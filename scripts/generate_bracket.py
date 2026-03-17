#!/usr/bin/env python3
"""
Generate tournament JSON data from ESPN APIs.

Fetches all NCAA tournament teams, seeds, regions, and ESPN IDs by:
  1. Building a team ID → name/abbrev lookup from the ESPN teams directory
  2. Fetching all postseason event IDs from the core API
  3. Fetching event details for competitor IDs, seeds, and regions
  4. Cross-referencing to produce the full tournament bracket

Usage:
    python3 scripts/generate-bracket.py [year]
    python3 scripts/generate-bracket.py 2026
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen, Request
from urllib.error import URLError
from pathlib import Path

CORE_API = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball"
SITE_API = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"
HEADERS = {"User-Agent": "Mozilla/5.0"}

PLAYER_COLORS = [
    "#d32f2f", "#1565c0", "#2e7d32", "#ef6c00",
    "#7b1fa2", "#f5c518", "#455a64", "#8d4e2a",
]


def fetch_json(url):
    """Fetch JSON from a URL, returning None on failure."""
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except (URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"  Warning: failed to fetch {url}: {e}", file=sys.stderr)
        return None


def build_team_directory():
    """Fetch all D1 teams from the ESPN site API to build an ID → info lookup."""
    print("  Fetching team directory...")
    directory = {}
    page = 1
    while True:
        url = f"{SITE_API}/teams?limit=500&page={page}"
        data = fetch_json(url)
        if not data:
            break
        teams = data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
        if not teams:
            break
        for entry in teams:
            team = entry.get("team", {})
            team_id = str(team.get("id", ""))
            if team_id:
                directory[team_id] = {
                    "name": team.get("location", team.get("displayName", "")),
                    "displayName": team.get("displayName", ""),
                    "abbrev": team.get("abbreviation", ""),
                }
        page_count = data.get("pageCount", 1)
        if page >= page_count:
            break
        page += 1
    print(f"  Loaded {len(directory)} teams into directory")
    return directory


def get_all_event_urls(year):
    """Fetch all postseason event URLs from the core API (paginated)."""
    event_urls = []
    page = 1
    while True:
        url = f"{CORE_API}/seasons/{year}/types/3/events?limit=50&page={page}"
        print(f"  Fetching event list page {page}...")
        data = fetch_json(url)
        if not data:
            break
        items = data.get("items", [])
        if not items:
            break
        for item in items:
            ref = item.get("$ref", "")
            if ref:
                event_urls.append(ref)
        page_count = data.get("pageCount", 1)
        if page >= page_count:
            break
        page += 1
    return event_urls


ROUND_PATTERNS = [
    ("First Four", "firstFour"),
    ("1st Round", "round1"),
    ("2nd Round", "round2"),
    ("Sweet 16", "sweet16"),
    ("Regional Semifinal", "sweet16"),
    ("Elite Eight", "elite8"),
    ("Elite 8", "elite8"),
    ("Regional Final", "elite8"),
    ("Final Four", "finalFour"),
    ("National Semifinal", "finalFour"),
    ("National Championship", "championship"),
    ("Championship", "championship"),
]


def parse_event(data, team_directory, year):
    """Extract team info from an event detail response using team directory.

    Returns (teams_found, event_date) where event_date is YYYYMMDD or None.
    """
    if not data:
        return [], None

    # Extract event date as YYYYMMDD in US Eastern time.
    # ESPN scoreboard API indexes by ET date, but the core API returns UTC.
    # A 9 PM ET game shows as the next day in UTC, so we must convert.
    event_date = None
    raw_date = data.get("date", "")
    if raw_date and len(raw_date) >= 10:
        from datetime import datetime, timezone, timedelta
        try:
            utc_dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            et_offset = timedelta(hours=-4)  # EDT (tournament is always in March/April)
            et_dt = utc_dt.astimezone(timezone(et_offset))
            event_date = et_dt.strftime("%Y%m%d")
        except (ValueError, TypeError):
            event_date = raw_date[:10].replace("-", "")
    # Keep full ISO datetime for schedule display
    event_datetime = raw_date or None

    teams_found = []
    for comp in data.get("competitions", []):
        region = None
        round_name = None
        for note in comp.get("notes", []):
            headline = note.get("headline", "")
            # Must contain "Championship" and a region name to be NCAA tournament
            # This filters out NIT, CBI, CIT ("College Basketball Crown", etc.)
            if "Championship" not in headline:
                continue
            for r in ["South", "East", "Midwest", "West"]:
                if r in headline:
                    region = r
                    break
            for pattern, rname in ROUND_PATTERNS:
                if pattern in headline:
                    round_name = rname
                    break

        # Regional games need a region; national games (FF/Championship) don't
        if not region and round_name not in ("finalFour", "championship"):
            continue

        for competitor in comp.get("competitors", []):
            seed = competitor.get("curatedRank", {}).get("current")
            team_id = str(competitor.get("id", ""))

            # Skip TBD placeholders (negative IDs) and invalid seeds
            if not seed or not team_id or int(team_id) <= 0:
                continue
            if seed > 16:
                continue
            # Regional rounds require a region; national rounds (FF/Champ) don't
            if not region and round_name not in ("finalFour", "championship"):
                continue

            team_info = team_directory.get(team_id)
            if not team_info:
                # Fallback: fetch team info from core API
                team_data = fetch_json(f"{CORE_API}/seasons/{year}/teams/{team_id}")
                if team_data:
                    team_info = {
                        "name": team_data.get("location", team_data.get("displayName", f"Team {team_id}")),
                        "displayName": team_data.get("displayName", ""),
                        "abbrev": team_data.get("abbreviation", ""),
                    }
                    team_directory[team_id] = team_info
                else:
                    team_info = {"name": f"Team {team_id}", "displayName": "", "abbrev": ""}

            raw_score = competitor.get("score")
            if isinstance(raw_score, dict):
                score = int(raw_score["value"]) if raw_score.get("value") is not None else None
            elif raw_score is not None and str(raw_score).isdigit():
                score = int(raw_score)
            else:
                score = None

            teams_found.append({
                "seed": seed,
                "name": team_info.get("name", f"Team {team_id}"),
                "displayName": team_info.get("displayName", ""),
                "espnId": team_id,
                "abbrev": team_info.get("abbrev", ""),
                "region": region,
                "round": round_name,
                "winner": competitor.get("winner", None),
                "score": score,
                "gameDate": event_datetime,
            })
    return teams_found, event_date


def fetch_event_detail(url, team_directory, year):
    """Fetch a single event's details and parse teams."""
    data = fetch_json(url)
    if not data:
        return [], None
    return parse_event(data, team_directory, year)


def collect_all_teams(event_urls, team_directory, year):
    """Concurrently fetch event details and collect team info.

    Returns (all_teams, first_four_games, all_appearances, game_dates) where:
      - all_teams: deduplicated dict for bracket building
      - first_four_games: detected First Four matchups
      - all_appearances: every team entry from every event (for result backfilling)
      - game_dates: sorted list of unique YYYYMMDD date strings
    """
    all_teams = {}
    all_appearances = []
    game_dates = set()

    print(f"  Fetching details for {len(event_urls)} events (concurrent)...")
    with ThreadPoolExecutor(max_workers=12) as pool:
        future_to_url = {
            pool.submit(fetch_event_detail, url, team_directory, year): url
            for url in event_urls
        }
        done_count = 0
        for future in as_completed(future_to_url):
            done_count += 1
            if done_count % 20 == 0:
                print(f"  ...{done_count}/{len(event_urls)} events fetched")
            teams, event_date = future.result()
            if event_date:
                game_dates.add(event_date)
            for t in teams:
                all_appearances.append(t)
                key = (t["region"], t["seed"], t["espnId"])
                if key not in all_teams:
                    all_teams[key] = t

    # Identify First Four pairs: multiple teams with same region+seed
    # Only consider teams that have a region (excludes FF/Championship national games)
    region_seed_groups = {}
    for t in all_teams.values():
        if t["region"] is None:
            continue
        rs_key = (t["region"], t["seed"])
        region_seed_groups.setdefault(rs_key, []).append(t)

    first_four_games = []
    for (region, seed), group in region_seed_groups.items():
        if len(group) == 2:
            first_four_games.append({
                "team1": group[0]["name"],
                "team1EspnId": group[0]["espnId"],
                "team1Abbrev": group[0]["abbrev"],
                "team2": group[1]["name"],
                "team2EspnId": group[1]["espnId"],
                "team2Abbrev": group[1]["abbrev"],
                "region": region,
                "seed": seed,
                "winner": None,
            })

    return all_teams, first_four_games, all_appearances, sorted(game_dates)


def build_regions(all_teams, first_four_games):
    """Organize teams into regions with consistent schema."""
    regions = {"South": [], "East": [], "Midwest": [], "West": []}

    ff_slots = {}
    for ff in first_four_games:
        ff_slots[(ff["region"], ff["seed"])] = ff

    seen_region_seeds = set()
    regional_teams = [t for t in all_teams.values() if t["region"] is not None]
    for t in sorted(regional_teams, key=lambda x: (x["region"], x["seed"])):
        region = t["region"]
        seed = t["seed"]
        rs_key = (region, seed)

        if rs_key in seen_region_seeds:
            continue
        seen_region_seeds.add(rs_key)

        is_ff = rs_key in ff_slots
        if is_ff:
            ff = ff_slots[rs_key]
            entry = {
                "seed": seed,
                "name": f"{ff['team1']} / {ff['team2']}",
                "espnId": None,
                "abbrev": None,
                "owner": None,
                "firstFour": True,
            }
        else:
            entry = {
                "seed": seed,
                "name": t["name"],
                "espnId": t["espnId"],
                "abbrev": t["abbrev"],
                "owner": None,
                "firstFour": False,
            }

        if region in regions:
            regions[region].append(entry)

    for region in regions:
        regions[region].sort(key=lambda x: x["seed"])

    return regions


def build_tournament_json(year, regions, first_four_games, game_dates=None):
    """Assemble the complete tournament JSON."""
    return {
        "year": year,
        "title": f"March Madness Pool {year}",
        "gameDates": game_dates or [],
        "players": [
            {"name": f"Player {i + 1}", "color": color}
            for i, color in enumerate(PLAYER_COLORS)
        ],
        "finalFourMatchups": [["South", "East"], ["Midwest", "West"]],
        "firstFour": first_four_games,
        "regions": regions,
        "results": {
            **{
                r: {
                    "round1": [None] * 8,
                    "round2": [None] * 4,
                    "sweet16": [None] * 2,
                    "elite8": [None],
                }
                for r in ["South", "East", "Midwest", "West"]
            },
            "finalFour": [None, None],
            "championship": [None],
        },
    }


def validate(regions, first_four_games):
    """Print warnings for incomplete data."""
    total_teams = sum(len(r) for r in regions.values())
    ff_count = len(first_four_games)
    print(f"\n  Teams found: {total_teams} across 4 regions")
    print(f"  First Four games: {ff_count}")

    for name, teams in regions.items():
        seeds = [t["seed"] for t in teams]
        expected = list(range(1, 17))
        missing = [s for s in expected if s not in seeds]
        if missing:
            print(f"  WARNING: {name} missing seeds: {missing}")
        if len(teams) != 16:
            print(f"  WARNING: {name} has {len(teams)} teams (expected 16)")
        else:
            print(f"  {name}: 16/16 seeds filled")

    for ff in first_four_games:
        print(f"  First Four: {ff['team1']} vs {ff['team2']} → {ff['region']} ({ff['seed']} seed)")


def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    print(f"Generating bracket data for {year}...\n")

    # Step 1: Build team directory (name lookup by ESPN ID)
    team_directory = build_team_directory()

    # Step 2: Get all postseason event URLs
    event_urls = get_all_event_urls(year)
    print(f"  Found {len(event_urls)} postseason events")

    if not event_urls:
        print("ERROR: No events found. Is the bracket set?", file=sys.stderr)
        sys.exit(1)

    # Step 3: Fetch event details and extract teams
    all_teams, first_four_games, all_appearances, game_dates = collect_all_teams(event_urls, team_directory, year)
    print(f"  Found {len(all_teams)} unique team entries")

    # Step 4: Build regions
    regions = build_regions(all_teams, first_four_games)

    # Step 5: Validate
    validate(regions, first_four_games)

    # Step 6: Build and write JSON
    tournament = build_tournament_json(year, regions, first_four_games, game_dates)

    output_dir = Path(__file__).parent.parent / "data"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{year}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(tournament, f, indent=2)

    print(f"\n  Written to {output_path}")
    print("  Next steps:")
    print("  1. Fill in player names and colors in the 'players' array")
    print("  2. Assign 'owner' for each team after the draft")
    print("  3. Update 'results' as games are played")


if __name__ == "__main__":
    main()
