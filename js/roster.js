/* ── Roster Tab Rendering ── */

function renderRoster(scores) {
  const container = document.getElementById('roster-view');
  container.innerHTML = scores.map(player => {
    const teamRows = player.teams.map(t => {
      const statusClass = t.eliminated ? 'eliminated' : (t.wins.length > 0 ? 'active' : '');
      const team = getTeamByName(t.name);
      const logoUrl = team ? teamLogoUrl(team.espnId) : null;
      const cdnUrl = team ? teamLogoCdnUrl(team.espnId) : null;
      const logoImg = logoUrl
        ? `<img class="team-logo" src="${escapeHtml(logoUrl)}" alt="" width="20" height="20" loading="lazy" onerror="if(this.src!=='${escapeHtml(cdnUrl)}')this.src='${escapeHtml(cdnUrl)}';else this.style.display='none'">`
        : '';

      // Live game indicator — only show for games currently in progress
      let liveHtml = '';
      let isLiveGame = false;
      if (team && team.espnId) {
        for (const game of LIVE_GAMES) {
          if (!game.isLive) continue;
          const gt = game.teams.find(gt => gt.espnId === String(team.espnId));
          if (gt) {
            const opp = game.teams.find(gt2 => gt2.espnId !== String(team.espnId));
            const oppName = opp ? opp.shortName : '?';
            const oppScore = opp ? opp.score : '?';
            liveHtml = `<span class="roster-live">${gt.score}-${oppScore} vs ${escapeHtml(oppName)}</span>`;
            isLiveGame = true;
            break;
          }
        }
      }

      return `
        <li class="roster-team ${statusClass}${isLiveGame ? ' live' : ''}">
          ${logoImg}
          <span class="seed">${t.seed}</span>
          <div class="roster-team-info">
            <span class="team-name">${escapeHtml(t.name)}</span>
            ${liveHtml}
          </div>
          <span class="region-badge">${escapeHtml(t.region)}</span>
        </li>
      `;
    }).join('');

    return `
      <div class="roster-card" style="border:2px solid ${player.color}">
        <div class="roster-header" data-player="${escapeHtml(player.name)}" style="background:${hexToRgba(player.color, 0.15)};border-bottom:2px solid ${player.color}">
          <span class="roster-player-name" style="color:${player.color}">${escapeHtml(player.name)}</span>
          <span class="roster-score" style="color:${player.color}">${player.score} pts</span>
        </div>
        <ul class="roster-teams">${teamRows}</ul>
      </div>
    `;
  }).join('');

  container.querySelectorAll('.roster-header').forEach(header => {
    header.addEventListener('click', () => {
      const name = header.dataset.player;
      const player = scores.find(p => p.name === name);
      if (player) showScoreBreakdown(player);
    });
  });
}
