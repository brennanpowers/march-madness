# March Madness Pool

Static website for a family March Madness draft pool. Hosted on GitHub Pages at `marchmadness.brennanpowers.com`.

## Architecture

- **Pure HTML/CSS/JS** — no build step, no framework
- **Data-driven** — all tournament data lives in `data/<year>.json`
- **GitHub Pages** — deploy by pushing to `main`; CNAME file handles custom domain
- **ESPN API** — unofficial `site.api.espn.com` endpoints for live scores (client-side)

## Key Files

| File | Purpose |
|------|---------|
| `index.html` | Single-page app with Bracket and Roster tabs |
| `css/style.css` | Dark theme, responsive, mobile-first |
| `js/app.js` | Data loading, scoring engine, leaderboard, tabs |
| `js/bracket.js` | Region bracket rendering with connector lines |
| `js/roster.js` | Player roster cards with team lists |
| `data/<year>.json` | Tournament data: teams, draft owners, results |
| `js/espn.js` | ESPN live data integration, logo URLs, scoreboard fetching |
| `admin.html` | Password-gated admin page for draft roster assignment |
| `scripts/setup-year.py` | One-stop setup: bracket + logos + results backfill |
| `scripts/generate_bracket.py` | Core bracket generator (ESPN API → tournament JSON) |

## Data Model

Each year's JSON (`data/2026.json`) contains:

- `players[]` — name + color for each pool participant
- `gameDates[]` — YYYYMMDD strings for every tournament game date (used by client to avoid brute-force fetching)
- `regions{}` — 4 regions, each with 16 teams (seed, name, espnId, abbrev, owner, firstFour)
- `firstFour[]` — First Four play-in game details
- `results{}` — winners per round per region, plus finalFour and championship
- `finalFourMatchups` — which regions pair in the Final Four (auto-detected from ESPN data)

### Scoring

`points = seed × round_multiplier`

| Round | Multiplier |
|-------|-----------|
| Round of 64 | 1 |
| Round of 32 | 2 |
| Sweet 16 | 3 |
| Elite 8 | 4 |
| Final Four | 5 |
| Championship | 6 |

### Results Array Indexing

Each region's `round1` array has 8 slots matching bracket order:
- `[0]`: 1v16 winner, `[1]`: 8v9, `[2]`: 5v12, `[3]`: 4v13, `[4]`: 6v11, `[5]`: 3v14, `[6]`: 7v10, `[7]`: 2v15

Later rounds feed forward: `round2[0]` = winner of `round1[0]` vs `round1[1]`, etc.

## ESPN API Endpoints

- Scoreboard: `site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates=YYYYMMDD&groups=100`
- Teams directory: `site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams?limit=500`
- Core events: `sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/seasons/{year}/types/3/events`
- WADL docs: `sports.core.api.espn.com/v2/application.wadl`, `sports.core.api.espn.com/v3/application.wadl`

## Context Index

- **espn-api** — Comprehensive reference for ESPN's undocumented APIs: endpoints, response structures, gotchas, filtering strategies, and logo CDN
