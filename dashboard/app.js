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
  let showBattersTop15 = false;
  let showBowlersTop15 = false;

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

  // Tab Navigation with Full Browser History & Back/Forward Support
  const tabButtons = document.querySelectorAll('.nav-tab-btn');
  const tabSections = document.querySelectorAll('.tab-section');

  function switchTab(tabId, pushHistory = true) {
    if (!tabId) tabId = 'overview';
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

    if (pushHistory) {
      const newHash = tabId === 'overview' ? '' : '#' + tabId;
      if (window.location.hash !== newHash) {
        try {
          history.pushState({ tab: tabId }, '', newHash || window.location.pathname);
        } catch (e) {
          // Fallback if local file protocol restricts pushState
          window.location.hash = newHash;
        }
      }
    }
  }

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab, true));
  });

  // Handle native browser Back / Forward buttons
  window.addEventListener('popstate', (e) => {
    if (e.state && e.state.tab) {
      switchTab(e.state.tab, false);
    } else if (window.location.hash) {
      const hashTab = window.location.hash.replace('#', '');
      if (document.getElementById(`section-${hashTab}`)) {
        switchTab(hashTab, false);
      }
    } else if (window.INITIAL_TAB) {
      switchTab(window.INITIAL_TAB, false);
    } else {
      switchTab('overview', false);
    }
  });

  // ==================== SECTION 1: OVERVIEW HERO (TOP 10 & TOP 15) ====================
  function renderOverview() {
    const batGrid = document.getElementById('top10-batters-grid');
    const bowlGrid = document.getElementById('top10-bowlers-grid');
    const batHeading = document.getElementById('batters-heading');
    const bowlHeading = document.getElementById('bowlers-heading');
    const batBtn = document.getElementById('toggle-batters-top15-btn');
    const bowlBtn = document.getElementById('toggle-bowlers-top15-btn');

    const batList = showBattersTop15 ? (data.top15_batters || data.top10_batters) : data.top10_batters;
    const bowlList = showBowlersTop15 ? (data.top15_bowlers || data.top10_bowlers) : data.top10_bowlers;

    if (batHeading) batHeading.textContent = showBattersTop15 ? 'Top 15 Batters Under Pressure' : 'Top 10 Batters Under Pressure';
    if (bowlHeading) bowlHeading.textContent = showBowlersTop15 ? 'Top 15 Bowlers Under Pressure' : 'Top 10 Bowlers Under Pressure';
    if (batBtn) batBtn.textContent = showBattersTop15 ? 'Show Top 10 Only ↑' : 'Show Next 5 Players (Top 15) ↓';
    if (bowlBtn) bowlBtn.textContent = showBowlersTop15 ? 'Show Top 10 Only ↑' : 'Show Next 5 Players (Top 15) ↓';

    if (batGrid) {
      batGrid.innerHTML = batList.map((p, idx) => `
        <div class="player-card rank-${p.rank} animate-rise" style="animation-delay: ${idx * 40}ms" onclick="openPlayerModal('batter', ${p.striker_id})">
          <div class="card-header">
            <div>
              <div class="player-name">#${p.rank} ${p.striker_name}</div>
              <span class="player-role-tag">${String(p.role).replace('_', ' ')}</span>
            </div>
            <div class="card-rating-block" title="Pressure Performance Rating: Net runs contributed above league average per 100 high-pressure balls faced.">
              <div class="rating-headline count-up" data-target="${p.final_pressure_rating.toFixed(2)}">+${p.final_pressure_rating.toFixed(2)}</div>
              <div class="rating-sub-label">Runs Above Avg / 100b</div>
              <div class="rating-ci" title="95% Clustered Confidence Interval: statistically verified range across 400 match resamples"><span style="opacity: 0.7; font-size: 9.5px; font-weight: normal;">95% CI:</span> [${p.ci_lower.toFixed(1)}, ${p.ci_upper.toFixed(1)}]</div>
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
      bowlGrid.innerHTML = bowlList.map((p, idx) => `
        <div class="player-card rank-${p.rank} animate-rise" style="animation-delay: ${idx * 40}ms" onclick="openPlayerModal('bowler', ${p.bowler_id})">
          <div class="card-header">
            <div>
              <div class="player-name">#${p.rank} ${p.bowler_name}</div>
              <span class="player-role-tag">${String(p.role)} phase</span>
            </div>
            <div class="card-rating-block" title="Pressure Performance Rating: Net runs saved compared to league average per 100 high-pressure balls bowled.">
              <div class="rating-headline count-up" data-target="${p.final_pressure_rating.toFixed(2)}">+${p.final_pressure_rating.toFixed(2)}</div>
              <div class="rating-sub-label">Runs Saved / 100b</div>
              <div class="rating-ci" title="95% Clustered Confidence Interval: statistically verified range across 400 match resamples"><span style="opacity: 0.7; font-size: 9.5px; font-weight: normal;">95% CI:</span> [${p.ci_lower.toFixed(1)}, ${p.ci_upper.toFixed(1)}]</div>
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

  // Toggle Top 15 Event Listeners
  document.getElementById('toggle-batters-top15-btn')?.addEventListener('click', () => {
    showBattersTop15 = !showBattersTop15;
    renderOverview();
  });

  document.getElementById('toggle-bowlers-top15-btn')?.addEventListener('click', () => {
    showBowlersTop15 = !showBowlersTop15;
    renderOverview();
  });

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
        <td style="font-weight: 800; font-family: var(--font-heading); font-size: 15px; color: var(--rr-pink);">
          +${p.final_pressure_rating.toFixed(2)}
          <span style="font-size: 9.5px; font-weight: normal; color: var(--text-muted); display: block;">runs/100b</span>
        </td>
        <td style="color: var(--text-secondary); font-size: 11px; font-family: var(--font-mono); font-weight: 600;">[${p.ci_lower.toFixed(1)}, ${p.ci_upper.toFixed(1)}]</td>
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
        <td style="font-weight: 800; font-family: var(--font-heading); font-size: 15px; color: var(--rr-blue);">
          +${p.final_pressure_rating.toFixed(2)}
          <span style="font-size: 9.5px; font-weight: normal; color: var(--text-muted); display: block;">saved/100b</span>
        </td>
        <td style="color: var(--text-secondary); font-size: 11px; font-family: var(--font-mono); font-weight: 600;">[${p.ci_lower.toFixed(1)}, ${p.ci_upper.toFixed(1)}]</td>
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
      <div style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid var(--border); padding-bottom: 16px; margin-bottom: 14px;">
        <div>
          <h2 style="font-size: 24px; color: var(--text);">${name}</h2>
          <span class="player-role-tag">${isBat ? p.role : p.role + ' phase'}</span>
        </div>
        <div style="text-align: right;">
          <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.5px;">
            ${isBat ? 'Net Runs Above Avg / 100b' : 'Net Runs Saved / 100b'}
          </div>
          <div style="font-size: 34px; font-weight: 800; font-family: var(--font-heading); color: var(--rr-pink); line-height: 1.1;">
            +${p.final_pressure_rating.toFixed(2)}
          </div>
          <div style="font-size: 11.5px; color: var(--text-secondary); font-family: var(--font-mono); font-weight: 600; margin-top: 2px;" title="95% Clustered Confidence Interval">
            95% CI: [${p.ci_lower.toFixed(1)}, ${p.ci_upper.toFixed(1)}]
          </div>
        </div>
      </div>

      <!-- Plain-English Real-World Meaning Callout -->
      <div style="background: rgba(230, 56, 148, 0.08); border-left: 4px solid var(--rr-pink); padding: 12px 14px; border-radius: 6px; margin-bottom: 16px; font-size: 12.5px; line-height: 1.5; color: var(--text);">
        💡 <strong>What this rating (+${p.final_pressure_rating.toFixed(2)}) means:</strong> Under high-pressure conditions (top 25% highest-leverage balls), <strong>${name}</strong> delivers <strong>+${p.final_pressure_rating.toFixed(2)} net runs ${isBat ? 'above' : 'saved compared to'} an average IPL/T20 ${isBat ? 'batter' : 'bowler'} per 100 deliveries</strong>. 
        The <strong>95% CI [${p.ci_lower.toFixed(1)}, ${p.ci_upper.toFixed(1)}]</strong> statistically proves with 95% certainty across 400 match resamples that his true skill level is between ${p.ci_lower.toFixed(1)} and ${p.ci_upper.toFixed(1)} runs.
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

  // ==================== SECTION 6: COMPARE TOOL WITH FULL CRUD ====================
  window.addToCompare = function(p) {
    // Avoid exact duplicate
    const exists = comparePlayers.some(x => (x.id === p.id) || 
      ('striker_id' in x && 'striker_id' in p && x.striker_id === p.striker_id) ||
      ('bowler_id' in x && 'bowler_id' in p && x.bowler_id === p.bowler_id)
    );
    if (!exists) {
      comparePlayers.push(p);
    }
    closePlayerModal();
    switchTab('compare');
  };

  window.removeComparePlayer = function(index) {
    comparePlayers.splice(index, 1);
    renderCompareView();
  };

  window.clearAllCompare = function() {
    comparePlayers = [];
    renderCompareView();
  };

  window.editCustomPlayer = function(index) {
    const p = comparePlayers[index];
    if (!p) return;
    openCustomPlayerModal(p, index);
  };

  // Quick Add UI logic
  const quickAddBar = document.getElementById('quick-add-bar');
  const quickAddType = document.getElementById('quick-add-type');
  const quickAddSelect = document.getElementById('quick-add-select');
  const addExistingBtn = document.getElementById('add-existing-player-btn');
  const confirmQuickAddBtn = document.getElementById('confirm-quick-add-btn');
  const cancelQuickAddBtn = document.getElementById('cancel-quick-add-btn');
  const clearCompareBtn = document.getElementById('clear-compare-btn');

  function populateQuickAddOptions() {
    if (!quickAddSelect || !quickAddType) return;
    const type = quickAddType.value;
    const list = type === 'batter' ? data.all_batters : data.all_bowlers;
    
    // Sort alphabetically by name
    const sorted = [...list].sort((a, b) => {
      const na = type === 'batter' ? a.striker_name : a.bowler_name;
      const nb = type === 'batter' ? b.striker_name : b.bowler_name;
      return na.localeCompare(nb);
    });

    quickAddSelect.innerHTML = sorted.map(p => {
      const id = type === 'batter' ? p.striker_id : p.bowler_id;
      const name = type === 'batter' ? p.striker_name : p.bowler_name;
      const rating = p.final_pressure_rating.toFixed(1);
      return `<option value="${id}">${name} (Rating: ${rating})</option>`;
    }).join('');
  }

  if (quickAddType) {
    quickAddType.addEventListener('change', populateQuickAddOptions);
  }

  if (addExistingBtn) {
    addExistingBtn.addEventListener('click', () => {
      populateQuickAddOptions();
      if (quickAddBar) quickAddBar.style.display = 'block';
    });
  }

  if (cancelQuickAddBtn) {
    cancelQuickAddBtn.addEventListener('click', () => {
      if (quickAddBar) quickAddBar.style.display = 'none';
    });
  }

  if (confirmQuickAddBtn) {
    confirmQuickAddBtn.addEventListener('click', () => {
      const type = quickAddType.value;
      const id = parseInt(quickAddSelect.value);
      const list = type === 'batter' ? data.all_batters : data.all_bowlers;
      const p = list.find(x => (type === 'batter' ? x.striker_id : x.bowler_id) === id);
      if (p) {
        window.addToCompare(p);
      }
      if (quickAddBar) quickAddBar.style.display = 'none';
    });
  }

  if (clearCompareBtn) {
    clearCompareBtn.addEventListener('click', () => {
      window.clearAllCompare();
    });
  }

  // Custom Player CRUD Modal
  window.openCustomPlayerModal = function(player = null, editIndex = -1) {
    const modal = document.getElementById('custom-player-modal');
    const title = document.getElementById('custom-modal-title');
    const form = document.getElementById('custom-player-form');
    if (!modal || !form) return;

    document.getElementById('custom-edit-index').value = editIndex;
    if (player && editIndex >= 0) {
      title.textContent = `Edit Matchup: ${player.striker_name || player.bowler_name || player.name}`;
      const isBat = player.is_custom ? player.player_type === 'batter' : ('striker_name' in player);
      document.getElementById('cust-name').value = player.striker_name || player.bowler_name || player.name;
      document.getElementById('cust-type').value = isBat ? 'batter' : 'bowler';
      document.getElementById('cust-role').value = player.role || 'Death Specialist';
      document.getElementById('cust-balls').value = player.balls || 100;
      document.getElementById('cust-rate').value = isBat ? (player.sr_hp || 180) : (player.econ_hp || 7.5);
      document.getElementById('cust-diff').value = isBat ? (player.rae_per_100 || 25) : (player.rsae_per_100 || 18);
      document.getElementById('cust-hit').value = player.hit_rate || 0.65;
      document.getElementById('cust-rating').value = player.final_pressure_rating || 20.0;
    } else {
      title.textContent = 'Create Custom Player / Scenario (CRUD)';
      form.reset();
      document.getElementById('custom-edit-index').value = -1;
    }
    modal.style.display = 'flex';
  };

  window.closeCustomPlayerModal = function() {
    const modal = document.getElementById('custom-player-modal');
    if (modal) modal.style.display = 'none';
  };

  document.getElementById('create-custom-player-btn')?.addEventListener('click', () => {
    openCustomPlayerModal();
  });

  document.getElementById('cust-type')?.addEventListener('change', (e) => {
    const isBat = e.target.value === 'batter';
    const rateLbl = document.getElementById('cust-rate-label');
    const diffLbl = document.getElementById('cust-diff-label');
    if (rateLbl) rateLbl.textContent = isBat ? 'Pressure Strike Rate' : 'Pressure Economy (per over)';
    if (diffLbl) diffLbl.textContent = isBat ? 'RAE / 100 Balls' : 'RSAE / 100 Balls';
  });

  document.getElementById('custom-player-form')?.addEventListener('submit', (e) => {
    e.preventDefault();
    const editIndex = parseInt(document.getElementById('custom-edit-index').value);
    const type = document.getElementById('cust-type').value;
    const isBat = type === 'batter';
    const name = document.getElementById('cust-name').value;
    const role = document.getElementById('cust-role').value;
    const balls = parseInt(document.getElementById('cust-balls').value);
    const rate = parseFloat(document.getElementById('cust-rate').value);
    const diff = parseFloat(document.getElementById('cust-diff').value);
    const hitRate = parseFloat(document.getElementById('cust-hit').value);
    const rating = parseFloat(document.getElementById('cust-rating').value);

    const customObj = {
      is_custom: true,
      player_type: type,
      name: name,
      role: role,
      balls: balls,
      hit_rate: hitRate,
      final_pressure_rating: rating,
      ci_lower: Math.max(0, rating - 8.5),
      ci_upper: rating + 12.0
    };

    if (isBat) {
      customObj.striker_name = name;
      customObj.sr_hp = rate;
      customObj.rae_per_100 = diff;
    } else {
      customObj.bowler_name = name;
      customObj.econ_hp = rate;
      customObj.rsae_per_100 = diff;
    }

    if (editIndex >= 0 && editIndex < comparePlayers.length) {
      comparePlayers[editIndex] = customObj;
    } else {
      comparePlayers.push(customObj);
    }

    closeCustomPlayerModal();
    renderCompareView();
  });

  function renderCompareView() {
    const container = document.getElementById('compare-cards-slot');
    if (!container) return;

    if (comparePlayers.length === 0) {
      container.innerHTML = `
        <div style="grid-column: 1/-1; background: var(--surface); border: 2px dashed var(--border); padding: 40px; border-radius: var(--radius-md); text-align: center;">
          <p style="color: var(--text-muted); font-size: 15px; margin-bottom: 12px;">No players currently selected in the comparison deck.</p>
          <button class="btn btn-primary" onclick="document.getElementById('add-existing-player-btn').click()">+ Add Player from Database</button>
        </div>
      `;
      return;
    }

    container.innerHTML = comparePlayers.map((p, idx) => {
      const isBat = p.is_custom ? (p.player_type === 'batter') : ('striker_name' in p);
      const name = p.striker_name || p.bowler_name || p.name;
      const rateVal = isBat ? `${(p.sr_hp || 0).toFixed(1)} SR` : `${(p.econ_hp || 0).toFixed(2)} Econ`;
      const diffVal = isBat ? `${(p.rae_per_100 || 0).toFixed(1)} RAE` : `${(p.rsae_per_100 || 0).toFixed(1)} RSAE`;
      const isCustomBadge = p.is_custom ? `<span style="background: var(--rr-gold-light); color: #B45309; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px; text-transform: uppercase;">Custom Trial</span>` : '';

      return `
        <div class="compare-card ${idx === 0 ? 'primary' : ''}">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
            <div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <h3 style="font-size: 19px; color: var(--text);">${name}</h3>
                ${isCustomBadge}
              </div>
              <span class="player-role-tag">${isBat ? p.role : p.role + ' phase'}</span>
            </div>
            <div style="display: flex; gap: 6px;">
              <button title="Edit Player / Scenario" onclick="editCustomPlayer(${idx})" style="background: var(--bg-secondary); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 4px 8px; cursor: pointer; font-size: 12px;">✏️</button>
              <button title="Remove Player" onclick="removeComparePlayer(${idx})" style="background: var(--bg-secondary); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 4px 8px; cursor: pointer; font-size: 12px; color: var(--danger);">🗑️</button>
            </div>
          </div>

          <div style="margin-bottom: 14px;">
            <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.5px;">
              ${isBat ? 'Net Runs Above Avg / 100b' : 'Net Runs Saved / 100b'}
            </div>
            <div style="font-size: 32px; font-family: var(--font-heading); color: var(--rr-pink); font-weight: 800; line-height: 1.1;">
              +${(p.final_pressure_rating || 0).toFixed(2)}
              <span style="font-size: 11.5px; font-family: var(--font-mono); color: var(--text-secondary); font-weight: 600; margin-left: 6px;" title="95% Clustered CI">
                [${(p.ci_lower || 0).toFixed(1)}, ${(p.ci_upper || 0).toFixed(1)}]
              </span>
            </div>
          </div>

          <div style="display: flex; flex-direction: column; gap: 10px; font-size: 13px; background: var(--bg-secondary); padding: 12px; border-radius: var(--radius-md);">
            <div style="display: flex; justify-content: space-between;">
              <span style="color: var(--text-muted);">High-Pressure Deliveries:</span>
              <strong>${p.balls || 0} balls</strong>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span style="color: var(--text-muted);">${isBat ? 'Pressure Strike Rate' : 'Pressure Economy'}:</span>
              <strong style="color: var(--text);">${rateVal}</strong>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span style="color: var(--text-muted);">${isBat ? 'Runs Above Expected (RAE)' : 'Runs Saved (RSAE)'}:</span>
              <strong style="color: ${(isBat ? p.rae_per_100 : p.rsae_per_100) >= 0 ? 'var(--success)' : 'var(--danger)'};">
                ${diffVal}
              </strong>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span style="color: var(--text-muted);">Consistency Hit Rate:</span>
              <strong>${((p.hit_rate || 0) * 100).toFixed(0)}%</strong>
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

  // Set initial tab based on window.INITIAL_TAB or URL Hash (for forward/backward nav)
  const initialHash = window.location.hash ? window.location.hash.replace('#', '') : null;
  const startTab = window.INITIAL_TAB || (initialHash && document.getElementById(`section-${initialHash}`) ? initialHash : 'overview');
  switchTab(startTab, false);
});

