/**
 * app.js - Rajasthan Royals SupeRR Selector S2 Interactive Dashboard Engine
 * Zero external network dependencies - 100% offline functionality.
 */

document.addEventListener('DOMContentLoaded', () => {
  const data = window.SUPERR_DATA;
  if (!data) {
    console.error('Fatal: SUPERR_DATA payload missing.');
    return;
  }

  // State
  let currentTab = 'overview';

  // Batters Table State
  let batSortKey = 'final_pressure_rating';
  let batSortAsc = false;
  let batSearch = '';
  let batRole = 'all';
  let batMinBalls = 70;

  // Bowlers Table State
  let bowlSortKey = 'final_pressure_rating';
  let bowlSortAsc = false;
  let bowlSearch = '';
  let bowlRole = 'all';
  let bowlMinBalls = 70;

  // Compare State
  let comparePlayers = [data.top10_batters[0], data.top10_batters[1]];

  // Interactive Chase Scrubber State

  // Tab Navigation
  const tabButtons = document.querySelectorAll('.nav-tab-btn');
  const tabSections = document.querySelectorAll('.tab-section');

  function switchTab(tabId) {
    currentTab = tabId;
    tabButtons.forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tabId);
    });
    tabSections.forEach(sec => {
      sec.style.display = sec.id === `section-${tabId}` ? 'block' : 'none';
    });
    if (tabId === 'batters') renderBattersTable();
    if (tabId === 'bowlers') renderBowlersTable();
    if (tabId === 'compare') renderCompareView();
  }

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // ==================== SECTION 1: OVERVIEW HERO ====================
  function renderOverview() {
    const batGrid = document.getElementById('top10-batters-grid');
    const bowlGrid = document.getElementById('top10-bowlers-grid');

    if (batGrid) {
      batGrid.innerHTML = data.top10_batters.map((p, idx) => `
        <div class="player-card rank-${p.rank} animate-rise" style="animation-delay: ${idx * 60}ms" onclick="openPlayerModal('batter', ${p.striker_id})">
          <div class="card-header">
            <div>
              <div class="player-name">#${p.rank} ${p.striker_name}</div>
              <span class="player-role-tag">${String(p.role).replace('_', ' ')}</span>
            </div>
            <div class="card-rating-block">
              <div class="rating-headline count-up" data-target="${p.final_pressure_rating.toFixed(2)}">${p.final_pressure_rating.toFixed(2)}</div>
              <div class="rating-ci">[${p.ci_lower.toFixed(1)}, ${p.ci_upper.toFixed(1)}]</div>
            </div>
          </div>
          <div class="card-metrics-row">
            <div class="metric-item">
              <span class="metric-label">Pressure SR</span>
              <span class="metric-num">${p.sr_hp.toFixed(1)}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">RAE / 100</span>
              <span class="metric-num" style="color: ${p.rae_per_100 >= 0 ? 'var(--success)' : 'var(--danger)'}">
                ${p.rae_per_100 >= 0 ? '+' : ''}${p.rae_per_100.toFixed(1)}
              </span>
            </div>
            <div class="metric-item">
              <span class="metric-label">Hit Rate</span>
              <span class="metric-num">${(p.hit_rate * 100).toFixed(0)}%</span>
            </div>
          </div>
        </div>
      `).join('');
    }

    if (bowlGrid) {
      bowlGrid.innerHTML = data.top10_bowlers.map((p, idx) => `
        <div class="player-card rank-${p.rank} animate-rise" style="animation-delay: ${idx * 60}ms" onclick="openPlayerModal('bowler', ${p.bowler_id})">
          <div class="card-header">
            <div>
              <div class="player-name">#${p.rank} ${p.bowler_name}</div>
              <span class="player-role-tag">${String(p.role)} phase</span>
            </div>
            <div class="card-rating-block">
              <div class="rating-headline count-up" data-target="${p.final_pressure_rating.toFixed(2)}">${p.final_pressure_rating.toFixed(2)}</div>
              <div class="rating-ci">[${p.ci_lower.toFixed(1)}, ${p.ci_upper.toFixed(1)}]</div>
            </div>
          </div>
          <div class="card-metrics-row">
            <div class="metric-item">
              <span class="metric-label">Pressure Econ</span>
              <span class="metric-num">${p.econ_hp.toFixed(2)}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">RSAE / 100</span>
              <span class="metric-num" style="color: ${p.rsae_per_100 >= 0 ? 'var(--success)' : 'var(--danger)'}">
                ${p.rsae_per_100 >= 0 ? '+' : ''}${p.rsae_per_100.toFixed(1)}
              </span>
            </div>
            <div class="metric-item">
              <span class="metric-label">Hit Rate</span>
              <span class="metric-num">${(p.hit_rate * 100).toFixed(0)}%</span>
            </div>
          </div>
        </div>
      `).join('');
    }
  }

  // ==================== SECTION 2: INTERACTIVE SCRUBBER ====================
  function initScrubber() {
    const slider = document.getElementById('scrubber-range');
    const playBtn = document.getElementById('scrubber-play-btn');
    if (!slider || chaseBalls.length === 0) return;

    slider.max = chaseBalls.length - 1;

    function updateScrubberView(idx) {
      scrubberIndex = idx;
      slider.value = idx;
      const b = chaseBalls[idx];
      if (!b) return;

      document.getElementById('scrub-ball-desc').textContent = 
        `Over ${b.overid}.${b.over_ball_num} | ${b.bowler_name} to ${b.striker_name}`;

      const wpPct = (b.wp * 100).toFixed(1);
      const piVal = b.pressure_index.toFixed(3);

      document.getElementById('scrub-wp-val').textContent = `${wpPct}%`;
      document.getElementById('scrub-pi-val').textContent = piVal;

      const wpBar = document.getElementById('scrub-wp-bar');
      if (wpBar) wpBar.style.width = `${wpPct}%`;

      const piBar = document.getElementById('scrub-pi-bar');
      if (piBar) {
        piBar.style.width = `${Math.min(100, b.pressure_index * 100)}%`;
        piBar.style.backgroundColor = b.pressure_index >= 0.38 ? 'var(--rr-pink)' : 'var(--rr-blue)';
      }

      document.getElementById('scrub-score').textContent = 
        `${b.cum_total_runs} (Needs ${b.runs_needed} off ${b.balls_remaining}b)`;
      document.getElementById('scrub-rrr').textContent = `RRR: ${b.required_run_rate.toFixed(2)}`;

      let outcomeText = `${b.batter_runs} runs`;
      if (b.is_wicket) outcomeText = `WICKET! (${b.dismissal_type})`;
      else if (b.is_six) outcomeText = `SIX!`;
      else if (b.is_four) outcomeText = `FOUR!`;
      else if (b.batter_runs === 0) outcomeText = `Dot Ball`;
      document.getElementById('scrub-outcome').textContent = outcomeText;
    }

    slider.addEventListener('input', (e) => {
      updateScrubberView(parseInt(e.target.value));
    });

    let playing = false;
    let timer = null;
    playBtn.addEventListener('click', () => {
      if (playing) {
        clearInterval(timer);
        playBtn.textContent = '▶ Play Chase';
        playing = false;
      } else {
        playBtn.textContent = '⏸ Pause';
        playing = true;
        timer = setInterval(() => {
          if (scrubberIndex >= chaseBalls.length - 1) {
            clearInterval(timer);
            playBtn.textContent = '▶ Replay';
            playing = false;
          } else {
            updateScrubberView(scrubberIndex + 1);
          }
        }, 550);
      }
    });

    updateScrubberView(0);
  }

  // ==================== SECTION 3: BATTERS TABLE ====================
  function renderBattersTable() {
    const tbody = document.getElementById('batters-table-body');
    if (!tbody) return;

    let list = data.all_batters.filter(p => {
      const matchSearch = String(p.striker_name).toLowerCase().includes(batSearch.toLowerCase());
      const matchRole = batRole === 'all' || p.role === batRole;
      const matchBalls = p.balls >= batMinBalls;
      return matchSearch && matchRole && matchBalls;
    });

    list.sort((a, b) => {
      let va = a[batSortKey] ?? 0;
      let vb = b[batSortKey] ?? 0;
      return batSortAsc ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1);
    });

    tbody.innerHTML = list.map((p, i) => `
      <tr onclick="openPlayerModal('batter', ${p.striker_id})">
        <td style="font-weight: bold; color: var(--rr-pink);">#${i + 1}</td>
        <td><strong>${p.striker_name}</strong></td>
        <td><span class="player-role-tag">${String(p.role).replace('_', ' ')}</span></td>
        <td>${p.balls}</td>
        <td>${p.matches}</td>
        <td><strong>${p.sr_hp.toFixed(1)}</strong></td>
        <td style="color: ${p.rae_per_100 >= 0 ? 'var(--success)' : 'var(--danger)'}">
          ${p.rae_per_100 >= 0 ? '+' : ''}${p.rae_per_100.toFixed(1)}
        </td>
        <td>${(p.hit_rate * 100).toFixed(0)}%</td>
        <td style="font-weight: 800; font-family: var(--font-heading); font-size: 15px;">
          ${p.final_pressure_rating.toFixed(2)}
        </td>
        <td style="color: var(--text-muted); font-size: 11px;">[${p.ci_lower.toFixed(1)}, ${p.ci_upper.toFixed(1)}]</td>
      </tr>
    `).join('');
  }

  // ==================== SECTION 4: BOWLERS TABLE ====================
  function renderBowlersTable() {
    const tbody = document.getElementById('bowlers-table-body');
    if (!tbody) return;

    let list = data.all_bowlers.filter(p => {
      const matchSearch = String(p.bowler_name).toLowerCase().includes(bowlSearch.toLowerCase());
      const matchRole = bowlRole === 'all' || p.role === bowlRole;
      const matchBalls = p.balls >= bowlMinBalls;
      return matchSearch && matchRole && matchBalls;
    });

    list.sort((a, b) => {
      let va = a[bowlSortKey] ?? 0;
      let vb = b[bowlSortKey] ?? 0;
      return bowlSortAsc ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1);
    });

    tbody.innerHTML = list.map((p, i) => `
      <tr onclick="openPlayerModal('bowler', ${p.bowler_id})">
        <td style="font-weight: bold; color: var(--rr-pink);">#${i + 1}</td>
        <td><strong>${p.bowler_name}</strong></td>
        <td><span class="player-role-tag">${String(p.role)}</span></td>
        <td>${p.balls}</td>
        <td>${p.matches}</td>
        <td><strong>${p.econ_hp.toFixed(2)}</strong></td>
        <td style="color: ${p.rsae_per_100 >= 0 ? 'var(--success)' : 'var(--danger)'}">
          ${p.rsae_per_100 >= 0 ? '+' : ''}${p.rsae_per_100.toFixed(1)}
        </td>
        <td>${(p.hit_rate * 100).toFixed(0)}%</td>
        <td style="font-weight: 800; font-family: var(--font-heading); font-size: 15px;">
          ${p.final_pressure_rating.toFixed(2)}
        </td>
        <td style="color: var(--text-muted); font-size: 11px;">[${p.ci_lower.toFixed(1)}, ${p.ci_upper.toFixed(1)}]</td>
      </tr>
    `).join('');
  }

  // Search & Filter Listeners
  document.getElementById('bat-search')?.addEventListener('input', (e) => {
    batSearch = e.target.value;
    renderBattersTable();
  });
  document.getElementById('bat-role-filter')?.addEventListener('change', (e) => {
    batRole = e.target.value;
    renderBattersTable();
  });
  document.getElementById('bat-balls-slider')?.addEventListener('input', (e) => {
    batMinBalls = parseInt(e.target.value);
    document.getElementById('bat-balls-val').textContent = batMinBalls;
    renderBattersTable();
  });

  document.getElementById('bowl-search')?.addEventListener('input', (e) => {
    bowlSearch = e.target.value;
    renderBowlersTable();
  });
  document.getElementById('bowl-role-filter')?.addEventListener('change', (e) => {
    bowlRole = e.target.value;
    renderBowlersTable();
  });
  document.getElementById('bowl-balls-slider')?.addEventListener('input', (e) => {
    bowlMinBalls = parseInt(e.target.value);
    document.getElementById('bowl-balls-val').textContent = bowlMinBalls;
    renderBowlersTable();
  });

  // Table Column Sort Click Handlers
  document.querySelectorAll('th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.sort;
      const isBat = th.closest('#section-batters') !== null;
      if (isBat) {
        batSortAsc = (batSortKey === key) ? !batSortAsc : false;
        batSortKey = key;
        renderBattersTable();
      } else {
        bowlSortAsc = (bowlSortKey === key) ? !bowlSortAsc : false;
        bowlSortKey = key;
        renderBowlersTable();
      }
    });
  });

  // ==================== SECTION 5: PLAYER MODAL ====================
  window.openPlayerModal = function(type, id) {
    const list = type === 'batter' ? data.all_batters : data.all_bowlers;
    const p = list.find(x => (type === 'batter' ? x.striker_id : x.bowler_id) === id);
    if (!p) return;

    const modal = document.getElementById('player-modal');
    const content = document.getElementById('modal-content-slot');
    if (!modal || !content) return;

    const isBat = type === 'batter';
    const name = isBat ? p.striker_name : p.bowler_name;

    content.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid var(--border); padding-bottom: 16px; margin-bottom: 18px;">
        <div>
          <h2 style="font-size: 24px; color: var(--text);">${name}</h2>
          <span class="player-role-tag">${isBat ? p.role : p.role + ' phase'}</span>
        </div>
        <div style="text-align: right;">
          <div style="font-size: 32px; font-weight: 800; font-family: var(--font-heading); color: var(--rr-pink);">${p.final_pressure_rating.toFixed(2)}</div>
          <div style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono);">95% CI: [${p.ci_lower.toFixed(1)}, ${p.ci_upper.toFixed(1)}]</div>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 18px;">
        <div style="background: var(--bg-secondary); padding: 14px; border-radius: var(--radius-md);">
          <div style="font-size: 12px; font-weight: bold; text-transform: uppercase; color: var(--rr-pink); margin-bottom: 8px;">🔥 High Pressure Execution</div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span>Sample Deliveries:</span> <strong>${p.balls} balls (${p.matches} matches)</strong>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span>${isBat ? 'Pressure Strike Rate' : 'Pressure Economy'}:</span>
            <strong>${isBat ? p.sr_hp.toFixed(1) : p.econ_hp.toFixed(2)}</strong>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span>${isBat ? 'RAE / 100 Balls' : 'RSAE / 100 Balls'}:</span>
            <strong style="color: ${(isBat ? p.rae_per_100 : p.rsae_per_100) >= 0 ? 'var(--success)' : 'var(--danger)'}">
              ${(isBat ? p.rae_per_100 : p.rsae_per_100) >= 0 ? '+' : ''}${(isBat ? p.rae_per_100 : p.rsae_per_100).toFixed(1)}
            </strong>
          </div>
          <div style="display: flex; justify-content: space-between;">
            <span>Positive Match Hit Rate:</span>
            <strong>${(p.hit_rate * 100).toFixed(0)}%</strong>
          </div>
        </div>

        <div style="background: var(--bg-secondary); padding: 14px; border-radius: var(--radius-md);">
          <div style="font-size: 12px; font-weight: bold; text-transform: uppercase; color: var(--rr-blue); margin-bottom: 8px;">⚖️ Baseline & Delta Comparison</div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span>Baseline ${isBat ? 'BPV' : 'BoPV'} / 100:</span>
            <strong>${(isBat ? p.bpv_base : p.bopv_base).toFixed(1)}</strong>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span>High Pressure ${isBat ? 'BPV' : 'BoPV'} / 100:</span>
            <strong>${(isBat ? p.bpv_raw : p.bopv_raw).toFixed(1)}</strong>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span>Pressure Delta:</span>
            <strong style="color: ${p.pressure_delta >= 0 ? 'var(--success)' : 'var(--danger)'}">
              ${p.pressure_delta >= 0 ? '+' : ''}${p.pressure_delta.toFixed(1)}
            </strong>
          </div>
          <div style="display: flex; justify-content: space-between;">
            <span>Shrinkage Retention:</span>
            <strong>${(p.shrinkage_weight * 100).toFixed(0)}%</strong>
          </div>
        </div>
      </div>

      <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 14px;">
        <button class="btn btn-secondary" onclick="addToCompare(${JSON.stringify(p).replace(/"/g, '&quot;')})">+ Add to Compare</button>
        <button class="btn btn-primary" onclick="closePlayerModal()">Close</button>
      </div>
    `;

    modal.style.display = 'flex';
  };

  window.closePlayerModal = function() {
    const modal = document.getElementById('player-modal');
    if (modal) modal.style.display = 'none';
  };

  // ==================== SECTION 6: COMPARE TOOL ====================
  window.addToCompare = function(p) {
    if (comparePlayers.length >= 3) {
      comparePlayers.shift();
    }
    comparePlayers.push(p);
    closePlayerModal();
    switchTab('compare');
  };

  function renderCompareView() {
    const container = document.getElementById('compare-cards-slot');
    if (!container) return;

    if (comparePlayers.length === 0) {
      container.innerHTML = `<p style="color: var(--text-muted);">Select players from the Batters or Bowlers tabs to compare head-to-head.</p>`;
      return;
    }

    container.innerHTML = comparePlayers.map((p, idx) => {
      const isBat = 'striker_name' in p;
      const name = isBat ? p.striker_name : p.bowler_name;
      return `
        <div class="compare-card ${idx === 0 ? 'primary' : ''}">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <h3 style="font-size: 20px; color: var(--text);">${name}</h3>
            <span class="player-role-tag">${isBat ? p.role : p.role + ' phase'}</span>
          </div>
          <div style="font-size: 32px; font-family: var(--font-heading); color: var(--rr-pink); font-weight: 800; margin-bottom: 12px;">
            ${p.final_pressure_rating.toFixed(2)}
          </div>
          <div style="display: flex; flex-direction: column; gap: 8px; font-size: 13.5px;">
            <div style="display: flex; justify-content: space-between;">
              <span>High-Pressure Balls:</span> <strong>${p.balls}</strong>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span>${isBat ? 'Pressure Strike Rate' : 'Pressure Economy'}:</span>
              <strong>${isBat ? p.sr_hp.toFixed(1) : p.econ_hp.toFixed(2)}</strong>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span>${isBat ? 'RAE / 100' : 'RSAE / 100'}:</span>
              <strong>${(isBat ? p.rae_per_100 : p.rsae_per_100).toFixed(1)}</strong>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span>Consistency Hit Rate:</span>
              <strong>${(p.hit_rate * 100).toFixed(0)}%</strong>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span>95% Confidence Interval:</span>
              <strong style="font-family: var(--font-mono);">[${p.ci_lower.toFixed(1)}, ${p.ci_upper.toFixed(1)}]</strong>
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  // ==================== SECTION 7: SENSITIVITY TABLE ====================
  function renderSensitivity() {
    const tbody = document.getElementById('sensitivity-table-body');
    if (!tbody || !data.sensitivity) return;

    tbody.innerHTML = data.sensitivity.map(s => `
      <tr>
        <td><strong>${s.scenario}</strong></td>
        <td>${s.batter_spearman.toFixed(3)}</td>
        <td>${s.batter_kendall.toFixed(3)}</td>
        <td style="font-weight: bold; color: var(--rr-pink);">${s.batter_top10_overlap}</td>
        <td>${s.bowler_spearman.toFixed(3)}</td>
        <td>${s.bowler_kendall.toFixed(3)}</td>
        <td style="font-weight: bold; color: var(--rr-blue);">${s.bowler_top10_overlap}</td>
      </tr>
    `).join('');
  }

  // Initial Boot
  renderOverview();
  initScrubber();
  renderSensitivity();
});

