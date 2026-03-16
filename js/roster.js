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
        ? `<img class="team-logo" src="${logoUrl}" alt="" width="20" height="20" loading="lazy" onerror="if(this.src!=='${cdnUrl}')this.src='${cdnUrl}';else this.style.display='none'">`
        : '';
      return `
        <li class="roster-team ${statusClass}">
          ${logoImg}
          <span class="seed">${t.seed}</span>
          <span class="team-name">${t.name}</span>
          <span class="region-badge">${t.region}</span>
        </li>
      `;
    }).join('');

    return `
      <div class="roster-card" style="border:2px solid ${player.color}">
        <div class="roster-header" data-player="${player.name}" style="background:${hexToRgba(player.color, 0.15)};border-bottom:2px solid ${player.color}">
          <span class="roster-player-name" style="color:${player.color}">${player.name}</span>
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
