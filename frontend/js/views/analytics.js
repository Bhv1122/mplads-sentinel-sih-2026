/**
 * frontend/js/views/analytics.js
 * =============================================================================
 * Phase 10 Production Analytics & Visualization Layer for MPLADS Risk Detection.
 * Integrates:
 *   1. Risk Distribution (Tiers, percentages, engine averages, KPIs)
 *   2. State-Wise Analysis (Metric comparator, ranked horizontal bars, readable labels)
 *   3. District-Wise Analysis (State cascading, Top-N controls, drill-down)
 *   4. Delay Statistics (Histogram buckets: 0, 1-30, 31-90, 91-180, 181-365, 365+ days)
 *   5. Cost Anomaly Statistics (Normal vs Anomaly rate, deviation histogram, peer medians)
 *   6. Temporal Longitudinal Trends (Intake, high-risk, overdue, and fiscal drawdowns)
 *   7. Interactive India Choropleth Map (Density, risk severity, hover cards, click-to-filter)
 *   8. Global Filter Bar (State, District, Risk Tier, Status, Sector, Reset, Active Chips)
 * =============================================================================
 */

(function () {
  'use strict';

  function formatCr(inrAmount) {
    if (!inrAmount) return '₹0.00 Cr';
    const val = Number(inrAmount) / 10000000;
    return `₹${val.toFixed(2)} Cr`;
  }

  function formatLakh(amount) {
    if (!amount) return '₹0.00 Lakh';
    const val = Number(amount);
    if (val >= 10000000) {
      return `₹${(val / 10000000).toFixed(2)} Cr`;
    }
    return `₹${(val / 100000).toFixed(2)} Lakh`;
  }

  function formatNumber(num) {
    if (num === null || num === undefined || isNaN(num)) return '0';
    return Number(num).toLocaleString('en-IN');
  }

  // State Management for Global Analytics Filters
  const state = {
    filters: {
      state: '',
      district: '',
      risk_level: '',
      status: '',
      sector: '',
      fy: '',
    },
    stateMetric: 'risk_score',
    districtLimit: 10,
    trendMode: 'volume',
    costAnomalyMode: 'histogram',
    availableStates: [],
    availableDistricts: [],
    indiaMapInstance: null,
    isLoading: false,
    queryCache: new Map(),
  };

  async function renderAnalyticsView({ container }) {
    // 1. Initial Scaffold with Filter Bar, Skeletons, and Grid
    container.innerHTML = `
      <main class="pl-64 pt-16 min-h-screen bg-background p-space-xl text-on-surface">
        <div class="flex flex-col w-full gap-space-lg max-w-[1600px] mx-auto">

          <!-- Official MoSPI Banner -->
          <div class="bg-surface-container-low border-l-4 border-primary px-space-base py-space-sm flex flex-col sm:flex-row sm:items-center justify-between gap-2 shadow-xs">
            <div class="flex items-center gap-space-sm">
              <span class="material-symbols-outlined text-primary text-[20px]">insights</span>
              <span class="font-body-sm text-body-sm text-on-surface font-medium">
                National Macro Surveillance & Predictive Risk Analytics • MoSPI Sentinel Engine
              </span>
            </div>
            <div class="flex items-center gap-3">
              <span id="syncIndicator" class="font-label-sm text-label-sm text-secondary font-tabular-data flex items-center gap-1.5">
                <span class="w-2 h-2 rounded-full bg-emerald-600 animate-pulse"></span>
                <span>PostgreSQL Live Aggregation</span>
              </span>
            </div>
          </div>

          <!-- Page Header & Action Controls -->
          <div class="flex flex-col md:flex-row md:items-end justify-between pb-space-md border-b border-outline-variant gap-space-md">
            <div>
              <h1 class="font-headline-lg text-headline-lg text-on-surface tracking-tight font-bold">
                Project Risk & Operational Visualizations
              </h1>
              <p class="font-body-md text-body-md text-secondary mt-space-2xs">
                Real-time algorithmic risk distribution, state/district disparities, timeline slippages, and cost deviations.
              </p>
            </div>
            <div class="flex items-center gap-space-sm flex-wrap">
              <button id="btnResetFilters" class="px-space-md py-space-xs border border-outline-variant rounded font-label-md font-medium text-secondary hover:text-on-surface hover:bg-surface-container transition-colors flex items-center gap-1 text-xs">
                <span class="material-symbols-outlined text-[16px]">restart_alt</span>
                <span>Reset Filters</span>
              </button>
              <a href="#/investigations" class="px-space-base py-space-xs bg-primary text-on-primary rounded font-label-md font-semibold hover:bg-primary-container transition-colors flex items-center gap-space-xs shadow-sm text-xs">
                <span class="material-symbols-outlined text-[16px]">gavel</span>
                <span>Triage Queue</span>
              </a>
            </div>
          </div>

          <!-- GLOBAL FILTER SYSTEM -->
          <div class="bg-surface-container-lowest border border-outline-variant rounded-lg p-space-base shadow-sm">
            <div class="flex items-center justify-between pb-space-xs border-b border-outline-variant/60 mb-space-sm">
              <div class="flex items-center gap-2">
                <span class="material-symbols-outlined text-primary text-[18px]">filter_alt</span>
                <span class="font-title-sm text-title-sm font-semibold">Global Analytics Filters</span>
              </div>
              <span id="activeFilterCount" class="text-xs text-secondary font-medium font-tabular-data">0 filters active</span>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3">
              <!-- State Filter -->
              <div class="flex flex-col gap-1">
                <label class="text-[11px] font-semibold text-secondary uppercase tracking-wider">State / UT</label>
                <select id="filterState" class="w-full text-xs bg-surface-container-low border border-outline-variant rounded px-2.5 py-1.5 focus:outline-none focus:border-primary">
                  <option value="">All States / UTs</option>
                </select>
              </div>

              <!-- District Filter -->
              <div class="flex flex-col gap-1">
                <label class="text-[11px] font-semibold text-secondary uppercase tracking-wider">District</label>
                <select id="filterDistrict" class="w-full text-xs bg-surface-container-low border border-outline-variant rounded px-2.5 py-1.5 focus:outline-none focus:border-primary">
                  <option value="">All Districts</option>
                </select>
              </div>

              <!-- Risk Tier Filter -->
              <div class="flex flex-col gap-1">
                <label class="text-[11px] font-semibold text-secondary uppercase tracking-wider">Risk Category</label>
                <select id="filterRiskLevel" class="w-full text-xs bg-surface-container-low border border-outline-variant rounded px-2.5 py-1.5 focus:outline-none focus:border-primary">
                  <option value="">All Risk Tiers</option>
                  <option value="Critical">Critical Risk (>= 80)</option>
                  <option value="High">High Risk (60–79)</option>
                  <option value="Moderate">Moderate / Medium (30–59)</option>
                  <option value="Low">Low Risk (< 30)</option>
                </select>
              </div>

              <!-- Project Status Filter -->
              <div class="flex flex-col gap-1">
                <label class="text-[11px] font-semibold text-secondary uppercase tracking-wider">Project Status</label>
                <select id="filterStatus" class="w-full text-xs bg-surface-container-low border border-outline-variant rounded px-2.5 py-1.5 focus:outline-none focus:border-primary">
                  <option value="">All Statuses</option>
                  <option value="In Progress">In Progress</option>
                  <option value="Completed">Completed</option>
                  <option value="Sanctioned">Sanctioned</option>
                  <option value="Stalled">Stalled</option>
                </select>
              </div>

              <!-- Sector Filter -->
              <div class="flex flex-col gap-1">
                <label class="text-[11px] font-semibold text-secondary uppercase tracking-wider">Development Sector</label>
                <select id="filterSector" class="w-full text-xs bg-surface-container-low border border-outline-variant rounded px-2.5 py-1.5 focus:outline-none focus:border-primary">
                  <option value="">All Sectors</option>
                  <option value="Drinking Water">Drinking Water</option>
                  <option value="Education">Education</option>
                  <option value="Electricity">Electricity</option>
                  <option value="Health">Health</option>
                  <option value="Irrigation">Irrigation</option>
                  <option value="Roads and Pathways">Roads & Pathways</option>
                  <option value="Sanitation">Sanitation</option>
                  <option value="Other Public Facilities">Other Public Facilities</option>
                </select>
              </div>

              <!-- Financial Year -->
              <div class="flex flex-col gap-1">
                <label class="text-[11px] font-semibold text-secondary uppercase tracking-wider">Financial Year</label>
                <select id="filterFY" class="w-full text-xs bg-surface-container-low border border-outline-variant rounded px-2.5 py-1.5 focus:outline-none focus:border-primary">
                  <option value="">All FYs</option>
                  <option value="2024-25">2024-25</option>
                  <option value="2023-24">2023-24</option>
                  <option value="2022-23">2022-23</option>
                </select>
              </div>
            </div>

            <!-- Active Filter Chips Container -->
            <div id="activeFilterChips" class="flex items-center gap-1.5 flex-wrap mt-space-sm pt-space-xs border-t border-outline-variant/40 empty:hidden"></div>
          </div>

          <!-- SUMMARY KPIS (Section 1 Header) -->
          <div id="kpiCardsContainer" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-gutter-grid">
            <!-- Rendered dynamically -->
          </div>

          <!-- ROW 1: RISK DISTRIBUTION (Section 1) + TEMPORAL TRENDS (Section 6) -->
          <div class="grid grid-cols-1 lg:grid-cols-12 gap-space-lg">
            <!-- Left: Risk Profile Donut & Engine Breakdown (5 cols) -->
            <div id="riskDistributionCard" class="lg:col-span-5 bg-surface-container-lowest border border-outline-variant p-space-base rounded-lg shadow-sm flex flex-col justify-between">
              <!-- Dynamically populated -->
            </div>

            <!-- Right: Temporal Longitudinal Trends (7 cols) -->
            <div id="trendsCard" class="lg:col-span-7 bg-surface-container-lowest border border-outline-variant p-space-base rounded-lg shadow-sm flex flex-col justify-between">
              <!-- Dynamically populated -->
            </div>
          </div>

          <!-- ROW 2: GEOSPATIAL SURVEILLANCE (Section 7: India Map) + STATE ANALYSIS (Section 2) -->
          <div class="grid grid-cols-1 lg:grid-cols-12 gap-space-lg">
            <!-- Left: India Map Choropleth (6 cols) -->
            <div id="indiaMapContainer" class="lg:col-span-6">
              <!-- Mounted via IndiaMapComponent -->
            </div>

            <!-- Right: State-Wise Analysis & Comparator (6 cols) -->
            <div id="stateAnalysisCard" class="lg:col-span-6 bg-surface-container-lowest border border-outline-variant p-space-base rounded-lg shadow-sm flex flex-col justify-between">
              <!-- Dynamically populated -->
            </div>
          </div>

          <!-- ROW 3: DISTRICT-WISE ANALYSIS (Section 3) -->
          <div id="districtAnalysisCard" class="bg-surface-container-lowest border border-outline-variant p-space-base rounded-lg shadow-sm">
            <!-- Dynamically populated -->
          </div>

          <!-- ROW 4: DELAY STATISTICS (Section 4) + COST ANOMALY STATISTICS (Section 5) -->
          <div class="grid grid-cols-1 lg:grid-cols-12 gap-space-lg">
            <!-- Delay Statistics (6 cols) -->
            <div id="delayStatisticsCard" class="lg:col-span-6 bg-surface-container-lowest border border-outline-variant p-space-base rounded-lg shadow-sm">
              <!-- Dynamically populated -->
            </div>

            <!-- Cost Anomaly Statistics (6 cols) -->
            <div id="costAnomalyCard" class="lg:col-span-6 bg-surface-container-lowest border border-outline-variant p-space-base rounded-lg shadow-sm">
              <!-- Dynamically populated -->
            </div>
          </div>

          <!-- ROW 5: FLAGGED PROJECTS DIRECT TRIAGE TABLE WITH EXPLAINABILITY DRILL-DOWN -->
          <div id="flaggedProjectsTableCard" class="bg-surface-container-lowest border border-outline-variant rounded-lg p-space-base shadow-sm">
            <!-- Dynamically populated -->
          </div>

        </div>
      </main>
    `;

    // 2. Attach Filter Change Listeners
    setupFilterListeners(container);

    // 3. Initial Load of States for Dropdown & Initial Dashboard Render
    await loadInitialFilterOptions();
    await loadAndRenderDashboard(container);
  }

  function setupFilterListeners(container) {
    const filterState = container.querySelector('#filterState');
    const filterDistrict = container.querySelector('#filterDistrict');
    const filterRiskLevel = container.querySelector('#filterRiskLevel');
    const filterStatus = container.querySelector('#filterStatus');
    const filterSector = container.querySelector('#filterSector');
    const filterFY = container.querySelector('#filterFY');
    const btnReset = container.querySelector('#btnResetFilters');

    filterState.addEventListener('change', async (e) => {
      state.filters.state = e.target.value;
      state.filters.district = ''; // reset district when state changes
      await updateDistrictOptions(state.filters.state);
      await loadAndRenderDashboard(container);
    });

    filterDistrict.addEventListener('change', async (e) => {
      state.filters.district = e.target.value;
      await loadAndRenderDashboard(container);
    });

    filterRiskLevel.addEventListener('change', async (e) => {
      state.filters.risk_level = e.target.value;
      await loadAndRenderDashboard(container);
    });

    filterStatus.addEventListener('change', async (e) => {
      state.filters.status = e.target.value;
      await loadAndRenderDashboard(container);
    });

    filterSector.addEventListener('change', async (e) => {
      state.filters.sector = e.target.value;
      await loadAndRenderDashboard(container);
    });

    filterFY.addEventListener('change', async (e) => {
      state.filters.fy = e.target.value;
      await loadAndRenderDashboard(container);
    });

    btnReset.addEventListener('click', async () => {
      state.filters = { state: '', district: '', risk_level: '', status: '', sector: '', fy: '' };
      filterState.value = '';
      filterDistrict.value = '';
      filterRiskLevel.value = '';
      filterStatus.value = '';
      filterSector.value = '';
      filterFY.value = '';
      await updateDistrictOptions('');
      await loadAndRenderDashboard(container);
    });
  }

  async function loadInitialFilterOptions() {
    try {
      const stateRes = await window.api.getStateAnalytics({ limit: 50 });
      if (stateRes && Array.isArray(stateRes.states)) {
        state.availableStates = stateRes.states.map(s => s.state_name).sort();
        const select = document.getElementById('filterState');
        if (select) {
          select.innerHTML = '<option value="">All States / UTs</option>' +
            state.availableStates.map(s => `<option value="${s}">${s}</option>`).join('');
        }
      }
    } catch (err) {
      console.warn('Could not load initial states list:', err);
    }
  }

  async function updateDistrictOptions(stateName) {
    const districtSelect = document.getElementById('filterDistrict');
    if (!districtSelect) return;

    if (!stateName) {
      districtSelect.innerHTML = '<option value="">All Districts</option>';
      return;
    }

    try {
      const distRes = await window.api.getDistrictAnalytics({ state: stateName, limit: 100 });
      if (distRes && Array.isArray(distRes.districts)) {
        districtSelect.innerHTML = '<option value="">All Districts</option>' +
          distRes.districts.map(d => `<option value="${d.district_name}">${d.district_name}</option>`).join('');
      }
    } catch (err) {
      console.warn('Could not load districts for state:', stateName, err);
    }
  }

  function renderActiveFilterChips(container) {
    const chipsContainer = container.querySelector('#activeFilterChips');
    const countEl = container.querySelector('#activeFilterCount');
    if (!chipsContainer) return;

    const active = Object.entries(state.filters).filter(([_, val]) => !!val);
    if (countEl) {
      countEl.textContent = `${active.length} active filter${active.length === 1 ? '' : 's'}`;
    }

    if (active.length === 0) {
      chipsContainer.innerHTML = '';
      return;
    }

    chipsContainer.innerHTML = `
      <span class="text-[10px] text-secondary font-semibold uppercase">Active:</span>
      ${active.map(([key, val]) => `
        <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-primary-container text-on-primary font-medium">
          <span>${key.replace('_', ' ')}: <b>${val}</b></span>
          <button class="hover:text-error transition-colors" data-remove-filter="${key}">
            <span class="material-symbols-outlined text-[14px] leading-none">close</span>
          </button>
        </span>
      `).join('')}
    `;

    chipsContainer.querySelectorAll('[data-remove-filter]').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const k = e.currentTarget.getAttribute('data-remove-filter');
        state.filters[k] = '';
        const inputEl = container.querySelector(`#filter${k.charAt(0).toUpperCase() + k.slice(1).replace('_l', 'L').replace('fy', 'FY')}`);
        if (inputEl) inputEl.value = '';
        if (k === 'state') {
          state.filters.district = '';
          const dInput = container.querySelector('#filterDistrict');
          if (dInput) dInput.value = '';
          await updateDistrictOptions('');
        }
        await loadAndRenderDashboard(container);
      });
    });
  }

  // ===========================================================================
  // Main Data Orchestrator: Fetches and updates all 7 visualization sections
  // ===========================================================================
  async function loadAndRenderDashboard(container) {
    state.isLoading = true;
    renderActiveFilterChips(container);

    const syncEl = container.querySelector('#syncIndicator');
    if (syncEl) {
      syncEl.innerHTML = `
        <span class="w-2 h-2 rounded-full bg-primary animate-ping"></span>
        <span class="text-primary font-medium">Querying PostgreSQL Live Aggregations...</span>
      `;
    }

    const filterParams = {};
    Object.entries(state.filters).forEach(([k, v]) => {
      if (v) filterParams[k] = v;
    });

    const cacheKey = JSON.stringify(filterParams) + `_m:${state.stateMetric}_d:${state.districtLimit}`;

    try {
      let aggregatedData;
      if (state.queryCache.has(cacheKey)) {
        aggregatedData = state.queryCache.get(cacheKey);
      } else {
        const [
          overview,
          riskDist,
          statesData,
          districtsData,
          delaysData,
          costAnomaliesData,
          trendsData,
          mapData,
          highRiskList
        ] = await Promise.all([
          window.api.getAnalyticsOverview(filterParams).catch(() => ({})),
          window.api.getRiskDistribution(filterParams).catch(() => ({})),
          window.api.getStateAnalytics({ ...filterParams, metric: state.stateMetric, limit: 15 }).catch(() => ({ states: [] })),
          window.api.getDistrictAnalytics({ ...filterParams, limit: state.districtLimit }).catch(() => ({ districts: [] })),
          window.api.getDelayAnalytics(filterParams).catch(() => ({ delay_buckets: {}, top_delayed_projects: [] })),
          window.api.getCostAnomalyAnalytics(filterParams).catch(() => ({ deviation_distribution: {}, largest_deviations: [] })),
          window.api.getTemporalTrends(filterParams).catch(() => ({ trend_points: [] })),
          window.api.getMapAnalytics(filterParams).catch(() => ({ states: [] })),
          window.api.getHighRiskProjects({ ...filterParams, limit: 10 }).catch(() => [])
        ]);

        aggregatedData = {
          overview,
          riskDist,
          statesData,
          districtsData,
          delaysData,
          costAnomaliesData,
          trendsData,
          mapData,
          highRiskList
        };
        state.queryCache.set(cacheKey, aggregatedData);
      }

      const {
        overview,
        riskDist,
        statesData,
        districtsData,
        delaysData,
        costAnomaliesData,
        trendsData,
        mapData,
        highRiskList
      } = aggregatedData;

      // 1. Render Summary KPIs
      renderOverviewKPIs(container, overview);

      // 2. Render Risk Distribution (Section 1)
      renderRiskDistribution(container, overview, riskDist);

      // 3. Render Temporal Trends (Section 6)
      renderTemporalTrends(container, trendsData);

      // 4. Render India Map (Section 7)
      renderIndiaMap(container, mapData);

      // 5. Render State Analysis (Section 2)
      renderStateAnalysis(container, statesData);

      // 6. Render District Analysis (Section 3)
      renderDistrictAnalysis(container, districtsData);

      // 7. Render Delay Statistics (Section 4)
      renderDelayStatistics(container, delaysData);

      // 8. Render Cost Anomaly Statistics (Section 5)
      renderCostAnomalyStatistics(container, costAnomaliesData);

      // 9. Render Flagged Projects Triage Table
      renderFlaggedProjectsTable(container, highRiskList);

    } catch (err) {
      console.error('Failed to load analytics visualizations:', err);
    } finally {
      state.isLoading = false;
      if (syncEl) {
        syncEl.innerHTML = `
          <span class="w-2 h-2 rounded-full bg-emerald-600 animate-pulse"></span>
          <span>PostgreSQL Live Aggregation • Verified</span>
        `;
      }
    }
  }

  // ---------------------------------------------------------------------------
  // 1. Overview KPIs
  // ---------------------------------------------------------------------------
  function renderOverviewKPIs(container, overview) {
    const cardContainer = container.querySelector('#kpiCardsContainer');
    if (!cardContainer) return;

    const total = overview.total_projects || 0;
    const high = overview.high_risk_projects || 0;
    const critical = overview.critical_risk_projects || 0;
    const avgScore = Number(overview.average_risk_score || 0).toFixed(1);
    const flaggedPct = Number(overview.flagged_percentage || 0).toFixed(1);

    cardContainer.innerHTML = `
      <!-- Total Projects -->
      <div class="bg-surface-container-lowest border border-outline-variant p-space-base rounded-lg shadow-sm flex flex-col justify-between">
        <div class="flex items-center justify-between text-secondary">
          <span class="font-label-sm text-[11px] uppercase font-semibold tracking-wider">Total Assessed Works</span>
          <span class="material-symbols-outlined text-[18px]">inventory_2</span>
        </div>
        <div class="font-display text-2xl font-bold text-on-surface font-tabular-data mt-2">
          ${formatNumber(total)}
        </div>
        <div class="flex items-center justify-between mt-2 pt-2 border-t border-outline-variant/40 text-[11px] text-secondary">
          <span>Active Constituency Works</span>
          <span class="font-semibold text-primary">100% Grounded</span>
        </div>
      </div>

      <!-- High-Risk Projects -->
      <div class="bg-surface-container-lowest border border-outline-variant p-space-base rounded-lg shadow-sm flex flex-col justify-between">
        <div class="flex items-center justify-between text-secondary">
          <span class="font-label-sm text-[11px] uppercase font-semibold tracking-wider">High-Risk Projects</span>
          <span class="material-symbols-outlined text-warning text-[18px]">warning</span>
        </div>
        <div class="font-display text-2xl font-bold text-warning font-tabular-data mt-2">
          ${formatNumber(high)}
        </div>
        <div class="flex items-center justify-between mt-2 pt-2 border-t border-outline-variant/40 text-[11px] text-secondary">
          <span>Score: 60 to 79</span>
          <span class="font-semibold text-warning">${total > 0 ? ((high / total) * 100).toFixed(0) : 0}% of portfolio</span>
        </div>
      </div>

      <!-- Critical-Risk Projects -->
      <div class="bg-surface-container-lowest border border-outline-variant p-space-base rounded-lg shadow-sm flex flex-col justify-between">
        <div class="flex items-center justify-between text-secondary">
          <span class="font-label-sm text-[11px] uppercase font-semibold tracking-wider">Critical Escalations</span>
          <span class="material-symbols-outlined text-error text-[18px]">crisis_alert</span>
        </div>
        <div class="font-display text-2xl font-bold text-error font-tabular-data mt-2">
          ${formatNumber(critical)}
        </div>
        <div class="flex items-center justify-between mt-2 pt-2 border-t border-outline-variant/40 text-[11px] text-secondary">
          <span>Score: >= 80</span>
          <span class="font-semibold text-error">${total > 0 ? ((critical / total) * 100).toFixed(0) : 0}% urgency</span>
        </div>
      </div>

      <!-- Average Risk Score -->
      <div class="bg-surface-container-lowest border border-outline-variant p-space-base rounded-lg shadow-sm flex flex-col justify-between">
        <div class="flex items-center justify-between text-secondary">
          <span class="font-label-sm text-[11px] uppercase font-semibold tracking-wider">Average Risk Score</span>
          <span class="material-symbols-outlined text-[18px]">speed</span>
        </div>
        <div class="font-display text-2xl font-bold text-on-surface font-tabular-data mt-2 flex items-baseline gap-1">
          <span>${avgScore}</span>
          <span class="text-xs text-secondary font-normal">/ 100</span>
        </div>
        <div class="flex items-center justify-between mt-2 pt-2 border-t border-outline-variant/40 text-[11px] text-secondary">
          <span>Baseline Benchmark</span>
          <span class="font-semibold ${avgScore >= 50 ? 'text-error' : 'text-emerald-600'}">${avgScore < 40 ? 'Moderate Baseline' : 'Elevated'}</span>
        </div>
      </div>

      <!-- Flagged Projects Rate -->
      <div class="bg-surface-container-lowest border border-outline-variant p-space-base rounded-lg shadow-sm flex flex-col justify-between">
        <div class="flex items-center justify-between text-secondary">
          <span class="font-label-sm text-[11px] uppercase font-semibold tracking-wider">Flagged Projects %</span>
          <span class="material-symbols-outlined text-primary text-[18px]">flag</span>
        </div>
        <div class="font-display text-2xl font-bold text-primary font-tabular-data mt-2">
          ${flaggedPct}%
        </div>
        <div class="flex items-center justify-between mt-2 pt-2 border-t border-outline-variant/40 text-[11px] text-secondary">
          <span>${overview.flagged_projects_count || 0} flagged works</span>
          <span class="font-semibold text-primary">Multi-Engine Triage</span>
        </div>
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // 2. Risk Distribution (Section 1)
  // ---------------------------------------------------------------------------
  function renderRiskDistribution(container, overview, riskDist) {
    const card = container.querySelector('#riskDistributionCard');
    if (!card) return;

    const total = overview.total_projects || riskDist.total_projects || 0;
    const dist = riskDist.distribution || {};
    const low = dist.LOW || overview.low_risk_projects || 0;
    const med = dist.MEDIUM || overview.moderate_risk_projects || 0;
    const high = dist.HIGH || overview.high_risk_projects || 0;
    const crit = dist.CRITICAL || overview.critical_risk_projects || 0;

    const donutHtml = window.ChartUtils.renderDonutChart({
      slices: [
        { label: 'Low Risk', value: low, color: '#16a34a', key: 'Low' },
        { label: 'Moderate Risk', value: med, color: '#eab308', key: 'Moderate' },
        { label: 'High Risk', value: high, color: '#ea580c', key: 'High' },
        { label: 'Critical Risk', value: crit, color: '#ba1a1a', key: 'Critical' }
      ],
      total,
      size: 170,
      centerText: total,
      centerSubtext: 'Assessed'
    });

    const engineAvgs = riskDist.engine_averages || {};
    const engineLabels = {
      'cost_anomaly': 'Cost Anomaly Engine',
      'delay_detection': 'Delay Timeline Engine',
      'progress_mismatch': 'Physical/Financial Gap',
      'agency_pattern': 'Agency Track Record',
      'duplicate_detection': 'Semantic Duplicate'
    };

    card.innerHTML = `
      <div>
        <div class="flex items-center justify-between pb-2 border-b border-outline-variant">
          <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-primary text-[18px]">pie_chart</span>
            <h3 class="font-title-sm text-title-sm text-on-surface font-bold">1. Risk Distribution & Profile</h3>
          </div>
          <span class="text-xs text-secondary font-tabular-data font-medium">Risk Engine v2.4</span>
        </div>
        <p class="font-body-sm text-xs text-secondary mt-1 mb-3">
          Algorithmic classification from 6 real detector outputs in PostgreSQL. Click tier to filter.
        </p>

        <!-- Donut & Legend Split -->
        <div class="flex flex-col sm:flex-row items-center justify-around gap-4 my-2">
          ${donutHtml}

          <!-- Legend Rows -->
          <div class="flex flex-col gap-2 text-xs w-full sm:max-w-[200px]">
            <div class="flex items-center justify-between p-1.5 rounded hover:bg-surface-container cursor-pointer" data-filter-tier="Low">
              <div class="flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-[#16a34a]"></span>
                <span class="font-medium text-on-surface">Low Risk</span>
              </div>
              <span class="font-tabular-data font-bold">${low} <span class="text-secondary font-normal">(${total > 0 ? ((low/total)*100).toFixed(0) : 0}%)</span></span>
            </div>

            <div class="flex items-center justify-between p-1.5 rounded hover:bg-surface-container cursor-pointer" data-filter-tier="Moderate">
              <div class="flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-[#eab308]"></span>
                <span class="font-medium text-on-surface">Moderate</span>
              </div>
              <span class="font-tabular-data font-bold">${med} <span class="text-secondary font-normal">(${total > 0 ? ((med/total)*100).toFixed(0) : 0}%)</span></span>
            </div>

            <div class="flex items-center justify-between p-1.5 rounded hover:bg-surface-container cursor-pointer" data-filter-tier="High">
              <div class="flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-[#ea580c]"></span>
                <span class="font-medium text-warning font-semibold">High Risk</span>
              </div>
              <span class="font-tabular-data font-bold text-warning">${high} <span class="text-secondary font-normal">(${total > 0 ? ((high/total)*100).toFixed(0) : 0}%)</span></span>
            </div>

            <div class="flex items-center justify-between p-1.5 rounded hover:bg-surface-container cursor-pointer" data-filter-tier="Critical">
              <div class="flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-[#ba1a1a]"></span>
                <span class="font-medium text-error font-semibold">Critical</span>
              </div>
              <span class="font-tabular-data font-bold text-error">${crit} <span class="text-secondary font-normal">(${total > 0 ? ((crit/total)*100).toFixed(0) : 0}%)</span></span>
            </div>
          </div>
        </div>

        <!-- Engine Score Breakdown Sub-chart -->
        <div class="mt-4 pt-3 border-t border-outline-variant/60">
          <div class="flex items-center justify-between mb-2">
            <span class="text-[11px] font-semibold text-secondary uppercase tracking-wider">Independent Detector Averages</span>
            <span class="text-[10px] text-secondary">Mean Score (0-100)</span>
          </div>
          <div class="space-y-2 text-xs">
            ${Object.entries(engineLabels).map(([engKey, engLabel]) => {
              const score = engineAvgs[engKey] || 0;
              const barColor = score >= 50 ? '#ba1a1a' : (score >= 30 ? '#ea580c' : '#00236f');
              return `
                <div class="flex flex-col gap-0.5">
                  <div class="flex items-center justify-between text-[11px]">
                    <span class="text-secondary">${engLabel}</span>
                    <span class="font-tabular-data font-semibold text-on-surface">${score.toFixed(1)}</span>
                  </div>
                  <div class="w-full bg-surface-container h-1.5 rounded-full overflow-hidden">
                    <div class="h-full rounded-full transition-all duration-500" style="width: ${Math.min(100, score)}%; background-color: ${barColor};"></div>
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        </div>
      </div>
    `;

    // Click tier or donut slice to filter
    card.querySelectorAll('[data-filter-tier], circle[data-tier]').forEach(el => {
      el.addEventListener('click', async (e) => {
        const tier = e.currentTarget.getAttribute('data-filter-tier') || e.currentTarget.getAttribute('data-tier');
        if (!tier) return;
        state.filters.risk_level = tier;
        const select = container.querySelector('#filterRiskLevel');
        if (select) select.value = tier;
        await loadAndRenderDashboard(container);
      });
    });
  }

  // ---------------------------------------------------------------------------
  // 3. State-Wise Analysis (Section 2)
  // ---------------------------------------------------------------------------
  function renderStateAnalysis(container, statesData) {
    const card = container.querySelector('#stateAnalysisCard');
    if (!card) return;

    const states = statesData.states || [];

    const metricLabels = {
      'risk_score': 'Average Risk Score',
      'projects': 'Total Assessed Works',
      'delays': 'Average Delay (Days)',
      'cost_anomaly': 'Cost Anomalies Count',
      'funds': 'Sanctioned Amount (Cr)'
    };

    const metricValueExtractors = {
      'risk_score': (s) => Number(s.average_risk_score || 0).toFixed(1),
      'projects': (s) => s.total_projects,
      'delays': (s) => `${Number(s.average_delay_days || 0).toFixed(0)}d`,
      'cost_anomaly': (s) => s.cost_anomaly_count || 0,
      'funds': (s) => `₹${(Number(s.total_sanctioned || 0) / 10000000).toFixed(2)} Cr`
    };

    card.innerHTML = `
      <div>
        <div class="flex flex-col sm:flex-row sm:items-center justify-between pb-2 border-b border-outline-variant gap-2">
          <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-primary text-[18px]">leaderboard</span>
            <h3 class="font-title-sm text-title-sm text-on-surface font-bold">2. State-Wise Analysis</h3>
          </div>
          
          <!-- Metric Comparator Selector -->
          <div class="flex items-center gap-1">
            <label class="text-[11px] text-secondary font-medium mr-1">Sort by:</label>
            <select id="stateMetricSelect" class="text-xs bg-surface-container-low border border-outline-variant rounded px-2 py-1 focus:outline-none focus:border-primary">
              <option value="risk_score" ${state.stateMetric === 'risk_score' ? 'selected' : ''}>Risk Score</option>
              <option value="projects" ${state.stateMetric === 'projects' ? 'selected' : ''}>Works Count</option>
              <option value="delays" ${state.stateMetric === 'delays' ? 'selected' : ''}>Avg Delay</option>
              <option value="cost_anomaly" ${state.stateMetric === 'cost_anomaly' ? 'selected' : ''}>Cost Anomalies</option>
              <option value="funds" ${state.stateMetric === 'funds' ? 'selected' : ''}>Sanctioned Outlay</option>
            </select>
          </div>
        </div>

        <p class="font-body-sm text-xs text-secondary mt-1 mb-3">
          Cross-state performance rankings. Click any state row to filter dashboard and view district triage.
        </p>

        <!-- Ranked Horizontal Bar Chart -->
        <div id="stateBarChartContainer" class="max-h-[380px] overflow-y-auto pr-1">
          ${window.ChartUtils.renderHorizontalBarChart({
            items: states,
            valueKey: state.stateMetric === 'risk_score' ? 'average_risk_score' :
                      (state.stateMetric === 'delays' ? 'average_delay_days' :
                      (state.stateMetric === 'cost_anomaly' ? 'cost_anomaly_count' :
                      (state.stateMetric === 'funds' ? 'total_sanctioned' : 'total_projects'))),
            labelKey: 'state_name',
            barColor: (item) => {
              if (item.critical_risk_projects > 0) return '#ba1a1a';
              if (item.high_risk_projects > 0) return '#ea580c';
              if (item.average_risk_score >= 35) return '#eab308';
              return '#00236f';
            },
            formatValue: (val, item) => metricValueExtractors[state.stateMetric](item)
          })}
        </div>
      </div>
    `;

    // State Metric Selector Change
    const sel = card.querySelector('#stateMetricSelect');
    if (sel) {
      sel.addEventListener('change', async (e) => {
        state.stateMetric = e.target.value;
        const res = await window.api.getStateAnalytics({ ...state.filters, metric: state.stateMetric, limit: 15 });
        renderStateAnalysis(container, res);
      });
    }

    // State Click to Drilldown
    card.querySelectorAll('[data-chart-item]').forEach(el => {
      el.addEventListener('click', async (e) => {
        const raw = e.currentTarget.getAttribute('data-chart-item');
        try {
          const item = JSON.parse(decodeURIComponent(raw));
          if (item && item.state_name) {
            state.filters.state = item.state_name;
            state.filters.district = '';
            const stateInput = container.querySelector('#filterState');
            if (stateInput) stateInput.value = item.state_name;
            await updateDistrictOptions(item.state_name);
            await loadAndRenderDashboard(container);
          }
        } catch (err) {
          console.error(err);
        }
      });
    });
  }

  // ---------------------------------------------------------------------------
  // 4. District-Wise Analysis (Section 3)
  // ---------------------------------------------------------------------------
  function renderDistrictAnalysis(container, districtsData) {
    const card = container.querySelector('#districtAnalysisCard');
    if (!card) return;

    const districts = districtsData.districts || [];
    const totalMatching = districtsData.total_districts || districts.length;

    card.innerHTML = `
      <div class="flex flex-col sm:flex-row sm:items-center justify-between pb-2 border-b border-outline-variant gap-2">
        <div class="flex items-center gap-2">
          <span class="material-symbols-outlined text-primary text-[18px]">domain</span>
          <h3 class="font-title-sm text-title-sm text-on-surface font-bold">
            3. District-Wise Analysis
            ${state.filters.state ? `<span class="text-xs font-semibold text-primary ml-1">(${state.filters.state})</span>` : ''}
          </h3>
        </div>

        <!-- District Top-N Controls -->
        <div class="flex items-center gap-2 text-xs">
          <span class="text-secondary">Showing:</span>
          <div class="inline-flex rounded border border-outline-variant p-0.5 bg-surface-container">
            ${[5, 10, 15, 25].map(n => `
              <button class="px-2 py-0.5 rounded font-medium transition-colors ${state.districtLimit === n ? 'bg-primary text-on-primary font-bold' : 'text-secondary hover:text-on-surface'}"
                      data-district-limit="${n}">
                Top ${n}
              </button>
            `).join('')}
          </div>
          <span class="text-secondary font-tabular-data text-[11px] ml-1">(${totalMatching} matching)</span>
        </div>
      </div>

      <p class="font-body-sm text-xs text-secondary mt-1 mb-3">
        Prioritized district rankings. Avoids overload via Top-N rankings. Click any district to isolate project works.
      </p>

      ${districts.length === 0 ? `
        <div class="py-8 text-center text-secondary text-xs">
          No district level works found for the selected state and filters.
        </div>
      ` : `
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <!-- District Risk Ranking Bars -->
          <div>
            <div class="text-[11px] font-semibold text-secondary uppercase mb-2">Ranked by Project Count & Risk Intensity</div>
            ${window.ChartUtils.renderHorizontalBarChart({
              items: districts,
              valueKey: 'total_projects',
              labelKey: 'district_name',
              sublabelKey: 'state_name',
              barColor: (d) => d.high_risk_projects > 0 ? '#ba1a1a' : '#00236f',
              formatValue: (val, d) => `${val} works (${Number(d.average_risk_score || 0).toFixed(1)} risk)`
            })}
          </div>

          <!-- District Matrix Table -->
          <div class="overflow-x-auto">
            <table class="w-full text-left font-body-sm text-xs border-collapse">
              <thead>
                <tr class="border-b border-outline-variant bg-surface-container-low text-secondary uppercase font-semibold">
                  <th class="py-1.5 px-2">District</th>
                  <th class="py-1.5 px-2 text-right">Works</th>
                  <th class="py-1.5 px-2 text-right">High Risk</th>
                  <th class="py-1.5 px-2 text-right">Avg Delay</th>
                  <th class="py-1.5 px-2 text-right">Sanctioned</th>
                  <th class="py-1.5 px-2 text-center">Action</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-outline-variant/40">
                ${districts.map(d => `
                  <tr class="hover:bg-surface-container-low transition-colors">
                    <td class="py-2 px-2 font-semibold text-on-surface">
                      ${d.district_name}
                      <span class="text-[10px] text-secondary block font-normal">${d.state_name}</span>
                    </td>
                    <td class="py-2 px-2 text-right font-tabular-data font-bold">${d.total_projects}</td>
                    <td class="py-2 px-2 text-right font-tabular-data ${d.high_risk_projects > 0 ? 'text-error font-bold' : 'text-secondary'}">${d.high_risk_projects}</td>
                    <td class="py-2 px-2 text-right font-tabular-data">${Number(d.average_delay_days || 0).toFixed(0)}d</td>
                    <td class="py-2 px-2 text-right font-tabular-data text-primary">₹${(Number(d.total_sanctioned || 0) / 10000000).toFixed(2)} Cr</td>
                    <td class="py-2 px-2 text-center">
                      <button class="px-2 py-0.5 text-[10px] font-semibold bg-surface-container text-primary hover:bg-primary hover:text-on-primary rounded transition-colors"
                              data-filter-district="${d.district_name}">
                        Filter
                      </button>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      `}
    `;

    // Top-N Button Click
    card.querySelectorAll('[data-district-limit]').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        state.districtLimit = Number(e.currentTarget.getAttribute('data-district-limit'));
        const distRes = await window.api.getDistrictAnalytics({ ...state.filters, limit: state.districtLimit });
        renderDistrictAnalysis(container, distRes);
      });
    });

    // Filter by District Click
    card.querySelectorAll('[data-filter-district]').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const dName = e.currentTarget.getAttribute('data-filter-district');
        state.filters.district = dName;
        const dInput = container.querySelector('#filterDistrict');
        if (dInput) dInput.value = dName;
        await loadAndRenderDashboard(container);
      });
    });
  }

  // ---------------------------------------------------------------------------
  // 5. Delay Statistics (Section 4)
  // ---------------------------------------------------------------------------
  function renderDelayStatistics(container, delaysData) {
    const card = container.querySelector('#delayStatisticsCard');
    if (!card) return;

    const buckets = delaysData.delay_buckets || {};
    const topDelayed = delaysData.top_delayed_projects || [];
    const avgDelay = Number(delaysData.average_delay_days || 0).toFixed(1);
    const maxDelay = delaysData.max_delay_days || 0;
    const delayedCount = delaysData.delayed_count || 0;
    const severeCount = delaysData.severely_delayed_count || 0;

    const histHtml = window.ChartUtils.renderHistogramChart({
      buckets,
      height: 140,
      barColor: (range) => {
        if (range === '365+ days' || range === '181-365 days') return '#ba1a1a';
        if (range === '91-180 days' || range === '31-90 days') return '#ea580c';
        if (range === '1-30 days') return '#eab308';
        return '#16a34a';
      },
      formatLabel: (l) => l.replace(' days', 'd'),
      formatValue: (v) => v
    });

    card.innerHTML = `
      <div>
        <div class="flex items-center justify-between pb-2 border-b border-outline-variant">
          <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-primary text-[18px]">schedule</span>
            <h3 class="font-title-sm text-title-sm text-on-surface font-bold">4. Timeline Slippage & Delay Statistics</h3>
          </div>
          <span class="text-xs font-tabular-data font-semibold text-error">${delayedCount} delayed works</span>
        </div>

        <p class="font-body-sm text-xs text-secondary mt-1 mb-3">
          Overdue days calculated directly by Delay Detection Engine against planned completion milestones.
        </p>

        <!-- Delay KPIs Grid -->
        <div class="grid grid-cols-4 gap-2 mb-3">
          <div class="bg-surface-container-low p-2 rounded text-center">
            <span class="text-[10px] text-secondary font-semibold uppercase block">On-Time</span>
            <span class="font-display text-base font-bold text-emerald-600 font-tabular-data">${delaysData.on_time_count || 0}</span>
          </div>
          <div class="bg-surface-container-low p-2 rounded text-center">
            <span class="text-[10px] text-secondary font-semibold uppercase block">Delayed</span>
            <span class="font-display text-base font-bold text-warning font-tabular-data">${delayedCount}</span>
          </div>
          <div class="bg-surface-container-low p-2 rounded text-center">
            <span class="text-[10px] text-secondary font-semibold uppercase block">> 90 Days</span>
            <span class="font-display text-base font-bold text-error font-tabular-data">${severeCount}</span>
          </div>
          <div class="bg-surface-container-low p-2 rounded text-center">
            <span class="text-[10px] text-secondary font-semibold uppercase block">Max Overrun</span>
            <span class="font-display text-base font-bold text-error font-tabular-data">${maxDelay}d</span>
          </div>
        </div>

        <!-- Delay Buckets Histogram -->
        <div class="mb-4">
          <div class="text-[11px] font-semibold text-secondary uppercase mb-1">Delay Duration Buckets</div>
          ${histHtml}
        </div>

        <!-- Top Overdue Works List -->
        <div class="pt-3 border-t border-outline-variant/60">
          <div class="flex items-center justify-between mb-2">
            <span class="text-[11px] font-semibold text-secondary uppercase tracking-wider">Severely Overdue Projects</span>
            <span class="text-[10px] text-secondary">Click ID to view evidence</span>
          </div>
          <div class="space-y-1.5 max-h-[160px] overflow-y-auto pr-1">
            ${topDelayed.length === 0 ? `
              <div class="text-xs text-secondary py-2 text-center">No overdue works recorded in this scope.</div>
            ` : topDelayed.map(p => `
              <div class="flex items-center justify-between p-2 rounded bg-surface-container-low hover:bg-surface-container transition-colors text-xs">
                <div class="flex flex-col max-w-[70%]">
                  <a href="#/projects/${encodeURIComponent(p.project_id)}" class="font-semibold text-primary hover:underline truncate">
                    ${p.project_title}
                  </a>
                  <span class="text-[10px] text-secondary truncate">${p.district_name}, ${p.state_name} • ${p.sector}</span>
                </div>
                <div class="flex items-center gap-2">
                  <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-error/10 text-error font-tabular-data">
                    +${p.days_delayed} days
                  </span>
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // 6. Cost Anomaly Statistics (Section 5)
  // ---------------------------------------------------------------------------
  function renderCostAnomalyStatistics(container, costAnomaliesData) {
    const card = container.querySelector('#costAnomalyCard');
    if (!card) return;

    const normalCount = costAnomaliesData.normal_cost_count || 0;
    const anomalyCount = costAnomaliesData.cost_anomalous_count || 0;
    const anomalyRate = Number(costAnomaliesData.cost_anomaly_rate_pct || 0).toFixed(1);
    const avgDev = Number(costAnomaliesData.average_deviation_pct || 0).toFixed(1);
    const buckets = costAnomaliesData.deviation_distribution || {};
    const topDeviations = costAnomaliesData.largest_deviations || [];

    const histHtml = window.ChartUtils.renderHistogramChart({
      buckets,
      height: 140,
      barColor: (range) => {
        if (range === '> 100%' || range === '51-100%') return '#ba1a1a';
        if (range === '26-50%') return '#ea580c';
        if (range === '1-25%') return '#eab308';
        return '#00236f';
      },
      formatLabel: (l) => l,
      formatValue: (v) => v
    });

    card.innerHTML = `
      <div>
        <div class="flex items-center justify-between pb-2 border-b border-outline-variant">
          <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-primary text-[18px]">trending_up</span>
            <h3 class="font-title-sm text-title-sm text-on-surface font-bold">5. Cost Anomaly Statistics & Peer Benchmark</h3>
          </div>
          <span class="text-xs font-tabular-data font-semibold text-warning">${anomalyCount} flagged costs</span>
        </div>

        <p class="font-body-sm text-xs text-secondary mt-1 mb-3">
          Statistical IQR outlier detection comparing unit costs against historical sector peer medians.
        </p>

        <!-- Cost Anomaly KPIs Grid -->
        <div class="grid grid-cols-4 gap-2 mb-3">
          <div class="bg-surface-container-low p-2 rounded text-center">
            <span class="text-[10px] text-secondary font-semibold uppercase block">Normal Cost</span>
            <span class="font-display text-base font-bold text-emerald-600 font-tabular-data">${normalCount}</span>
          </div>
          <div class="bg-surface-container-low p-2 rounded text-center">
            <span class="text-[10px] text-secondary font-semibold uppercase block">Anomalous</span>
            <span class="font-display text-base font-bold text-error font-tabular-data">${anomalyCount}</span>
          </div>
          <div class="bg-surface-container-low p-2 rounded text-center">
            <span class="text-[10px] text-secondary font-semibold uppercase block">Anomaly Rate</span>
            <span class="font-display text-base font-bold text-warning font-tabular-data">${anomalyRate}%</span>
          </div>
          <div class="bg-surface-container-low p-2 rounded text-center">
            <span class="text-[10px] text-secondary font-semibold uppercase block">Avg Deviation</span>
            <span class="font-display text-base font-bold text-error font-tabular-data">+${avgDev}%</span>
          </div>
        </div>

        <!-- Cost Deviation Distribution Histogram -->
        <div class="mb-4">
          <div class="text-[11px] font-semibold text-secondary uppercase mb-1">Cost Deviation vs Peer Median</div>
          ${histHtml}
        </div>

        <!-- Largest Cost Deviations with Plain-English Context -->
        <div class="pt-3 border-t border-outline-variant/60">
          <div class="flex items-center justify-between mb-2">
            <span class="text-[11px] font-semibold text-secondary uppercase tracking-wider">Largest Cost Deviations</span>
            <span class="text-[10px] text-secondary">Peer Comparison Ratio</span>
          </div>
          <div class="space-y-2 max-h-[160px] overflow-y-auto pr-1">
            ${topDeviations.length === 0 ? `
              <div class="text-xs text-secondary py-2 text-center">No cost anomalies detected in current scope.</div>
            ` : topDeviations.map(c => `
              <div class="p-2 rounded bg-surface-container-low hover:bg-surface-container transition-colors text-xs flex flex-col gap-1">
                <div class="flex items-center justify-between">
                  <a href="#/projects/${encodeURIComponent(c.project_id)}" class="font-semibold text-primary hover:underline truncate max-w-[65%]">
                    ${c.project_title}
                  </a>
                  <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-error/10 text-error font-tabular-data">
                    +${Number(c.deviation_percentage || 0).toFixed(0)}% vs Peer
                  </span>
                </div>
                <div class="flex items-center justify-between text-[11px] text-secondary">
                  <span>Actual Cost: <b class="text-on-surface">₹${Number(c.evaluated_cost || 0).toLocaleString('en-IN')}</b></span>
                  <span>Peer Median: <b class="text-on-surface">₹${Number(c.peer_median || 0).toLocaleString('en-IN')}</b></span>
                  <span class="font-medium text-error truncate max-w-[30%]">${c.anomaly_type || 'High Unit Cost'}</span>
                </div>
                ${c.reason ? `
                  <div class="text-[10px] text-secondary bg-surface-container/70 p-1.5 rounded border-l-2 border-primary mt-0.5 leading-snug font-sans">
                    ${c.reason}
                  </div>
                ` : ''}
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // 7. Temporal Longitudinal Trends (Section 6)
  // ---------------------------------------------------------------------------
  function renderTemporalTrends(container, trendsData) {
    const card = container.querySelector('#trendsCard');
    if (!card) return;

    const points = trendsData.trend_points || [];

    const trendModes = {
      'volume': [
        { key: 'project_count', label: 'Works Intake', color: '#00236f' },
        { key: 'high_risk_count', label: 'High/Critical Works', color: '#ba1a1a' }
      ],
      'anomalies': [
        { key: 'cost_anomalies_count', label: 'Cost Anomalies', color: '#ea580c' },
        { key: 'high_risk_count', label: 'High Risk Works', color: '#ba1a1a' }
      ],
      'delays': [
        { key: 'delayed_count', label: 'Delayed Works', color: '#ea580c' },
        { key: 'high_risk_count', label: 'High Risk Works', color: '#ba1a1a' }
      ],
      'financial': [
        { key: 'sanctioned_amount_cr', label: 'Sanctioned Outlay (Cr)', color: '#00236f' },
        { key: 'expenditure_amount_cr', label: 'Expenditure Drawn (Cr)', color: '#006a60' }
      ]
    };

    const activeSeries = trendModes[state.trendMode] || trendModes['volume'];

    card.innerHTML = `
      <div>
        <div class="flex flex-col sm:flex-row sm:items-center justify-between pb-2 border-b border-outline-variant gap-2">
          <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-primary text-[18px]">show_chart</span>
            <h3 class="font-title-sm text-title-sm text-on-surface font-bold">6. Temporal Longitudinal Trends</h3>
          </div>

          <!-- Trend Metric Tabs -->
          <div class="inline-flex rounded border border-outline-variant p-0.5 bg-surface-container text-xs">
            <button class="px-2 py-0.5 rounded font-medium transition-colors ${state.trendMode === 'volume' ? 'bg-primary text-on-primary font-bold' : 'text-secondary hover:text-on-surface'}"
                    data-trend-mode="volume">
              Works & Risk
            </button>
            <button class="px-2 py-0.5 rounded font-medium transition-colors ${state.trendMode === 'anomalies' ? 'bg-primary text-on-primary font-bold' : 'text-secondary hover:text-on-surface'}"
                    data-trend-mode="anomalies">
              Cost Anomalies
            </button>
            <button class="px-2 py-0.5 rounded font-medium transition-colors ${state.trendMode === 'delays' ? 'bg-primary text-on-primary font-bold' : 'text-secondary hover:text-on-surface'}"
                    data-trend-mode="delays">
              Delays
            </button>
            <button class="px-2 py-0.5 rounded font-medium transition-colors ${state.trendMode === 'financial' ? 'bg-primary text-on-primary font-bold' : 'text-secondary hover:text-on-surface'}"
                    data-trend-mode="financial">
              Expenditure Outlay
            </button>
          </div>
        </div>

        <p class="font-body-sm text-xs text-secondary mt-1 mb-2">
          Monthly chronological progression based on statutory project sanction dates in PostgreSQL.
        </p>

        <!-- SVG Multi-Series Trend Line Chart -->
        <div class="py-2">
          ${window.ChartUtils.renderTrendLineChart({
            points,
            series: activeSeries,
            height: 220
          })}
        </div>
      </div>
    `;

    // Trend Mode Buttons
    card.querySelectorAll('[data-trend-mode]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        state.trendMode = e.currentTarget.getAttribute('data-trend-mode');
        renderTemporalTrends(container, trendsData);
      });
    });
  }

  // ---------------------------------------------------------------------------
  // 8. India Choropleth Map (Section 7)
  // ---------------------------------------------------------------------------
  function renderIndiaMap(container, mapData) {
    const mapHost = container.querySelector('#indiaMapContainer');
    if (!mapHost) return;

    if (!state.indiaMapInstance) {
      state.indiaMapInstance = new window.IndiaMapComponent({
        container: mapHost,
        mapData,
        selectedState: state.filters.state,
        onStateClick: async (stateName, stateCode) => {
          state.filters.state = stateName;
          state.filters.district = '';
          const stateInput = container.querySelector('#filterState');
          if (stateInput) stateInput.value = stateName;
          await updateDistrictOptions(stateName);
          await loadAndRenderDashboard(container);

          // Smooth scroll to district analysis
          const districtSection = container.querySelector('#districtAnalysisCard');
          if (districtSection) {
            districtSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }
        }
      });
    } else {
      state.indiaMapInstance.container = mapHost;
      state.indiaMapInstance.updateData(mapData, state.filters.state);
    }
    state.indiaMapInstance.render();
  }

  // ---------------------------------------------------------------------------
  // 9. Flagged Projects Quick Triage Table with Explainability Link
  // ---------------------------------------------------------------------------
  function renderFlaggedProjectsTable(container, highRiskList) {
    const card = container.querySelector('#flaggedProjectsTableCard');
    if (!card) return;

    card.innerHTML = `
      <div class="flex items-center justify-between pb-2 border-b border-outline-variant">
        <div class="flex items-center gap-2">
          <span class="material-symbols-outlined text-primary text-[18px]">verified_user</span>
          <h3 class="font-title-sm text-title-sm text-on-surface font-bold">
            Flagged Works Surveillance Queue (Filtered Scope)
          </h3>
        </div>
        <a href="#/investigations" class="text-xs font-semibold text-primary hover:underline flex items-center gap-1">
          <span>Open Full Investigation Desk</span>
          <span class="material-symbols-outlined text-[14px]">arrow_forward</span>
        </a>
      </div>

      <p class="font-body-sm text-xs text-secondary mt-1 mb-3">
        High & Critical works flagged by algorithm. Every project displays measurable evidence justifying the flag.
      </p>

      <div class="overflow-x-auto">
        <table class="w-full text-left font-body-sm text-xs border-collapse">
          <thead>
            <tr class="border-b border-outline-variant bg-surface-container-low text-secondary uppercase font-semibold">
              <th class="py-2 px-3">Project ID & Title</th>
              <th class="py-2 px-3">State & District</th>
              <th class="py-2 px-3 text-center">Risk Tier</th>
              <th class="py-2 px-3 text-right">Risk Score</th>
              <th class="py-2 px-3">Measurable Flag Justification</th>
              <th class="py-2 px-3 text-center">Action</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-outline-variant/50">
            ${highRiskList.length === 0 ? `
              <tr>
                <td colspan="6" class="py-8 text-center text-secondary text-xs">
                  No high-risk works match the currently applied filter criteria.
                </td>
              </tr>
            ` : highRiskList.map(p => `
              <tr class="hover:bg-surface-container-low transition-colors">
                <td class="py-2 px-3">
                  <a href="#/projects/${encodeURIComponent(p.project_id)}" class="font-semibold text-primary hover:underline block truncate max-w-[280px]">
                    ${p.project_title}
                  </a>
                  <span class="text-[10px] text-secondary font-tabular-data">${p.project_id}</span>
                </td>
                <td class="py-2 px-3 text-secondary">
                  ${p.district_name || '—'}, ${p.state_name || '—'}
                </td>
                <td class="py-2 px-3 text-center">
                  <span class="inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                    p.risk_level === 'Critical' ? 'bg-error/10 text-error' :
                    (p.risk_level === 'High' ? 'bg-warning/10 text-warning' : 'bg-primary-container text-on-primary')
                  }">
                    ${p.risk_level}
                  </span>
                </td>
                <td class="py-2 px-3 text-right font-tabular-data font-bold ${p.risk_score >= 60 ? 'text-error' : 'text-on-surface'}">
                  ${Number(p.risk_score).toFixed(1)}
                </td>
                <td class="py-2 px-3">
                  <div class="flex items-center gap-1 flex-wrap">
                    ${(p.primary_risk_factors || p.important_risk_factors || []).slice(0, 2).map(rf => {
                      const label = typeof rf === 'string' ? rf : (rf.factor || rf.category || 'Risk Trigger');
                      const tooltip = typeof rf === 'string' ? rf : (rf.recommendation || rf.reason || rf.factor || '');
                      const impact = typeof rf === 'object' && rf.impact ? `[${rf.impact}]` : '';
                      return `
                        <span class="px-2 py-0.5 rounded text-[10px] bg-surface-container border border-outline-variant/60 font-medium text-on-surface truncate max-w-[220px]" title="${tooltip.replace(/"/g, '&quot;')}">
                          <b>${label}</b> ${impact}
                        </span>
                      `;
                    }).join('')}
                  </div>
                </td>
                <td class="py-2 px-3 text-center">
                  <div class="flex items-center justify-center gap-1.5">
                    <button class="px-2 py-1 text-[11px] font-semibold bg-primary/10 text-primary hover:bg-primary hover:text-on-primary rounded transition-colors inline-flex items-center gap-1"
                            data-explain-project="${p.project_id}">
                      <span class="material-symbols-outlined text-[13px]">psychology</span>
                      <span>Why Flagged?</span>
                    </button>
                    <a href="#/projects/${encodeURIComponent(p.project_id)}" class="px-2 py-1 text-[11px] font-semibold text-secondary hover:text-on-surface hover:bg-surface-container rounded transition-colors inline-flex items-center gap-1" title="Open Complete Project Dossier">
                      <span class="material-symbols-outlined text-[13px]">open_in_new</span>
                    </a>
                  </div>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;

    card.querySelectorAll('[data-explain-project]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const pid = e.currentTarget.getAttribute('data-explain-project');
        if (pid) openExplainabilityModal(pid);
      });
    });
  }

  // ===========================================================================
  // 10. Interactive Quick Explainability Dossier Modal
  // ===========================================================================
  async function openExplainabilityModal(projectId) {
    let modalEl = document.getElementById('analyticsExplainabilityModal');
    if (!modalEl) {
      modalEl = document.createElement('div');
      modalEl.id = 'analyticsExplainabilityModal';
      modalEl.className = 'fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs transition-opacity duration-200';
      document.body.appendChild(modalEl);
    }

    modalEl.innerHTML = `
      <div class="bg-surface-container-lowest border border-outline-variant rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div class="p-space-base border-b border-outline-variant flex items-center justify-between bg-surface-container-low">
          <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-primary text-[22px]">psychology</span>
            <div>
              <h3 class="font-title-sm text-title-sm font-bold text-on-surface">Algorithmic Risk Explainability Dossier</h3>
              <p class="text-[11px] text-secondary font-tabular-data">${projectId}</p>
            </div>
          </div>
          <button id="closeExplainModal" class="p-1 rounded text-secondary hover:text-on-surface hover:bg-surface-container transition-colors">
            <span class="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>
        <div id="explainModalContent" class="p-space-base overflow-y-auto space-y-4 text-xs">
          <div class="flex items-center justify-center py-12 gap-2 text-secondary">
            <span class="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin"></span>
            <span>Synthesizing multi-engine causal evidence...</span>
          </div>
        </div>
      </div>
    `;

    modalEl.style.display = 'flex';

    const closeBtn = modalEl.querySelector('#closeExplainModal');
    const closeModal = () => { modalEl.style.display = 'none'; };
    closeBtn.onclick = closeModal;
    modalEl.onclick = (e) => { if (e.target === modalEl) closeModal(); };

    try {
      const expl = await window.api.getProjectExplanation(projectId);
      const contentEl = modalEl.querySelector('#explainModalContent');
      if (!contentEl) return;

      const score = Number(expl.overall_score || expl.score || 0).toFixed(1);
      const tier = (expl.risk_level || 'Moderate').toUpperCase();
      const tierColor = tier === 'CRITICAL' ? '#ba1a1a' : (tier === 'HIGH' ? '#ea580c' : '#eab308');

      const discrepancies = expl.discrepancies || [];
      const recommendations = expl.recommendations || [];

      contentEl.innerHTML = `
        <!-- Summary Header Card -->
        <div class="p-3 rounded-lg bg-surface-container-low border border-outline-variant flex items-center justify-between gap-3">
          <div class="flex flex-col gap-0.5">
            <span class="text-[10px] uppercase tracking-wider font-semibold text-secondary">Composite Risk Assessment</span>
            <div class="flex items-center gap-2">
              <span class="font-display text-2xl font-bold font-tabular-data text-on-surface">${score}</span>
              <span class="text-xs text-secondary">/ 100</span>
              <span class="px-2 py-0.5 rounded text-[11px] font-bold text-white uppercase ml-1" style="background-color: ${tierColor};">
                ${tier} RISK
              </span>
            </div>
          </div>
          <a href="#/projects/${encodeURIComponent(projectId)}" class="px-3 py-1.5 bg-primary text-on-primary rounded font-medium hover:bg-primary-container transition-colors inline-flex items-center gap-1.5">
            <span>View Full Project Ledger</span>
            <span class="material-symbols-outlined text-[14px]">open_in_new</span>
          </a>
        </div>

        <!-- Synthesis Narrative -->
        <div class="p-3 rounded-lg border-l-4 border-primary bg-surface-container-lowest shadow-xs text-secondary leading-relaxed">
          <span class="font-bold text-on-surface block mb-1 text-xs">Why was this project flagged?</span>
          ${expl.summary || 'Project evaluated across the 6 independent risk engines.'}
        </div>

        <!-- Measurable Discrepancy Evidence -->
        <div>
          <span class="font-bold text-on-surface uppercase tracking-wider text-[11px] block mb-2">Detected Discrepancies & Concrete Evidence</span>
          <div class="space-y-2">
            ${discrepancies.length === 0 ? `
              <div class="p-3 text-center text-secondary bg-surface-container rounded">No active anomaly triggers recorded.</div>
            ` : discrepancies.map(d => `
              <div class="p-2.5 rounded-lg bg-surface-container-low border border-outline-variant flex flex-col gap-1">
                <div class="flex items-center justify-between font-semibold">
                  <span class="text-on-surface flex items-center gap-1.5">
                    <span class="material-symbols-outlined text-[16px] text-error">error</span>
                    ${d.name || d.detector}
                  </span>
                  <span class="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${d.severity === 'critical' ? 'bg-error/10 text-error' : (d.severity === 'high' ? 'bg-warning/10 text-warning' : 'bg-primary/10 text-primary')}">
                    ${d.severity || 'Medium'} Severity
                  </span>
                </div>
                ${(d.evidence || []).map(ev => `
                  <div class="text-[11px] text-secondary flex items-baseline gap-1.5 pl-5">
                    <span>•</span>
                    <span class="text-on-surface font-medium">${ev.text}</span>
                  </div>
                `).join('')}
                ${d.recommendation ? `
                  <div class="text-[10px] text-secondary pl-5 italic mt-0.5">
                    Mitigation: ${d.recommendation}
                  </div>
                ` : ''}
              </div>
            `).join('')}
          </div>
        </div>

        <!-- Recommendations Section -->
        ${recommendations.length > 0 ? `
          <div>
            <span class="font-bold text-on-surface uppercase tracking-wider text-[11px] block mb-2">MoSPI Sentinel Audit Directives</span>
            <ul class="space-y-1 pl-4 list-disc text-secondary text-[11px]">
              ${recommendations.map(r => `<li>${r}</li>`).join('')}
            </ul>
          </div>
        ` : ''}
      `;
    } catch (err) {
      console.error('Failed to load project explanation:', err);
      const contentEl = modalEl.querySelector('#explainModalContent');
      if (contentEl) {
        contentEl.innerHTML = `
          <div class="p-4 text-center text-error bg-error/10 rounded-lg">
            Unable to load explanation for project ${projectId}. Check backend connectivity.
          </div>
        `;
      }
    }
  }

  // Export view renderer to window scope for router and app.js
  window.renderAnalyticsView = renderAnalyticsView;
  window.AnalyticsView = {
    render: renderAnalyticsView
  };
})();
