/* ── App Core: data loading, scoring, tabs, leaderboard ── */

// Standard bracket seed order (top-to-bottom in each region)
// Matchups: 1v16, 8v9, 5v12, 4v13, 6v11, 3v14, 7v10, 2v15
const BRACKET_ORDER = [1, 16, 8, 9, 5, 12, 4, 13, 6, 11, 3, 14, 7, 10, 2, 15];

const ROUND_NAMES = ['round1', 'round2', 'sweet16', 'elite8'];
const ROUND_LABELS = {
  round1: 'Round of 64',
  round2: 'Round of 32',
  sweet16: 'Sweet 16',
  elite8: 'Elite 8',
  finalFour: 'Final Four',
  championship: 'Championship',
};
const ROUND_MULTIPLIER = {
  round1: 1,
  round2: 2,
  sweet16: 3,
  elite8: 4,
  finalFour: 5,
  championship: 6,
};

let DATA = null;
let CURRENT_YEAR = null;

async function loadYears() {
  try {
    const resp = await fetch('data/years.json');
    const years = await resp.json();
    return years.sort((a, b) => b - a); // newest first
  } catch (err) {
    console.warn('Failed to load years.json:', err);
    return [2026];
  }
}

function initYearSelect(years) {
  const select = document.getElementById('year-select');
  select.innerHTML = years.map(y =>
    `<option value="${y}" ${y === CURRENT_YEAR ? 'selected' : ''}>${y}</option>`
  ).join('');
  select.addEventListener('change', () => {
    const url = new URL(window.location);
    url.searchParams.set('year', select.value);
    window.location = url;
  });
}

async function loadData() {
  const years = await loadYears();
  const paramYear = new URLSearchParams(window.location.search).get('year');
  CURRENT_YEAR = paramYear ? parseInt(paramYear, 10) : years[0];
  initYearSelect(years);

  const resp = await fetch(`data/${CURRENT_YEAR}.json`);
  DATA = await resp.json();
  document.getElementById('title').textContent = DATA.title;
  document.title = DATA.title;
}

/* ── Scoring ── */

function getTeamByName(name) {
  for (const region of Object.values(DATA.regions)) {
    const team = region.find(t => t.name === name);
    if (team) return team;
  }
  return null;
}

function buildOwnerMap() {
  // Map team name → owner name
  const map = {};
  for (const teams of Object.values(DATA.regions)) {
    for (const t of teams) {
      if (t.owner) map[t.name] = t.owner;
    }
  }
  return map;
}

function computeTeamWins(teamName) {
  // Returns array of round names this team has won
  const wins = [];
  const results = DATA.results;

  for (const regionName of Object.keys(DATA.regions)) {
    const regionResults = results[regionName];
    if (!regionResults) continue;

    for (const roundName of ROUND_NAMES) {
      const roundResults = regionResults[roundName];
      if (!roundResults) continue;
      if (roundResults.includes(teamName)) {
        wins.push(roundName);
      }
    }
  }

  // Check Final Four and Championship
  if (results.finalFour && results.finalFour.includes(teamName)) {
    wins.push('finalFour');
  }
  if (results.championship && results.championship.includes(teamName)) {
    wins.push('championship');
  }

  return wins;
}

function isTeamEliminated(teamName) {
  // A team is eliminated if they appear as a competitor in a round
  // where they didn't win. We check by finding their region and
  // tracing through the bracket.
  let team = null;
  let regionName = null;

  for (const [rn, teams] of Object.entries(DATA.regions)) {
    const found = teams.find(t => t.name === teamName);
    if (found) { team = found; regionName = rn; break; }
  }
  if (!team || !regionName) return false;

  const regionResults = DATA.results[regionName];
  if (!regionResults) return false;
  const bracketIdx = BRACKET_ORDER.indexOf(team.seed);
  if (bracketIdx === -1) return false;

  // Trace through rounds
  let matchIdx = Math.floor(bracketIdx / 2);
  for (const roundName of ROUND_NAMES) {
    const result = regionResults[roundName][matchIdx];
    if (result === null) return false; // game not played yet
    if (result !== teamName) return true; // lost this round
    matchIdx = Math.floor(matchIdx / 2);
  }

  // Check Final Four
  const ffMatchups = DATA.finalFourMatchups;
  const ffIdx = ffMatchups.findIndex(pair => pair.includes(regionName));
  if (ffIdx !== -1) {
    const ffResult = DATA.results.finalFour[ffIdx];
    if (ffResult === null) return false;
    if (ffResult !== teamName) return true;

    const champResult = DATA.results.championship[0];
    if (champResult === null) return false;
    if (champResult !== teamName) return true;
  }

  return false;
}

