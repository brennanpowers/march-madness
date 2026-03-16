# March Madness Pool

A static website for running a family NCAA tournament draft pool. 8 players snake-draft all 64 teams (8 each), then watch points accumulate as their teams win through the bracket. Hosted on GitHub Pages at [marchmadness.brennanpowers.com](https://marchmadness.brennanpowers.com).

[Bracket View Screenshot]

[Roster View Screenshot]

[Leaderboard Screenshot]

## How It Works

- **No backend.** The site is pure HTML/CSS/JS served from GitHub Pages.
- **Data-driven.** Each year's tournament lives in a single JSON file (`data/<year>.json`) containing teams, seeds, regions, draft assignments, results, and schedule.
- **Live scores from ESPN.** On page load, the client fetches ESPN's undocumented scoreboard API for each tournament game date. Finished game results are overlaid onto the bracket automatically. During live games, the page refreshes every 60 seconds.
- **Deploy by pushing to `main`.** The CNAME file routes `marchmadness.brennanpowers.com` to GitHub Pages.

## Pool Rules

- 8 players, snake draft, 8 teams each (all 64 tournament teams are drafted)
- No restrictions on which teams you can pick at any slot
- First Four play-in teams: you draft the seed slot (both teams), and whichever team wins goes to your roster
- **Scoring:** `seed x round_multiplier` -- a 12-seed winning in the Round of 64 earns 12 points; winning in the Round of 32 earns 24 points
- Drafting the eventual champion also earns a piece of the pot

### Scoring Table

| Round | Multiplier | Example (12-seed) |
|-------|------------|-------------------|
| Round of 64 | 1 | 12 pts |
| Round of 32 | 2 | 24 pts |
| Sweet 16 | 3 | 36 pts |
| Elite 8 | 4 | 48 pts |
| Final Four | 5 | 60 pts |
| Championship | 6 | 72 pts |

## Quick Start

### 1. Set up a new year

```bash
python3 scripts/setup-year.py 2027
```

This single command:
- Fetches the full tournament bracket from ESPN's API (teams, seeds, regions, schedule)
- Downloads all 68 team logos to `img/logos/`
- Backfills results for any completed games (useful for adding past years)
- Adds the year to `data/years.json`

Output: `data/2027.json` ready for draft assignment.

### 2. Run the draft

1. Open `admin.html` in a browser
2. Enter the password (`marchmadness`)
3. Edit player names and colors in the **Players** section
4. Assign teams in the **Draft Roster** section (dropdown per team, or typeahead search in the Players section)
5. Set the **Final Four Matchups** (which regions play each other in the semifinals)
6. Click **Generate JSON**, then **Download .json**
7. Replace `data/2027.json` with the downloaded file

### 3. Deploy

```bash
git add data/2027.json data/years.json img/logos/
git commit -m "Add 2027 tournament"
git push
```

The site is live at `marchmadness.brennanpowers.com` within a minute or two.

## Project Structure

```
marchmadness/
├── index.html              # Main site -- bracket + roster tabs, leaderboard, score modal
├── admin.html              # Password-gated admin page for draft assignment
├── CNAME                   # GitHub Pages custom domain config
├── css/
│   └── style.css           # Light theme, responsive, mobile-first
├── js/
│   ├── espn.js             # ESPN live integration, logo URLs, shared utilities
│   ├── app.js              # Data loading, scoring engine, leaderboard, tabs
│   ├── bracket.js          # Region bracket rendering with logos and connectors
│   └── roster.js           # Player roster cards with team lists
├── data/
│   ├── years.json                  # Array of available years (drives the year dropdown)
│   ├── years.schema.json           # JSON Schema for years.json
│   ├── tournament-year.schema.json # JSON Schema for <year>.json files
│   ├── 2026.json                   # Current year tournament data
│   ├── 2025.json                   # Historical data
│   └── 2024.json                   # Historical data
├── img/
│   └── logos/              # Cached team logo PNGs ({espnId}.png)
├── scripts/
│   ├── setup-year.py       # One-stop setup: bracket + logos + results + years manifest
│   └── generate_bracket.py # Core bracket generator (ESPN API -> tournament JSON)
├── tests/
│   ├── test-data-integrity.py  # Validates all year JSON files against schemas
│   ├── test-setup-script.py    # Unit tests for setup script
│   └── test-scoring.html       # Browser-based scoring engine tests
├── requirements-dev.txt        # Python dev dependencies (jsonschema)
└── docs/
    ├── espn-core-v2.wadl       # ESPN API endpoint documentation (machine-readable)
    └── espn-core-v3.wadl
```

### Script load order (in index.html)

`espn.js` -> `app.js` -> `bracket.js` -> `roster.js`

`espn.js` must load first because it defines `hexToRgba()` and `teamLogoUrl()` used by all other scripts.

## ESPN Integration

The site uses two of ESPN's undocumented, unauthenticated public APIs. No API key required. CORS headers are present for client-side use.

### Setup time (Python scripts, one-time per year)

The `setup-year.py` script uses the **Core API** (`sports.core.api.espn.com/v2`) to build the bracket:

1. Fetches the team directory (ID -> name/abbreviation lookup)
2. Fetches all postseason events from the Core API (~100-120 events, paginated)
3. Filters to NCAA tournament games by headline pattern
4. Extracts teams, seeds, regions, and game schedule
5. Backfills results for completed games using the `winner` boolean
6. Downloads team logos from ESPN's CDN (`cdn.espn.com/i/teamlogos/ncaa/500/{espnId}.png`)

Total: ~130 API requests, takes about 15 seconds with concurrency.

### Runtime (client-side, every page load)

The client uses the **Site API** (`site.api.espn.com`) for live score updates:

1. Reads the `gameDates` array from the year's JSON (only dates the tournament actually runs)
2. Filters to dates up to today
3. Fetches the scoreboard for each date in parallel (`?dates=YYYYMMDD&groups=100&limit=100`)
4. Matches teams by ESPN ID to the bracket data
5. Overlays finished game results where the JSON has `null`
6. Auto-refreshes every 60 seconds during live games (fetches only today's date after initial load)

If ESPN is unavailable, the site still works -- it just shows whatever results are already in the JSON file.

### Logos

Logos are cached locally at `img/logos/{espnId}.png` with a CDN fallback URL. The setup script downloads all 68 logos (~20-35 KB each) during year setup.

## Admin Page

The admin page (`admin.html`) is a client-side tool for managing draft rosters. It's password-gated with the password `marchmadness` (stored in localStorage -- this is a family pool, not Fort Knox).

### Sections

- **Players**: Edit names and colors. Typeahead search to assign teams directly to a player. Clear individual or all rosters.
- **Draft Roster**: Grid of all 64 teams organized by region, each with an owner dropdown. Shows draft counts per player (target: 8 each).
- **Final Four Matchups**: Set which two regions play each other in each semifinal. Auto-detected for completed years, must be set manually for the current year.
- **Export JSON**: Generate, preview, copy, or download the complete year JSON. This is what gets committed to `data/<year>.json`.

### Snapshots

The admin page supports saving/loading snapshots to localStorage. Useful during a live draft to save progress or try different assignments.

## Adding Historical Years

The setup script handles past years automatically:

```bash
python3 scripts/setup-year.py 2024
```

For a completed tournament, the script backfills all results from ESPN's API, so the bracket renders fully populated. The Final Four matchup pairings are auto-detected from completed game data.

Years appear in the site's dropdown in reverse chronological order, driven by `data/years.json`.

## Data Model

Each year's JSON (`data/<year>.json`) contains:

| Key | Description |
|-----|-------------|
| `year`, `title` | Metadata |
| `gameDates[]` | `YYYYMMDD` strings for every tournament game date |
| `players[]` | Name + color for each pool participant |
| `regions{}` | 4 regions, each with 16 teams (`seed`, `name`, `espnId`, `abbrev`, `owner`, `firstFour`) |
| `firstFour[]` | First Four play-in game details with ESPN IDs |
| `results{}` | Winners per round per region, plus `finalFour` and `championship` |
| `schedule{}` | ISO datetimes per game slot (mirrors `results` structure) |
| `finalFourMatchups` | Which regions pair in the Final Four semifinals |

Results use `null` for unplayed games. The client fills these in at runtime from ESPN data.

Formal JSON Schema definitions live alongside the data files: `data/tournament-year.schema.json` and `data/years.schema.json`. The integrity test (`tests/test-data-integrity.py`) validates all data files against these schemas.

## Tech Stack

- **HTML/CSS/JS** -- no build step, no framework, no dependencies
- **Python 3** -- setup scripts (standard library only) and test tooling (`pip install -r requirements-dev.txt`)
- **ESPN undocumented APIs** -- Core API for bracket building, Site API for live scores
- **GitHub Pages** -- hosting and deployment
- **Custom domain** -- `marchmadness.brennanpowers.com` via CNAME

## DNS / Deployment

The site is hosted on GitHub Pages with a custom subdomain.

### GitHub Pages setup

1. In the repo settings, GitHub Pages is configured to deploy from the `main` branch root
2. The `CNAME` file in the repo root contains `marchmadness.brennanpowers.com`

### DNS setup

Add a CNAME record with your DNS provider:

```
marchmadness.brennanpowers.com  CNAME  brennanpowers.github.io
```

GitHub handles HTTPS automatically via Let's Encrypt once the CNAME is verified.

### Deploying updates

Push to `main`. GitHub Pages rebuilds within 1-2 minutes. No build step or CI/CD needed -- the repo root is served directly.

```bash
git push origin main
```

During the tournament, the only changes that need deploying are:
- Initial draft roster (`data/<year>.json` with owners assigned)
- Manual result corrections (rare -- ESPN live data handles this automatically)
