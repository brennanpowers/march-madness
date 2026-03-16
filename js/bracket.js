/* ── Bracket Rendering ── */

function renderBracket() {
  const regionNames = Object.keys(DATA.regions);
  const tabs = document.getElementById('region-tabs');
  tabs.innerHTML = [...regionNames, 'Final Four'].map((name, i) => `
    <button class="region-tab ${i === 0 ? 'active' : ''}" data-region="${name}">${name}</button>
  `).join('');

  tabs.querySelectorAll('.region-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.querySelectorAll('.region-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      showRegion(tab.dataset.region);
    });
  });

  showRegion(regionNames[0]);
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
      matchup.appendChild(buildTeamSlot(top, winner, roundIdx === 0));
      matchup.appendChild(buildTeamSlot(bot, winner, roundIdx === 0));

      // Game time
      const schedule = DATA.schedule?.[regionName]?.[roundName];
      const gameDate = schedule?.[matchIdx];
      if (gameDate) {
        const timeEl = document.createElement('div');
        timeEl.className = 'matchup-time';
        timeEl.textContent = formatGameTime(gameDate, !!winner);
        matchup.appendChild(timeEl);
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

function buildTeamSlot(team, winner, showSeed) {
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

  el.innerHTML = logoImg + seedSpan + nameSpan + ownerSpan;
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

function buildFinalFour() {
  const wrapper = document.createElement('div');
  wrapper.className = 'final-four';

  const ffMatchups = DATA.finalFourMatchups;
  const ffResults = DATA.results.finalFour;
  const champResult = DATA.results.championship[0];

  // Semi-final matchups
  ffMatchups.forEach((pair, i) => {
    const region1 = pair[0];
    const region2 = pair[1];
    const team1Name = DATA.results[region1].elite8[0];
    const team2Name = DATA.results[region2].elite8[0];
    const team1 = team1Name ? getTeamByName(team1Name) : null;
    const team2 = team2Name ? getTeamByName(team2Name) : null;
    const winner = ffResults[i];

    const div = document.createElement('div');
    div.className = 'ff-matchup';

    const label = document.createElement('div');
    label.className = 'ff-label';
    label.textContent = `${region1} vs ${region2}`;
    div.appendChild(label);

    const matchup = document.createElement('div');
    matchup.className = 'matchup';
    matchup.appendChild(buildTeamSlot(
      team1 || { seed: '?', name: `${region1} Champion`, owner: null, firstFour: false },
      winner, true
    ));
    matchup.appendChild(buildTeamSlot(
      team2 || { seed: '?', name: `${region2} Champion`, owner: null, firstFour: false },
      winner, true
    ));
    // FF game time
    const ffGameDate = DATA.schedule?.finalFour?.[i];
    if (ffGameDate) {
      const timeEl = document.createElement('div');
      timeEl.className = 'matchup-time';
      timeEl.textContent = formatGameTime(ffGameDate, !!winner);
      matchup.appendChild(timeEl);
    }

    div.appendChild(matchup);
    wrapper.appendChild(div);
  });

  // Championship
  const champDiv = document.createElement('div');
  champDiv.className = 'ff-matchup';
  const champLabel = document.createElement('div');
  champLabel.className = 'championship-label';
  champLabel.textContent = 'Championship';
  champDiv.appendChild(champLabel);

  const semi1Winner = ffResults[0];
  const semi2Winner = ffResults[1];
  const team1 = semi1Winner ? getTeamByName(semi1Winner) : null;
  const team2 = semi2Winner ? getTeamByName(semi2Winner) : null;

  const champMatchup = document.createElement('div');
  champMatchup.className = 'matchup';
  champMatchup.appendChild(buildTeamSlot(
    team1 || { seed: '?', name: 'Semifinal 1 Winner', owner: null, firstFour: false },
    champResult, true
  ));
  champMatchup.appendChild(buildTeamSlot(
    team2 || { seed: '?', name: 'Semifinal 2 Winner', owner: null, firstFour: false },
    champResult, true
  ));
  const champGameDate = DATA.schedule?.championship?.[0];
  if (champGameDate) {
    const timeEl = document.createElement('div');
    timeEl.className = 'matchup-time';
    timeEl.textContent = formatGameTime(champGameDate, !!champResult);
    champMatchup.appendChild(timeEl);
  }

  champDiv.appendChild(champMatchup);
  wrapper.appendChild(champDiv);

  // Champion display
  if (champResult) {
    const champTeam = getTeamByName(champResult);
    const champDisplay = document.createElement('div');
    champDisplay.className = 'championship-label';
    champDisplay.textContent = `🏆 ${champResult}${champTeam ? ` (${champTeam.seed})` : ''}`;
    champDisplay.style.fontSize = '1.2rem';
    wrapper.appendChild(champDisplay);
  }

  return wrapper;
}
