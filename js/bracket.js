/* ── Bracket Rendering ── */

let _activeRegionTab = sessionStorage.getItem('activeRegionTab');

function renderBracket() {
  const regionNames = Object.keys(DATA.regions);
  const allTabs = [...regionNames, 'Final Four'];
  const activeTab = _activeRegionTab && allTabs.includes(_activeRegionTab) ? _activeRegionTab : regionNames[0];

  const tabs = document.getElementById('region-tabs');
  tabs.innerHTML = allTabs.map(name => `
    <button class="region-tab ${name === activeTab ? 'active' : ''}" data-region="${name}">${name}</button>
  `).join('');

  tabs.querySelectorAll('.region-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.querySelectorAll('.region-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      _activeRegionTab = tab.dataset.region;
      sessionStorage.setItem('activeRegionTab', _activeRegionTab);
      showRegion(tab.dataset.region);
    });
  });

  showRegion(activeTab);
}

function showRegion(regionName) {
  const container = document.getElementById('bracket-container');
  if (regionName === 'Final Four') {
    container.innerHTML = '';
    container.appendChild(buildFinalFour());
  } else {
    container.innerHTML = '';
    container.appendChild(buildRegionBracket(regionName));
  }
}

function buildRegionBracket(regionName) {
  const teams = DATA.regions[regionName];
  const results = DATA.results[regionName];
  const teamsBySeed = {};
  teams.forEach(t => teamsBySeed[t.seed] = t);

  // Build bracket-ordered team list
  const ordered = BRACKET_ORDER.map(s => teamsBySeed[s]);

  const wrapper = document.createElement('div');
  wrapper.className = 'bracket-region';
  wrapper.style.paddingTop = '24px';

  let currentTeams = ordered;

  ROUND_NAMES.forEach((roundName, roundIdx) => {
    const roundResults = results[roundName];
    const roundEl = document.createElement('div');
    roundEl.className = 'round';

    const label = document.createElement('div');
    label.className = 'round-label';
    label.textContent = ROUND_LABELS[roundName];
    roundEl.appendChild(label);

    // Create matchups from pairs of current teams
    const nextTeams = [];
    for (let i = 0; i < currentTeams.length; i += 2) {
      const top = currentTeams[i];
      const bot = currentTeams[i + 1];
      const matchIdx = Math.floor(i / 2);
      const winner = roundResults[matchIdx];

      const matchup = document.createElement('div');
      matchup.className = 'matchup';
      matchup.appendChild(buildTeamSlot(top, winner, roundIdx === 0, roundName));
      matchup.appendChild(buildTeamSlot(bot, winner, roundIdx === 0, roundName));

      // Game time / live status — only match ESPN games for this specific round
      const topGame = top && top.espnId ? getLiveGame(String(top.espnId)) : null;
      const botGame = bot && bot.espnId ? getLiveGame(String(bot.espnId)) : null;
      const matchGame = (topGame && topGame.round === roundName) ? topGame
                       : (botGame && botGame.round === roundName) ? botGame
                       : null;
      if (matchGame && (matchGame.isLive || matchGame.isFinal)) {
        if (matchGame.isLive) matchup.classList.add('live');
        const timeEl = document.createElement('div');
        timeEl.className = 'matchup-time' + (matchGame.isLive ? ' live' : '');
        timeEl.textContent = getGameStatusText(matchGame);
        matchup.appendChild(timeEl);
      } else {
        const schedule = DATA.schedule?.[regionName]?.[roundName];
        const gameDate = schedule?.[matchIdx];
        if (gameDate) {
          const timeEl = document.createElement('div');
          timeEl.className = 'matchup-time';
          timeEl.textContent = formatGameTime(gameDate, !!winner);
          matchup.appendChild(timeEl);
        }
      }

      roundEl.appendChild(matchup);

      // Feed winner into next round
      if (winner) {
        const winnerTeam = teams.find(t => t.name === winner);
        nextTeams.push(winnerTeam || { seed: '?', name: winner, owner: null, firstFour: false });
      } else {
        nextTeams.push(null);
      }
    }

    wrapper.appendChild(roundEl);

    // Add connector column between rounds (except after last round)
    if (roundIdx < ROUND_NAMES.length - 1) {
      const connCol = document.createElement('div');
      connCol.className = 'connector-col';
      for (let i = 0; i < currentTeams.length / 2; i += 2) {
        const conn = document.createElement('div');
        conn.className = 'connector';
        connCol.appendChild(conn);
      }
      wrapper.appendChild(connCol);
    }

    currentTeams = nextTeams;
  });

  return wrapper;
}

