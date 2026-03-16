# March Madness Pool

Static website for a family March Madness draft pool. Hosted on GitHub Pages at `marchmadness.brennanpowers.com`.

## Pool Rules

- 8 players, snake draft, 8 teams each (all 64 teams drafted)
- Can draft any team at your pick — no position restrictions
- First Four teams: you draft the slot (both teams), winner goes to your roster
- Scoring: `seed × round_number` (a 12-seed winning in R64 = 12 pts, in R32 = 24 pts)
- Most total points wins
- Drafting the eventual champion also gets a piece of the pot

## Architecture

- **Pure HTML/CSS/JS** — no build step, no framework, no backend
- **Data-driven** — all tournament data lives in `data/<year>.json`
- **GitHub Pages** — deploy by pushing to `main`; CNAME file handles custom domain
- **ESPN API** — undocumented client-side endpoints for live scores and results
- **Static with live overlay** — JSON file is source of truth for rosters/owners; ESPN API overlays live scores and auto-fills results at runtime

## How Updates Work (No Backend)

1. **Draft day (one time)**: Use `admin.html` to assign teams → export JSON → replace `data/<year>.json` → `git push`
2. **During tournament (automatic)**: Every page load fetches ESPN scoreboards for all game dates, applies finished game results client-side. 60-second auto-refresh for live games.
3. **First Four winners**: Resolved automatically from ESPN live data — no manual entry needed
4. **Fallback**: If ESPN is unavailable, manually edit `results` in the JSON and push

## Key Files

| File | Purpose |
|------|---------|
| `index.html` | Single-page app with Bracket and Roster tabs |
| `css/style.css` | Light theme, responsive, mobile-first |
| `js/app.js` | Data loading, scoring engine, leaderboard, tabs, score breakdown |
| `js/bracket.js` | Region bracket rendering with logos, game times, connectors |
| `js/roster.js` | Player roster cards with team lists |
| `js/espn.js` | Shared utilities (`hexToRgba`), ESPN live integration, logo URLs |
| `data/<year>.json` | Tournament data: teams, draft owners, results, schedule |
| `data/years.json` | Array of available years (drives the year dropdown) |
| `data/tournament-year.schema.json` | JSON Schema for `<year>.json` files |
| `data/years.schema.json` | JSON Schema for `years.json` |
| `requirements-dev.txt` | Python dev dependencies (`jsonschema`) |
| `admin.html` | Password-gated (`marchmadness`) admin page for draft roster assignment |
| `scripts/setup_year.py` | One-stop setup: bracket + logos + results backfill + years manifest |
| `scripts/generate_bracket.py` | Core bracket generator (ESPN API → tournament JSON) |
| `docs/espn-core-v*.wadl` | ESPN API endpoint documentation (machine-readable) |

## Setup Workflow (New Year)

```bash
python3 scripts/setup_year.py 2027
# → data/2027.json (bracket + schedule + backfilled results if completed)
# → img/logos/*.png (68 team logos, cached locally)
# → data/years.json updated
# Then open admin.html to assign draft rosters, export JSON, git push
```

## Data Model

Each year's JSON (`data/2026.json`) contains:

- `year`, `title` — metadata
- `gameDates[]` — YYYYMMDD strings for every tournament game date (client fetches only these, not brute-force)
- `players[]` — name + color for each pool participant
- `regions{}` — 4 regions, each with 16 teams `{seed, name, espnId, abbrev, owner, firstFour}`
- `firstFour[]` — First Four play-in game details with ESPN IDs for both teams
- `results{}` — winners per round per region, plus `finalFour` and `championship`
- `schedule{}` — ISO datetimes per game slot (mirrors `results` structure)
- `finalFourMatchups` — which regions pair in the FF (auto-detected for completed years, set in admin for current year)

### Scoring

`points = seed × round_multiplier`

| Round | Key | Multiplier |
|-------|-----|-----------|
| Round of 64 | round1 | 1 |
| Round of 32 | round2 | 2 |
| Sweet 16 | sweet16 | 3 |
| Elite 8 | elite8 | 4 |
| Final Four | finalFour | 5 |
| Championship | championship | 6 |

### Results Array Indexing

Each region's `round1` array has 8 slots matching bracket seed order:
- `[0]`: 1v16 winner, `[1]`: 8v9, `[2]`: 5v12, `[3]`: 4v13, `[4]`: 6v11, `[5]`: 3v14, `[6]`: 7v10, `[7]`: 2v15

Later rounds feed forward: `round2[0]` = winner of `round1[0]` vs `round1[1]`, etc.

The `schedule` object mirrors this exact structure but stores ISO datetime strings instead of team names.

### Player Colors

8 maximally distinct colors for light-theme backgrounds:

| # | Name | Hex |
|---|------|-----|
| 1 | Red | `#d32f2f` |
| 2 | Blue | `#1565c0` |
| 3 | Green | `#2e7d32` |
| 4 | Orange | `#ef6c00` |
| 5 | Purple | `#7b1fa2` |
| 6 | Yellow | `#f5c518` |
| 7 | Slate | `#455a64` |
| 8 | Brown | `#8d4e2a` |

Team slots use the owner's color: 20% tint + 2px border for winners, 8% tint + 0.35 opacity for losers, 10% tint for pending.

## Script Load Order

`espn.js` → `app.js` → `bracket.js` → `roster.js`

`espn.js` must load first because it defines `hexToRgba()` and `teamLogoUrl()` used by all other scripts.

## Tests

```bash
# Install dev dependencies (one time)
pip3 install -r requirements-dev.txt

# Data integrity — validates all year JSON files against JSON Schemas + semantic checks
python3 tests/test_data_integrity.py

# Setup script — unit tests for backfill, FF detection, schedule building
python3 tests/test_setup_script.py

# Scoring engine — open in browser, exercises JS scoring/bracket logic
open tests/test-scoring.html
```

## Context Index

- **espn-api** — ESPN's undocumented APIs: endpoints, response structures, gotchas, year-to-year headline differences, filtering strategies, logo CDN
- **admin-page** — Admin page architecture: auth, data flow, two input methods, snapshots, First Four handling, what's excluded
- **scoring-and-bracket** — Scoring formula, bracket seed order, results array mapping, elimination detection algorithm, winner/loser rendering, CSS alignment trick
- **json-schemas** — Comprehensive specifications for `years.json` and `<year>.json`: every field, type, constraint, array index mapping, lifecycle, and cross-references
