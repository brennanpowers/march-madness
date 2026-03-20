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
- **GitHub Pages** — deployed via GitHub Actions workflow on push to `main`; CNAME file handles custom domain
- **Cache-busting** — Actions workflow replaces `__CACHE_BUST__` placeholders in HTML with the short commit SHA before deploying, so browsers always fetch fresh JS/CSS
- **ESPN API** — undocumented client-side endpoints for live scores and results
- **Static with live overlay** — JSON file is source of truth for rosters/owners; ESPN API overlays live scores and auto-fills results at runtime

## How Updates Work (No Backend)

1. **Draft day (one time)**: Use `admin.html` to assign teams → export JSON → replace `data/<year>.json` → `git push`
2. **During tournament**: Run `setup_year.py --update <year>` after each day's games to bake results and scores into the JSON, then `git push`. Between updates, the frontend shows live scores from ESPN on game days (auto-refreshes every 60s). On non-game days and for past tournaments, zero ESPN API calls — everything renders from static JSON.
3. **First Four winners**: Resolved automatically by `--update` or by the frontend's live ESPN overlay
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
| `admin.html` | Password-gated admin page for draft roster assignment |
| `scripts/setup_year.py` | Full setup (`2027`) or update existing year (`--update 2026`) |
| `scripts/generate_bracket.py` | Core bracket generator (ESPN API → tournament JSON) |
| `docs/espn-core-v*.wadl` | ESPN API endpoint documentation (machine-readable) |
| `.github/workflows/deploy.yml` | GitHub Actions workflow: cache-bust + deploy to Pages |

## Setup Workflow

### New Year (one-time)

```bash
python3 scripts/setup_year.py 2027
```

Creates `data/2027.json` from scratch, downloads logos, updates `years.json`. Players have default names ("Player 1"–"Player 8") and no owner assignments. Open `admin.html` to assign draft rosters, export JSON, then `git push`.

### During Tournament

```bash
python3 scripts/setup_year.py --update 2026
```

Refreshes results, schedule, scores, and First Four winners from ESPN. **Preserves:** player names, colors, owner assignments, Final Four matchup order. Run this after each day's games to bake scores into the JSON. Between updates, the frontend handles live scores from ESPN automatically.

### What `--update` Does vs Doesn't

| Updated | Preserved |
|---------|-----------|
| `results` (backfills null slots) | `players` (names, colors) |
| `schedule` (game times) | Owner assignments on teams |
| `gameScores` (per-team scores) | `finalFourMatchups` order |
| `gameDates` (ET-corrected) | |
| `firstFour` winners | |
| Team logos (downloads new) | |

## Data Model

Each year's JSON (`data/2026.json`) contains:

- `year`, `title` — metadata
- `gameDates[]` — YYYYMMDD strings in US Eastern time for every tournament game date
- `players[]` — name + color for each pool participant
- `regions{}` — 4 regions, each with 16 teams `{seed, name, espnId, abbrev, owner, firstFour}`
- `firstFour[]` — First Four play-in game details with ESPN IDs for both teams
- `results{}` — winners per round per region, plus `finalFour` and `championship`
- `schedule{}` — ISO datetimes per game slot (mirrors `results` structure)
- `gameScores{}` — per-team scores by round (e.g., `{"Auburn": {"round1": 83, "round2": 82}}`)
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
playwright install chromium  # one-time browser download for page load tests

# Data integrity — validates all year JSON files against JSON Schemas + semantic checks
python3 tests/test_data_integrity.py

# Setup script — unit tests for backfill, FF detection, schedule building
python3 tests/test_setup_script.py

# Page load — loads index.html and admin.html in headless Chromium, catches runtime JS errors
python3 tests/test_page_loads.py

# Scoring engine — open in browser, exercises JS scoring/bracket logic
open tests/test-scoring.html
```