function buildTeamSlot(team, winner, showSeed, roundName) {
  const el = document.createElement('div');
  el.className = 'team-slot';

  if (!team) {
    el.classList.add('empty');
    el.innerHTML = '<span class="team-name">TBD</span>';
    return el;
  }

  const isWinner = winner && team.name === winner;
  const isLoser = winner && team.name !== winner;
  const playerColor = team.owner ? getPlayerColor(team.owner) : null;

  if (isWinner) el.classList.add('winner');
  if (isLoser) el.classList.add('loser');

  // Apply player color as background tint
  if (playerColor) {
    if (isLoser) {
      // Greyed-out: very faint color with desaturation
      el.style.background = hexToRgba(playerColor, 0.08);
      el.style.borderColor = hexToRgba(playerColor, 0.15);
    } else if (isWinner) {
      // Bold/loud: strong color tint
      el.style.background = hexToRgba(playerColor, 0.2);
      el.style.borderColor = playerColor;
      el.style.borderWidth = '2px';
    } else {
      // Pending: light tint
      el.style.background = hexToRgba(playerColor, 0.1);
      el.style.borderColor = hexToRgba(playerColor, 0.25);
    }
  }

  const logoUrl = teamLogoUrl(team.espnId);
  const cdnUrl = teamLogoCdnUrl(team.espnId);
  const logoImg = logoUrl
    ? `<img class="team-logo" src="${escapeHtml(logoUrl)}" alt="" width="18" height="18" loading="lazy" onerror="if(this.src!=='${escapeHtml(cdnUrl)}')this.src='${escapeHtml(cdnUrl)}';else this.style.display='none'">`
    : '';
  const seedSpan = `<span class="seed">${team.seed}</span>`;
  const nameSpan = `<span class="team-name">${escapeHtml(team.name)}</span>`;
  const ownerSpan = team.owner
    ? `<span class="owner-tag" style="background:${playerColor};color:#fff">${escapeHtml(team.owner)}</span>`
    : '';

  // Score: prefer static gameScores, fall back to ESPN live data for in-progress/final games
  const game = team.espnId ? getLiveGame(String(team.espnId)) : null;
  let score = roundName ? getStaticScore(team.name, roundName) : null;
  let isLive = false;
  if (score === null && game && (game.isLive || game.isFinal)) {
    if (game.round === roundName) {
      score = getTeamScore(game, String(team.espnId));
      isLive = game.isLive;
    }
  }
  const scoreSpan = score !== null
    ? `<span class="team-score${isLive ? ' live' : ''}">${score}</span>`
    : '';

  if (isLive) el.classList.add('live');

  el.innerHTML = logoImg + seedSpan + nameSpan + ownerSpan + scoreSpan;
  return el;
}


function formatGameTime(isoDate, isFinal) {
  if (!isoDate) return '';
  const d = new Date(isoDate);
  const month = d.toLocaleString('en-US', { month: 'short' });
  const day = d.getDate();
  if (isFinal) {
    return `${month} ${day} · Final`;
  }
  const time = d.toLocaleString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
  const now = new Date();
  // If the game is today, just show the time
  if (d.toDateString() === now.toDateString()) {
    return time;
  }
  return `${month} ${day} · ${time}`;
}

function getPlayerColor(ownerName) {
  const player = DATA.players.find(p => p.name === ownerName);
  return player ? player.color : '#8b949e';
}

function buildFFMatchupTime(team1, team2, roundName, slotIdx, matchupEl) {
  const g1 = team1 && team1.espnId ? getLiveGame(String(team1.espnId)) : null;
  const g2 = team2 && team2.espnId ? getLiveGame(String(team2.espnId)) : null;
  const game = (g1 && g1.round === roundName) ? g1
             : (g2 && g2.round === roundName) ? g2
             : null;
  const el = document.createElement('div');
  if (game && (game.isLive || game.isFinal)) {
    if (game.isLive && matchupEl) matchupEl.classList.add('live');
    el.className = 'matchup-time' + (game.isLive ? ' live' : '');
    el.textContent = getGameStatusText(game);
  } else {
    const schedule = roundName === 'championship' ? DATA.schedule?.championship : DATA.schedule?.finalFour;
    const gameDate = schedule?.[slotIdx];
    if (gameDate) {
      el.className = 'matchup-time';
      const winner = roundName === 'championship' ? DATA.results.championship[0]
                   : DATA.results.finalFour[slotIdx];
      el.textContent = formatGameTime(gameDate, !!winner);
    } else {
      return null;
    }
  }
  return el;
}

