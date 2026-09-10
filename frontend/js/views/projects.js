/**
 * frontend/js/views/projects.js
 * =============================================================================
 * Master Projects Registry View (Stitch Design).
 * Connects to GET /projects with live Search, Filter Dropdowns, Pagination, and Sorting.
 * Preserves 100% of the Stitch layout, table structure, typography, and badges.
 * =============================================================================
 */

(function () {
  'use strict';

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

  let currentParams = {
    page: 1,
    limit: 10,
    q: '',
    sector: '',
    risk_level: '',
    state_id: '',
  };

  let debounceTimer = null;

  async function renderProjectsView({ container, queryParams }) {
    if (queryParams) {
      if (queryParams.q !== undefined) currentParams.q = queryParams.q;
      if (queryParams.page !== undefined) currentParams.page = parseInt(queryParams.page) || 1;
      if (queryParams.risk_level !== undefined) currentParams.risk_level = queryParams.risk_level;
      if (queryParams.sector !== undefined) currentParams.sector = queryParams.sector;
    }

    // 1. Initial Frame Render
    container.innerHTML = `
      <main class="pl-64 pt-16 min-h-screen bg-background p-space-xl">
        <!-- Official Banner -->
        <div class="bg-surface-container-lowest border-l-4 border-primary-container p-space-base mb-space-lg shadow-sm rounded-DEFAULT flex flex-col md:flex-row md:items-center justify-between gap-space-md">
          <div class="flex items-start gap-space-md">
            <span class="material-symbols-outlined text-primary-container text-[24px] mt-0.5">policy</span>
            <div>
              <div class="flex items-center gap-space-sm mb-space-2xs">
                <span class="font-label-sm text-label-sm text-secondary uppercase font-semibold tracking-wider">Cycle: FY 2024-25</span>
                <span class="inline-flex items-center px-1.5 py-0.5 border border-outline-variant bg-surface-container-low text-secondary font-mono text-label-sm font-semibold rounded-sm">NIC-DG-SYNCED</span>
              </div>
              <h2 class="font-title-sm text-title-sm text-on-surface font-semibold">Public MIS Database • Constituency Works Ledger</h2>
              <p class="font-body-sm text-body-sm text-secondary">Statutory expenditure record under Rule 14(2) of the MPLADS Scheme Guidelines.</p>
            </div>
          </div>
          <div class="flex items-center gap-space-sm shrink-0">
            <button id="exportCsvBtn" type="button" class="px-space-base py-space-sm bg-surface-container-low text-on-surface font-label-md text-label-md rounded border border-outline-variant hover:bg-surface-container transition-colors flex items-center gap-space-xs font-semibold">
              <span class="material-symbols-outlined text-[18px]">file_download</span>
              <span>Export CSV</span>
            </button>
            <a href="#/investigations" class="px-space-base py-space-sm bg-primary text-on-primary font-label-md text-label-md rounded hover:bg-primary-container transition-colors flex items-center gap-space-xs font-semibold">
              <span class="material-symbols-outlined text-[18px]">rule</span>
              <span>Audit Queue</span>
            </a>
          </div>
        </div>

        <!-- Section Title -->
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-space-md pb-space-lg mb-space-xl border-b border-outline-variant">
          <div>
            <h1 class="font-headline-lg text-headline-lg text-on-surface font-bold tracking-tight">Master Projects Registry</h1>
            <p class="font-body-md text-body-md text-secondary mt-space-2xs">Comprehensive audit trail of developmental recommendations, sanctions, and site milestones</p>
          </div>
        </div>

        <!-- Summary KPIs (4 Cards) -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-space-md mb-space-xl">
          <div class="bg-surface-container-lowest border border-outline-variant rounded-lg p-space-base shadow-sm">
            <span class="font-label-sm text-label-sm text-secondary uppercase font-semibold">Total Sanctioned Works</span>
            <div id="statTotalWorks" class="font-display text-display text-on-surface font-tabular-data mt-space-xs text-2xl font-bold">...</div>
            <span class="font-body-sm text-body-sm text-secondary">Active database records</span>
          </div>
          <div class="bg-surface-container-lowest border border-outline-variant rounded-lg p-space-base shadow-sm">
            <span class="font-label-sm text-label-sm text-secondary uppercase font-semibold">Aggregate Sanctioned</span>
            <div id="statTotalFunds" class="font-display text-display text-primary font-tabular-data mt-space-xs text-2xl font-bold">...</div>
            <span class="font-body-sm text-body-sm text-secondary">Total approved outlay</span>
          </div>
          <div class="bg-surface-container-lowest border border-outline-variant rounded-lg p-space-base shadow-sm">
            <span class="font-label-sm text-label-sm text-secondary uppercase font-semibold">High/Critical Flags</span>
            <div id="statHighRisk" class="font-display text-display text-error font-tabular-data mt-space-xs text-2xl font-bold">...</div>
            <span class="font-body-sm text-body-sm text-secondary">Requires collector scrutiny</span>
          </div>
          <div class="bg-surface-container-lowest border border-outline-variant rounded-lg p-space-base shadow-sm">
            <span class="font-label-sm text-label-sm text-secondary uppercase font-semibold">Completion Rate</span>
            <div id="statCompleted" class="font-display text-display text-on-surface font-tabular-data mt-space-xs text-2xl font-bold">...</div>
            <span class="font-body-sm text-body-sm text-secondary">Certified completions</span>
          </div>
        </div>

        <!-- Filters & Search Toolbar -->
        <div class="bg-surface-container-lowest border border-outline-variant p-space-base rounded-lg mb-space-lg shadow-sm">
          <div class="grid grid-cols-1 md:grid-cols-12 gap-space-md items-center">
            <!-- Search Input (5 cols) -->
            <div class="md:col-span-5 relative flex items-center">
              <span class="material-symbols-outlined absolute left-space-sm text-outline pointer-events-none text-[18px]">search</span>
              <input id="projectSearchInput" class="w-full pl-9 pr-space-md py-space-sm font-body-sm text-body-sm bg-surface-container-lowest border border-outline-variant rounded-lg text-on-surface placeholder:text-outline focus:outline-none focus:border-primary-container transition-colors" placeholder="Search by Project ID, Title, or Agency..." type="text" value="${escapeHtml(currentParams.q)}">
            </div>

            <!-- Risk Level Filter (3 cols) -->
            <div class="md:col-span-3">
              <select id="filterRiskLevel" class="w-full py-space-sm px-space-sm font-body-sm text-body-sm bg-surface-container-lowest border border-outline-variant rounded-lg text-on-surface focus:outline-none focus:border-primary-container transition-colors">
                <option value="">All Risk Levels</option>
                <option value="Critical" ${currentParams.risk_level === 'Critical' ? 'selected' : ''}>Critical Risk Only</option>
                <option value="High" ${currentParams.risk_level === 'High' ? 'selected' : ''}>High Risk Only</option>
                <option value="Moderate" ${currentParams.risk_level === 'Moderate' ? 'selected' : ''}>Moderate Risk</option>
                <option value="Low" ${currentParams.risk_level === 'Low' ? 'selected' : ''}>Low Risk (Healthy)</option>
              </select>
            </div>

            <!-- Sector Filter (2 cols) -->
            <div class="md:col-span-2">
              <select id="filterSector" class="w-full py-space-sm px-space-sm font-body-sm text-body-sm bg-surface-container-lowest border border-outline-variant rounded-lg text-on-surface focus:outline-none focus:border-primary-container transition-colors">
                <option value="">All Sectors</option>
                <option value="Roads & Bridges" ${currentParams.sector === 'Roads & Bridges' ? 'selected' : ''}>Roads & Bridges</option>
                <option value="Drinking Water" ${currentParams.sector === 'Drinking Water' ? 'selected' : ''}>Drinking Water</option>
                <option value="Education" ${currentParams.sector === 'Education' ? 'selected' : ''}>Education</option>
                <option value="Health" ${currentParams.sector === 'Health' ? 'selected' : ''}>Health</option>
                <option value="Irrigation" ${currentParams.sector === 'Irrigation' ? 'selected' : ''}>Irrigation</option>
              </select>
            </div>

            <!-- Reset Filters (2 cols) -->
            <div class="md:col-span-2 flex justify-end">
              <button id="btnResetFilters" type="button" class="w-full py-space-sm px-space-sm bg-surface-container-low border border-outline-variant text-secondary hover:text-on-surface text-body-sm rounded-lg font-semibold transition-colors flex items-center justify-center gap-1">
                <span class="material-symbols-outlined text-[16px]">restart_alt</span>
                <span>Reset</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Projects Table Card -->
        <div class="bg-surface-container-lowest border border-outline-variant rounded-lg shadow-sm overflow-hidden mb-space-xl">
          <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse">
              <thead>
                <tr class="bg-surface-container-low border-b-2 border-outline-variant">
                  <th class="py-space-sm px-space-md font-label-md text-label-md text-secondary uppercase tracking-wider" scope="col">Project ID</th>
                  <th class="py-space-sm px-space-md font-label-md text-label-md text-secondary uppercase tracking-wider" scope="col">Project Name</th>
                  <th class="py-space-sm px-space-md font-label-md text-label-md text-secondary uppercase tracking-wider" scope="col">State / Constituency</th>
                  <th class="py-space-sm px-space-md font-label-md text-label-md text-secondary uppercase tracking-wider text-right" scope="col">Cost</th>
                  <th class="py-space-sm px-space-md font-label-md text-label-md text-secondary uppercase tracking-wider" scope="col">Risk Score</th>
                  <th class="py-space-sm px-space-md font-label-md text-label-md text-secondary uppercase tracking-wider" scope="col">Status</th>
                  <th class="py-space-sm px-space-md font-label-md text-label-md text-secondary uppercase tracking-wider text-right" scope="col">Action</th>
                </tr>
              </thead>
              <tbody id="projectsTableBody" class="divide-y divide-outline-variant">
                <!-- Dynamic rows injected here -->
                <tr>
                  <td colspan="7" class="py-12 text-center text-secondary">
                    <span class="material-symbols-outlined animate-spin text-3xl text-primary">progress_activity</span>
                    <div class="mt-2 text-sm">Loading projects registry...</div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination Footer -->
          <div class="p-space-base border-t border-outline-variant bg-surface-container-low flex flex-col sm:flex-row items-center justify-between gap-space-md">
            <div id="paginationInfo" class="font-body-sm text-body-sm text-secondary">
              Showing 0 of 0 projects
            </div>
            <div class="flex items-center gap-space-xs">
              <button id="btnPrevPage" class="px-space-md py-space-xs bg-surface-container-lowest border border-outline-variant text-on-surface rounded font-label-sm font-semibold hover:bg-surface-container disabled:opacity-40 disabled:cursor-not-allowed">
                Previous
              </button>
              <span id="pageIndicator" class="px-space-md py-space-xs font-tabular-data text-body-sm text-on-surface font-semibold">Page 1</span>
              <button id="btnNextPage" class="px-space-md py-space-xs bg-surface-container-lowest border border-outline-variant text-on-surface rounded font-label-sm font-semibold hover:bg-surface-container disabled:opacity-40 disabled:cursor-not-allowed">
                Next
              </button>
            </div>
          </div>
        </div>
      </main>
    `;

    // 2. Bind listeners
    const searchInput = document.getElementById('projectSearchInput');
    const riskSelect = document.getElementById('filterRiskLevel');
    const sectorSelect = document.getElementById('filterSector');
    const btnReset = document.getElementById('btnResetFilters');
    const btnPrev = document.getElementById('btnPrevPage');
    const btnNext = document.getElementById('btnNextPage');
    const btnExport = document.getElementById('exportCsvBtn');

    searchInput.addEventListener('input', (e) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        currentParams.q = e.target.value.trim();
        currentParams.page = 1;
        fetchAndRenderProjects();
      }, 350);
    });

    riskSelect.addEventListener('change', (e) => {
      currentParams.risk_level = e.target.value;
      currentParams.page = 1;
      fetchAndRenderProjects();
    });

    sectorSelect.addEventListener('change', (e) => {
      currentParams.sector = e.target.value;
      currentParams.page = 1;
      fetchAndRenderProjects();
    });

    btnReset.addEventListener('click', () => {
      currentParams = { page: 1, limit: 10, q: '', sector: '', risk_level: '', state_id: '' };
      searchInput.value = '';
      riskSelect.value = '';
      sectorSelect.value = '';
      fetchAndRenderProjects();
    });

    btnPrev.addEventListener('click', () => {
      if (currentParams.page > 1) {
        currentParams.page--;
        fetchAndRenderProjects();
      }
    });

    btnNext.addEventListener('click', () => {
      currentParams.page++;
      fetchAndRenderProjects();
    });

    btnExport.addEventListener('click', () => {
      exportProjectsCsv();
    });

    // 3. Load initial data
    await fetchAndRenderProjects();
    loadMacroStats();
  }

  async function loadMacroStats() {
    try {
      const analytics = await window.api.getAnalytics();
      const statTotalWorks = document.getElementById('statTotalWorks');
      const statTotalFunds = document.getElementById('statTotalFunds');
      const statHighRisk = document.getElementById('statHighRisk');
      const statCompleted = document.getElementById('statCompleted');

      if (statTotalWorks) statTotalWorks.textContent = formatNumber(analytics.total_projects || 0);
      if (statTotalFunds) {
        const amt = Number(analytics.total_sanctioned_amount || 0);
        statTotalFunds.textContent = amt >= 10000000 ? `₹${(amt / 10000000).toFixed(1)} Cr` : `₹${(amt / 100000).toFixed(1)} L`;
      }
      if (statHighRisk) {
        const elevated = (analytics.risk_distribution?.High || 0) + (analytics.risk_distribution?.Critical || 0);
        statHighRisk.textContent = formatNumber(elevated);
      }
      if (statCompleted) statCompleted.textContent = formatNumber(analytics.completed_projects || 0);
    } catch (err) {
      console.warn('[ProjectsView] Error loading macro stats:', err);
    }
  }

  async function fetchAndRenderProjects() {
    const tbody = document.getElementById('projectsTableBody');
    const paginationInfo = document.getElementById('paginationInfo');
    const pageIndicator = document.getElementById('pageIndicator');
    const btnPrev = document.getElementById('btnPrevPage');
    const btnNext = document.getElementById('btnNextPage');

    if (!tbody) return;

    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="py-12 text-center text-secondary">
          <span class="material-symbols-outlined animate-spin text-3xl text-primary">progress_activity</span>
          <div class="mt-2 text-sm">Querying projects...</div>
        </td>
      </tr>
    `;

    try {
      const skip = (currentParams.page - 1) * currentParams.limit;
      const res = await window.api.getProjects({
        skip,
        limit: currentParams.limit,
        q: currentParams.q,
        sector: currentParams.sector,
        risk_level: currentParams.risk_level,
      });

      const items = res.items || [];
      const total = res.total || 0;
      const totalPages = Math.max(1, Math.ceil(total / currentParams.limit));

      if (paginationInfo) {
        const start = total === 0 ? 0 : skip + 1;
        const end = Math.min(total, skip + items.length);
        paginationInfo.textContent = `Showing ${start}–${end} of ${formatNumber(total)} projects`;
      }

      if (pageIndicator) pageIndicator.textContent = `Page ${currentParams.page} of ${totalPages}`;
      if (btnPrev) btnPrev.disabled = currentParams.page <= 1;
      if (btnNext) btnNext.disabled = currentParams.page >= totalPages;

      if (items.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="7" class="py-12 text-center text-secondary">
              <span class="material-symbols-outlined text-4xl text-outline mb-2">search_off</span>
              <div class="font-bold text-on-surface">No projects found</div>
              <div class="text-sm mt-1">Try relaxing your search terms or filter selections.</div>
            </td>
          </tr>
        `;
        return;
      }

      tbody.innerHTML = items.map(proj => {
        const riskLevel = (proj.risk_level || 'Moderate').toUpperCase();
        const riskScore = Number(proj.overall_risk_score || proj.risk_score || 0).toFixed(1);

        let badgeClass = 'border-[#fde68a] bg-[#fffbeb] text-[#d97706]';
        let badgeLabel = 'Moderate';
        if (riskLevel === 'CRITICAL') {
          badgeClass = 'border-[#fecaca] bg-[#fef2f2] text-[#dc2626]';
          badgeLabel = 'Critical';
        } else if (riskLevel === 'HIGH') {
          badgeClass = 'border-[#fed7aa] bg-[#fff7ed] text-[#ea580c]';
          badgeLabel = 'High';
        } else if (riskLevel === 'LOW') {
          badgeClass = 'border-[#bbf7d0] bg-[#f0fdf4] text-[#16a34a]';
          badgeLabel = 'Low';
        }

        const costFormatted = formatLakh(proj.sanctioned_amount);
        const statusText = proj.current_status || 'In Progress';

        return `
          <tr class="hover:bg-surface-container-low transition-colors">
            <td class="py-space-md px-space-md font-tabular-data text-tabular-data text-on-surface font-semibold">
              <a href="#/projects/${encodeURIComponent(proj.project_id)}" class="text-primary hover:underline">${proj.project_id}</a>
              <div class="text-[11px] text-secondary font-mono">${proj.project_code || ''}</div>
            </td>
            <td class="py-space-md px-space-md">
              <div class="font-body-sm text-body-sm text-on-surface font-semibold max-w-sm truncate">${proj.project_title || 'Untitled Project'}</div>
              <div class="font-label-sm text-label-sm text-secondary">${proj.sector || 'General'}</div>
            </td>
            <td class="py-space-md px-space-md">
              <div class="font-body-sm text-body-sm text-on-surface">${proj.state_name || '—'}</div>
              <div class="font-label-sm text-label-sm text-secondary">${proj.district_name || ''}</div>
            </td>
            <td class="py-space-md px-space-md text-right font-tabular-data text-tabular-data text-on-surface font-semibold">
              ${costFormatted}
            </td>
            <td class="py-space-md px-space-md">
              <div class="flex items-center gap-2">
                <span class="inline-flex items-center px-2 py-0.5 border ${badgeClass} font-label-sm text-label-sm font-bold rounded-DEFAULT">
                  ${badgeLabel}
                </span>
                <span class="font-mono text-xs font-semibold text-on-surface">${riskScore}</span>
              </div>
            </td>
            <td class="py-space-md px-space-md">
              <span class="font-body-sm text-body-sm text-on-surface">${statusText}</span>
            </td>
            <td class="py-space-md px-space-md text-right">
              <a href="#/projects/${encodeURIComponent(proj.project_id)}" class="px-space-md py-space-xs bg-surface-container-low border border-outline-variant text-primary hover:bg-primary hover:text-on-primary font-label-sm font-semibold rounded transition-colors inline-flex items-center gap-1">
                <span>View</span>
                <span class="material-symbols-outlined text-[14px]">arrow_forward</span>
              </a>
            </td>
          </tr>
        `;
      }).join('');
    } catch (err) {
      console.error('[ProjectsView] Error fetching projects:', err);
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="py-8 text-center text-error">
            <span class="material-symbols-outlined text-3xl">error</span>
            <div class="font-semibold mt-1">Unable to load projects registry</div>
            <div class="text-sm text-secondary mt-1">${err.message || 'Please verify network or database connectivity.'}</div>
          </td>
        </tr>
      `;
    }
  }

  async function exportProjectsCsv() {
    try {
      const res = await window.api.getProjects({ skip: 0, limit: 100 });
      const items = res.items || [];
      if (items.length === 0) {
        alert('No projects to export.');
        return;
      }
      const headers = ['Project ID', 'Code', 'Title', 'State', 'District', 'Sector', 'Sanctioned Amount', 'Risk Level', 'Risk Score', 'Status'];
      const rows = items.map(p => [
        `"${p.project_id}"`,
        `"${p.project_code || ''}"`,
        `"${(p.project_title || '').replace(/"/g, '""')}"`,
        `"${p.state_name || ''}"`,
        `"${p.district_name || ''}"`,
        `"${p.sector || ''}"`,
        p.sanctioned_amount || 0,
        `"${p.risk_level || ''}"`,
        p.overall_risk_score || 0,
        `"${p.current_status || ''}"`
      ]);
      const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `MPLADS_Projects_Registry_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('Error exporting CSV: ' + err.message);
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[m]);
  }

  window.renderProjectsView = renderProjectsView;
})();
