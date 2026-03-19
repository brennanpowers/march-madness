/* ── Shared Utilities ── */

// Cache-busting: per-minute timestamp so browsers never serve stale JSON
function cacheBust(url) {
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}_=${Math.floor(Date.now() / 60000)}`;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

/* ── ESPN Live Data Integration ── */

const ESPN_SCOREBOARD = 'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard';
const ESPN_LOGO_CDN = 'https://cdn.espn.com/i/teamlogos/ncaa/500';

function teamLogoUrl(espnId) {
  if (!espnId) return null;
  // Use local cached logos first, fall back to ESPN CDN via onerror in HTML
  return `img/logos/${espnId}.png`;
}

function teamLogoCdnUrl(espnId) {
  if (!espnId) return null;
  return `${ESPN_LOGO_CDN}/${espnId}.png`;
}

// Build a lookup: espnId → team data from our JSON
function buildEspnIdMap() {
  const map = {};
  for (const [regionName, teams] of Object.entries(DATA.regions)) {
    for (const t of teams) {
      if (t.espnId) {
        map[t.espnId] = { ...t, region: regionName };
      }
    }
  }
  // Also index First Four teams
  for (const ff of (DATA.firstFour || [])) {
    if (ff.team1EspnId) map[ff.team1EspnId] = { name: ff.team1, espnId: ff.team1EspnId, region: ff.region, seed: ff.seed };
    if (ff.team2EspnId) map[ff.team2EspnId] = { name: ff.team2, espnId: ff.team2EspnId, region: ff.region, seed: ff.seed };
  }
  return map;
}

async function fetchEspnScoreboard(date) {
  const dateStr = date || getTodayStr();
  const url = `${ESPN_SCOREBOARD}?dates=${dateStr}&groups=100&limit=100`;
  try {
    const resp = await fetch(url);
    if (!resp.ok) return null;
    return await resp.json();
  } catch (err) {
    console.warn('ESPN scoreboard fetch failed:', err);
    return null;
  }
}

function getTodayStr() {
  const d = new Date();
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
}

function parseEspnGames(scoreboard) {
  if (!scoreboard || !scoreboard.events) return [];
  const espnMap = buildEspnIdMap();

  return scoreboard.events.map(event => {
    const comp = event.competitions?.[0];
    if (!comp) return null;

    const status = comp.status?.type?.name; // STATUS_SCHEDULED, STATUS_IN_PROGRESS, STATUS_FINAL
    const clock = comp.status?.displayClock;
    const period = comp.status?.period;

    const teams = comp.competitors?.map(c => {
      const id = c.team?.id || c.id;
      const ourTeam = espnMap[String(id)];
      return {
        espnId: String(id),
        name: c.team?.displayName || c.team?.location || ourTeam?.name || 'Unknown',
        shortName: c.team?.location || ourTeam?.name || c.team?.displayName || 'Unknown',
        score: parseInt(c.score, 10) || 0,
        seed: c.curatedRank?.current,
        ourTeam,
      };
    }) || [];

    let region = null;
    let round = null;
    for (const note of (comp.notes || [])) {
      const h = note.headline || '';
      for (const r of ['South', 'East', 'Midwest', 'West']) {
        if (h.includes(r)) { region = r; break; }
      }
      if (h.includes('First Four')) round = 'firstFour';
      else if (h.includes('1st Round')) round = 'round1';
      else if (h.includes('2nd Round')) round = 'round2';
      else if (h.includes('Sweet 16') || h.includes('Regional Semifinal')) round = 'sweet16';
      else if (h.includes('Elite Eight') || h.includes('Regional Final') || h.includes('Elite 8')) round = 'elite8';
      else if (h.includes('Final Four') || h.includes('National Semifinal')) round = 'finalFour';
      else if (h.includes('Championship') || h.includes('National Championship')) round = 'championship';
    }

    return {
      id: event.id,
      status,
      clock,
      period,
      teams,
      region,
      round,
      isFinal: status === 'STATUS_FINAL',
      isLive: status === 'STATUS_IN_PROGRESS' || status === 'STATUS_HALFTIME' || status === 'STATUS_END_PERIOD',
    };
  }).filter(Boolean);
}

function applyEspnResults(games) {
  // Apply finished game results to DATA
  // Only updates results that are currently null (doesn't override manual entries)
  let updated = false;

  for (const game of games) {
    if (!game.isFinal) continue;
    // Regional rounds need a region; FF/Championship don't
    if (!game.region && game.round !== 'finalFour' && game.round !== 'championship') continue;

    // Find the winner (higher score)
    const sorted = [...game.teams].sort((a, b) => b.score - a.score);
    const winnerEspnId = sorted[0]?.espnId;
    const winnerTeam = sorted[0]?.ourTeam;
    if (!winnerTeam) continue;

    if (game.round === 'firstFour') {
      // Update First Four winner
      const ff = DATA.firstFour?.find(f =>
        f.region === game.region && f.seed === winnerTeam.seed
      );
      if (ff && !ff.winner) {
        ff.winner = winnerTeam.name;
        // Update region team entry
        const regionTeam = DATA.regions[game.region]?.find(
          t => t.seed === ff.seed && t.firstFour
        );
        if (regionTeam) {
          regionTeam.name = winnerTeam.name;
          regionTeam.espnId = winnerEspnId;
          regionTeam.abbrev = winnerTeam.abbrev || regionTeam.abbrev;
        }
        updated = true;
      }
      continue;
    }

    // Regional rounds
    if (game.round && DATA.results[game.region]) {
      const roundResults = DATA.results[game.region][game.round];
      if (!roundResults) continue;

      // Find the correct slot by matching team seeds/names
      const slotIdx = findResultSlot(game, winnerTeam.name);
      if (slotIdx !== -1 && roundResults[slotIdx] === null) {
        roundResults[slotIdx] = winnerTeam.name;
        updated = true;
      }
    }

    // Final Four
    if (game.round === 'finalFour') {
      const ffMatchups = DATA.finalFourMatchups;
      for (let i = 0; i < ffMatchups.length; i++) {
        const pair = ffMatchups[i];
        if (game.teams.some(t => t.ourTeam?.region && pair.includes(t.ourTeam.region))) {
          if (DATA.results.finalFour[i] === null) {
            DATA.results.finalFour[i] = winnerTeam.name;
            updated = true;
          }
          break;
        }
      }
    }

    // Championship
    if (game.round === 'championship') {
      if (DATA.results.championship[0] === null) {
        DATA.results.championship[0] = winnerTeam.name;
        updated = true;
      }
    }
  }

  return updated;
}

function findResultSlot(game, winnerName) {
  // Determine which index in the round's result array this game maps to
  const region = game.region;
  const round = game.round;
  if (!region || !round || !DATA.results[region]) return -1;

  const regionTeams = DATA.regions[region];
  const teamsBySeed = {};
  regionTeams.forEach(t => teamsBySeed[t.seed] = t);
  const ordered = BRACKET_ORDER.map(s => teamsBySeed[s]);

  if (round === 'round1') {
    // Match by seeds: find which matchup pair contains both game teams
    for (let i = 0; i < 8; i++) {
      const top = ordered[i * 2];
      const bot = ordered[i * 2 + 1];
      const gameTeamNames = game.teams.map(t => t.ourTeam?.name).filter(Boolean);
      if (gameTeamNames.includes(top?.name) || gameTeamNames.includes(bot?.name)) {
        return i;
      }
    }
  } else {
    // For later rounds, find slot where the winner would feed into
    // by checking existing results
    const prevRound = ROUND_NAMES[ROUND_NAMES.indexOf(round) - 1];
    if (!prevRound) return -1;
    const prevResults = DATA.results[region][prevRound];
    const roundResults = DATA.results[region][round];

    for (let i = 0; i < roundResults.length; i++) {
      const feeder1 = prevResults[i * 2];
      const feeder2 = prevResults[i * 2 + 1];
      const gameTeamNames = game.teams.map(t => t.ourTeam?.name).filter(Boolean);
      if (gameTeamNames.includes(feeder1) || gameTeamNames.includes(feeder2)) {
        return i;
      }
    }
  }

  return -1;
}

// Store live game data for display (scores, clock, etc.)
let LIVE_GAMES = [];

function isTournamentActive() {
  // Only fetch ESPN data if today falls within the tournament's date range
  const dates = DATA.gameDates || [];
  if (!dates.length) return false;
  const today = getTodayStr();
  const firstDate = dates[0];
  const lastDate = dates[dates.length - 1];
  // Add 1 real day to last date for the post-final window
  const last = new Date(`${lastDate.slice(0,4)}-${lastDate.slice(4,6)}-${lastDate.slice(6,8)}`);
  last.setDate(last.getDate() + 1);
  const dayAfter = `${last.getFullYear()}${String(last.getMonth()+1).padStart(2,'0')}${String(last.getDate()).padStart(2,'0')}`;
  return today >= firstDate && today <= dayAfter;
}

function getTournamentDates() {
  const today = getTodayStr();
  const allDates = DATA.gameDates || [];
  return allDates.filter(d => d <= today);
}

let _fullHistoryLoaded = false;

function hasNullResults() {
  // Check if any result slot is still null (needs backfilling)
  const r = DATA.results;
  for (const region of Object.keys(DATA.regions)) {
    const rr = r[region];
    if (!rr) continue;
    for (const round of Object.values(rr)) {
      if (round.some(v => v === null)) return true;
    }
  }
  if (r.finalFour?.some(v => v === null)) return true;
  if (r.championship?.some(v => v === null)) return true;
  return false;
}

async function refreshLiveData() {
  if (!isTournamentActive()) return { games: [], updated: false };

  if (!_fullHistoryLoaded) {
    // Only backfill past dates if there are null results to fill
    if (hasNullResults()) {
      const today = getTodayStr();
      const pastDates = getTournamentDates().filter(d => d < today);
      if (pastDates.length) {
        const scoreboards = await Promise.all(
          pastDates.map(date => fetchEspnScoreboard(date))
        );
        const allGames = scoreboards.flatMap(sb => parseEspnGames(sb));
        applyEspnResults(allGames);
      }
    }
    _fullHistoryLoaded = true;
  }

  // LIVE_GAMES only holds today's games
  const todayData = await fetchEspnScoreboard(getTodayStr());
  LIVE_GAMES = parseEspnGames(todayData);
  const updated = applyEspnResults(LIVE_GAMES);
  return { games: LIVE_GAMES, updated: LIVE_GAMES.length > 0 || updated };
}

function getLiveGame(espnId) {
  // LIVE_GAMES only contains today's games
  for (const game of LIVE_GAMES) {
    if (game.teams.some(t => t.espnId === espnId)) {
      return game;
    }
  }
  return null;
}

function getTeamScore(game, espnId) {
  if (!game) return null;
  const t = game.teams.find(t => t.espnId === espnId);
  return t ? t.score : null;
}

// Look up a static score from DATA.gameScores (populated by setup script)
function getStaticScore(teamName, roundName) {
  return DATA.gameScores?.[teamName]?.[roundName] ?? null;
}

function otLabel(period) {
  if (period <= 2) return '';
  if (period === 3) return 'OT';
  return `${period - 2}OT`;
}

function getGameStatusText(game) {
  if (!game) return '';
  if (game.isFinal) {
    return game.period > 2 ? `Final/${otLabel(game.period)}` : 'Final';
  }
  if (game.isLive) {
    if (game.status === 'STATUS_HALFTIME') return 'Half';
    const half = game.period === 1 ? '1H' : game.period === 2 ? '2H' : otLabel(game.period);
    return half && game.clock ? `${half} ${game.clock}` : 'LIVE';
  }
  return '';
}