function buildFinalFour() {
  const wrapper = document.createElement('div');
  wrapper.className = 'final-four';

  const ffMatchups = DATA.finalFourMatchups;
  const ffResults = DATA.results.finalFour;
  const champResult = DATA.results.championship[0];

  // ── Left semifinal (matchup 0) ──
  const leftCol = document.createElement('div');
  leftCol.className = 'ff-col';

  const pair0 = ffMatchups[0];
  const left1Name = DATA.results[pair0[0]].elite8[0];
  const left2Name = DATA.results[pair0[1]].elite8[0];
  const left1 = left1Name ? getTeamByName(left1Name) : null;
  const left2 = left2Name ? getTeamByName(left2Name) : null;

  const leftLabel = document.createElement('div');
  leftLabel.className = 'ff-label';
  leftLabel.textContent = `${pair0[0]} vs ${pair0[1]}`;
  leftCol.appendChild(leftLabel);

  const leftMatchup = document.createElement('div');
  leftMatchup.className = 'matchup';
  leftMatchup.appendChild(buildTeamSlot(
    left1 || { seed: '?', name: `${pair0[0]} Champion`, owner: null, firstFour: false },
    ffResults[0], true, 'finalFour'
  ));
  leftMatchup.appendChild(buildTeamSlot(
    left2 || { seed: '?', name: `${pair0[1]} Champion`, owner: null, firstFour: false },
    ffResults[0], true, 'finalFour'
  ));
  const leftTime = buildFFMatchupTime(left1, left2, 'finalFour', 0, leftMatchup);
  if (leftTime) leftMatchup.appendChild(leftTime);
  leftCol.appendChild(leftMatchup);
  wrapper.appendChild(leftCol);

  // ── Connector ──
  const connLeft = document.createElement('div');
  connLeft.className = 'ff-connector';
  wrapper.appendChild(connLeft);

  // ── Center: Championship + Champion ──
  const centerCol = document.createElement('div');
  centerCol.className = 'ff-col ff-center';

  const champLabel = document.createElement('div');
  champLabel.className = 'championship-label';
  champLabel.textContent = 'Championship';
  centerCol.appendChild(champLabel);

  const semi1Winner = ffResults[0];
  const semi2Winner = ffResults[1];
  const champTeam1 = semi1Winner ? getTeamByName(semi1Winner) : null;
  const champTeam2 = semi2Winner ? getTeamByName(semi2Winner) : null;

  const champMatchup = document.createElement('div');
  champMatchup.className = 'matchup';
  champMatchup.appendChild(buildTeamSlot(
    champTeam1 || { seed: '?', name: 'Semifinal 1', owner: null, firstFour: false },
    champResult, true, 'championship'
  ));
  champMatchup.appendChild(buildTeamSlot(
    champTeam2 || { seed: '?', name: 'Semifinal 2', owner: null, firstFour: false },
    champResult, true, 'championship'
  ));
  const champTime = buildFFMatchupTime(champTeam1, champTeam2, 'championship', 0, champMatchup);
  if (champTime) champMatchup.appendChild(champTime);
  centerCol.appendChild(champMatchup);

  // Champion display
  if (champResult) {
    const champTeam = getTeamByName(champResult);
    const logoUrl = champTeam ? teamLogoUrl(champTeam.espnId) : null;
    const cdnUrl = champTeam ? teamLogoCdnUrl(champTeam.espnId) : null;
    const playerColor = champTeam && champTeam.owner ? getPlayerColor(champTeam.owner) : null;

    const champDisplay = document.createElement('div');
    champDisplay.className = 'champion-display';
    if (playerColor) {
      champDisplay.style.borderColor = playerColor;
      champDisplay.style.background = hexToRgba(playerColor, 0.1);
    }

    let html = '<div class="champion-trophy">&#127942;</div>';
    if (logoUrl) {
      html += `<img class="champion-logo" src="${escapeHtml(logoUrl)}" alt="" onerror="if(this.src!=='${escapeHtml(cdnUrl)}')this.src='${escapeHtml(cdnUrl)}';else this.style.display='none'">`;
    }
    html += `<div class="champion-name">${escapeHtml(champResult)}</div>`;
    if (champTeam) {
      html += `<div class="champion-seed">${champTeam.seed} seed</div>`;
    }
    if (champTeam && champTeam.owner) {
      html += `<div class="champion-owner" style="background:${playerColor};color:#fff">${escapeHtml(champTeam.owner)}</div>`;
    }
    champDisplay.innerHTML = html;
    centerCol.appendChild(champDisplay);
  }

  wrapper.appendChild(centerCol);

  // ── Connector ──
  const connRight = document.createElement('div');
  connRight.className = 'ff-connector';
  wrapper.appendChild(connRight);

  // ── Right semifinal (matchup 1) ──
  const rightCol = document.createElement('div');
  rightCol.className = 'ff-col';

  const pair1 = ffMatchups[1];
  const right1Name = DATA.results[pair1[0]].elite8[0];
  const right2Name = DATA.results[pair1[1]].elite8[0];
  const right1 = right1Name ? getTeamByName(right1Name) : null;
  const right2 = right2Name ? getTeamByName(right2Name) : null;

  const rightLabel = document.createElement('div');
  rightLabel.className = 'ff-label';
  rightLabel.textContent = `${pair1[0]} vs ${pair1[1]}`;
  rightCol.appendChild(rightLabel);

  const rightMatchup = document.createElement('div');
  rightMatchup.className = 'matchup';
  rightMatchup.appendChild(buildTeamSlot(
    right1 || { seed: '?', name: `${pair1[0]} Champion`, owner: null, firstFour: false },
    ffResults[1], true, 'finalFour'
  ));
  rightMatchup.appendChild(buildTeamSlot(
    right2 || { seed: '?', name: `${pair1[1]} Champion`, owner: null, firstFour: false },
    ffResults[1], true, 'finalFour'
  ));
  const rightTime = buildFFMatchupTime(right1, right2, 'finalFour', 1, rightMatchup);
  if (rightTime) rightMatchup.appendChild(rightTime);
  rightCol.appendChild(rightMatchup);
  wrapper.appendChild(rightCol);

  return wrapper;
}