function computeScores() {
  // Returns [{name, color, score, teams: [{name, seed, region, wins, points, eliminated}]}]
  const ownerMap = buildOwnerMap();
  const players = DATA.players.map(p => ({
    name: p.name,
    color: p.color,
    score: 0,
    teams: [],
  }));

  const playerIdx = {};
  players.forEach((p, i) => playerIdx[p.name] = i);

  for (const [regionName, teams] of Object.entries(DATA.regions)) {
    for (const team of teams) {
      if (!team.owner) continue;
      const idx = playerIdx[team.owner];
      if (idx === undefined) continue;

      const wins = computeTeamWins(team.name);
      let points = 0;
      for (const roundName of wins) {
        points += team.seed * ROUND_MULTIPLIER[roundName];
      }

      players[idx].teams.push({
        name: team.name,
        seed: team.seed,
        region: regionName,
        wins,
        points,
        eliminated: isTeamEliminated(team.name),
      });
      players[idx].score += points;
    }
  }

  // Sort teams within each player by seed
  for (const p of players) {
    p.teams.sort((a, b) => a.seed - b.seed);
  }

  // Sort players by score descending
  players.sort((a, b) => b.score - a.score);
  return players;
}

/* ── Leaderboard ── */

function renderLeaderboard(scores) {
  const el = document.getElementById('leaderboard');
  el.innerHTML = scores.map((p, i) => `
    <div class="lb-card" data-player="${escapeHtml(p.name)}" style="background:${hexToRgba(p.color, 0.15)};border:2px solid ${p.color}">
      <span class="lb-rank">#${i + 1}</span>
      <span class="lb-pip" style="background:${p.color}"></span>
      <span class="lb-name">${escapeHtml(p.name)}</span>
      <span class="lb-score">${p.score}</span>
    </div>
  `).join('');

  el.querySelectorAll('.lb-card').forEach(card => {
    card.addEventListener('click', () => {
      const name = card.dataset.player;
      const player = scores.find(p => p.name === name);
      if (player) showScoreBreakdown(player);
    });
  });
}

/* ── Score Breakdown Modal ── */

const ROUND_SHORT = {
  round1: 'R64', round2: 'R32', sweet16: 'S16',
  elite8: 'E8', finalFour: 'F4', championship: 'CH',
};
const ALL_ROUNDS = ['round1', 'round2', 'sweet16', 'elite8', 'finalFour', 'championship'];

function hasRoundStarted(roundName) {
  // A round has started if any result exists for it anywhere
  if (roundName === 'finalFour') {
    return DATA.results.finalFour.some(v => v !== null);
  }
  if (roundName === 'championship') {
    return DATA.results.championship.some(v => v !== null);
  }
  for (const region of Object.keys(DATA.regions)) {
    const rr = DATA.results[region]?.[roundName];
    if (rr && rr.some(v => v !== null)) return true;
  }
  return false;
}

function showScoreBreakdown(player) {
  const modal = document.getElementById('score-modal');
  const breakdown = document.getElementById('score-breakdown');

  // Figure out which rounds have started (to show columns)
  const activeRounds = ALL_ROUNDS.filter(r => hasRoundStarted(r));

  const headerCols = activeRounds.map(r => `<th>${ROUND_SHORT[r]}</th>`).join('');

  const rows = player.teams.map(t => {
    const status = t.eliminated ? 'eliminated' : (t.wins.length > 0 ? 'active' : 'pending');
    const roundCells = activeRounds.map(r => {
      const pts = t.wins.includes(r) ? t.seed * ROUND_MULTIPLIER[r] : 0;
      return `<td class="round-pts">${pts}</td>`;
    }).join('');

    return `<tr class="${status}">
      <td><span class="seed">${t.seed}</span> ${escapeHtml(t.name)}</td>
      ${roundCells}
      <td class="pts-total">${t.points}</td>
    </tr>`;
  }).join('');

  breakdown.innerHTML = `
    <h3 style="color:${player.color}">${escapeHtml(player.name)}</h3>
    <table class="breakdown-table">
      <thead><tr><th>Team</th>${headerCols}<th>Tot</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <div class="breakdown-total">Total: ${player.score} pts</div>
  `;

  modal.classList.remove('hidden');
}

/* ── Tab Switching ── */

function initTabs() {
  document.querySelectorAll('#main-nav .tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('#main-nav .tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');

      const target = tab.dataset.tab;
      document.getElementById('bracket-view').classList.toggle('hidden', target !== 'bracket');
      document.getElementById('roster-view').classList.toggle('hidden', target !== 'roster');
    });
  });
}

/* ── Init ── */

async function init() {
  await loadData();
  initTabs();

  // Initial render with static data
  let scores = computeScores();
  renderLeaderboard(scores);
  renderBracket();
  renderRoster(scores);

  // Fetch ESPN live data and re-render if results changed
  const { updated } = await refreshLiveData();
  if (updated) {
    scores = computeScores();
    renderLeaderboard(scores);
    renderBracket();
    renderRoster(scores);
  }

  // Auto-refresh every 60 seconds during live games
  setInterval(async () => {
    const { updated } = await refreshLiveData();
    if (updated) {
      const scores = computeScores();
      renderLeaderboard(scores);
      renderBracket();
      renderRoster(scores);
    }
  }, 60_000);
}

document.addEventListener('DOMContentLoaded', init);

// Close modal
document.addEventListener('click', (e) => {
  const modal = document.getElementById('score-modal');
  if (e.target.classList.contains('modal-backdrop') || e.target.classList.contains('modal-close')) {
    modal.classList.add('hidden');
  }
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.getElementById('score-modal').classList.add('hidden');
  }
});
