/**
 * frontend/js/views/dashboard.js
 * =============================================================================
 * Executive Monitoring Dashboard View (Stitch Design).
 * Connects to GET /analytics, GET /analytics/kpis, GET /high-risk, and GET /analytics/sectors.
 * Preserves 100% of the Stitch visual hierarchy, SVG donut chart, and typography.
 * =============================================================================
 */

(function () {
  'use strict';

  function formatNumber(num) {
    if (num === null || num === undefined || isNaN(num)) return '0';
    return Number(num).toLocaleString('en-IN');
  }

  function formatCr(inrAmount) {
    if (!inrAmount) return '0.00';
    const val = Number(inrAmount) / 10000000;
    return val >= 100 ? val.toFixed(1) : val.toFixed(2);
  }

  async function renderDashboardView({ container }) {
    // 1. Show Stitch-styled loading skeleton
    container.innerHTML = `
      <main class="pl-64 pt-16 min-h-screen bg-background p-space-xl">
        <div class="mb-space-lg bg-surface-container-low border-l-4 border-primary px-space-base py-space-sm flex items-center justify-between">
          <div class="flex items-center gap-space-sm">
            <span class="material-symbols-outlined text-primary text-[20px] animate-spin">refresh</span>
            <span class="font-body-sm text-body-sm text-on-surface font-medium">Synchronizing live MIS audit ledger...</span>
          </div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-gutter-grid mb-space-2xl">
          ${[1, 2, 3, 4].map(() => `
            <div class="bg-surface-container-lowest border border-outline-variant p-space-base h-32 animate-pulse flex flex-col justify-between">
              <div class="h-4 w-24 bg-surface-container rounded"></div>
              <div class="h-8 w-32 bg-surface-container rounded"></div>
            </div>
          `).join('')}
        </div>
      </main>
    `;

    try {
      // 2. Fetch live data in parallel
      const [analytics, highRiskList, sectors, kpis] = await Promise.all([
        window.api.getAnalytics().catch(() => ({})),
        window.api.getHighRiskProjects({ limit: 5 }).catch(() => []),
        window.api.getSectorAnalytics().catch(() => []),
        window.api.getKPIs().catch(() => ({}))
      ]);

      const totalProjects = analytics.total_projects || 0;
      const delayedCount = analytics.delayed_projects || 0;
      const utilizationPct = Number(analytics.overall_utilization_pct || kpis.utilization_rate_pct || 0).toFixed(1);
      const totalSanctionedCr = formatCr(analytics.total_sanctioned_amount || (kpis.total_sanctioned_funds_cr ? kpis.total_sanctioned_funds_cr * 10000000 : 0));

      // Risk Distribution Counts
      const dist = analytics.risk_distribution || {};
      const lowCount = dist.Low || 0;
      const medCount = dist.Moderate || dist.Medium || 0;
      const highCount = dist.High || 0;
      const critCount = dist.Critical || 0;
      const elevatedRiskCount = medCount + highCount + critCount;

      // Calculate SVG Donut parameters (circumference = 2 * PI * 38 = 238.76)
      const circumference = 238.76;
      const totalForChart = totalProjects > 0 ? totalProjects : 1;
      const lowPct = ((lowCount / totalForChart) * 100).toFixed(1);
      const medPct = ((medCount / totalForChart) * 100).toFixed(1);
      const highPct = ((highCount / totalForChart) * 100).toFixed(1);
      const critPct = ((critCount / totalForChart) * 100).toFixed(1);

      const lowLen = (lowCount / totalForChart) * circumference;
      const medLen = (medCount / totalForChart) * circumference;
      const highLen = (highCount / totalForChart) * circumference;
      const critLen = (critCount / totalForChart) * circumference;

      const lowOffset = 0;
      const medOffset = -lowLen;
      const highOffset = -(lowLen + medLen);
      const critOffset = -(lowLen + medLen + highLen);

      // 3. Render complete Stitch Executive Monitoring Dashboard
      container.innerHTML = `
        <main class="pl-64 pt-16 min-h-screen bg-background p-space-xl">
          <!-- Institutional Context Banner -->
          <div class="mb-space-lg bg-surface-container-low border-l-4 border-primary px-space-base py-space-sm flex items-center justify-between">
            <div class="flex items-center gap-space-sm">
              <span class="material-symbols-outlined text-primary text-[20px]">verified_user</span>
              <span class="font-body-sm text-body-sm text-on-surface font-medium">Official Internal Record • MoSPI MPLADS Surveillance Division • National Oversight</span>
            </div>
            <span class="font-label-sm text-label-sm text-secondary font-tabular-data">Status: Active Cycle • FY 2024-25</span>
          </div>

          <!-- Page Header -->
          <div class="flex flex-col md:flex-row md:items-end justify-between pb-space-lg mb-space-xl border-b border-outline-variant gap-space-md">
            <div>
              <h1 class="font-headline-lg text-headline-lg text-on-surface tracking-tight">Executive Monitoring Dashboard</h1>
              <p class="font-body-md text-body-md text-secondary mt-space-2xs">High-level statutory audit surveillance, fiscal compliance, and anomaly screening portfolio</p>
            </div>
            <div class="flex items-center gap-space-sm">
              <a href="#/investigations" class="px-space-base py-space-sm bg-error-container text-on-error-container font-label-md text-label-md rounded border border-error/30 hover:bg-error-container/60 transition-colors flex items-center gap-space-xs font-semibold">
                <span class="material-symbols-outlined text-[18px]">rule</span>
                <span>Audit Triage Queue (${highRiskList.length})</span>
              </a>
              <a href="#/projects" class="px-space-base py-space-sm bg-primary text-on-primary font-label-md text-label-md rounded hover:bg-primary-container transition-colors flex items-center gap-space-xs font-semibold">
                <span class="material-symbols-outlined text-[18px]">inventory_2</span>
                <span>View All Projects</span>
              </a>
            </div>
          </div>

          <!-- Top Metric Cards Grid (4 Columns) -->
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-gutter-grid mb-space-2xl">
            <!-- Card 1: Total Projects -->
            <div class="bg-surface-container-lowest border border-outline-variant p-space-base flex flex-col justify-between h-32 shadow-sm rounded-DEFAULT">
              <div class="flex items-center justify-between">
                <span class="font-label-sm text-label-sm text-secondary uppercase tracking-wider">Total Projects</span>
                <span class="material-symbols-outlined text-secondary text-[20px]">assignment</span>
              </div>
              <div class="flex flex-col">
                <span class="font-display text-display text-on-surface font-tabular-data leading-none font-bold text-2xl">${formatNumber(totalProjects)}</span>
                <span class="font-body-sm text-body-sm text-secondary mt-space-xs">Sanctioned in active cycle</span>
              </div>
            </div>

            <!-- Card 2: High Risk / Action Required -->
            <div class="bg-surface-container-lowest border border-outline-variant p-space-base flex flex-col justify-between h-32 shadow-sm rounded-DEFAULT">
              <div class="flex items-center justify-between">
                <span class="font-label-sm text-label-sm text-secondary uppercase tracking-wider">Elevated Risk Flags</span>
                <span class="material-symbols-outlined text-error text-[20px]">warning</span>
              </div>
              <div class="flex flex-col">
                <span class="font-display text-display text-error font-tabular-data leading-none font-bold text-2xl">${formatNumber(elevatedRiskCount)}</span>
                <span class="font-body-sm text-body-sm text-secondary mt-space-xs">${critCount} Critical • ${highCount} High • ${medCount} Moderate</span>
              </div>
            </div>

            <!-- Card 3: Delayed Projects -->
            <div class="bg-surface-container-lowest border border-outline-variant p-space-base flex flex-col justify-between h-32 shadow-sm rounded-DEFAULT">
              <div class="flex items-center justify-between">
                <span class="font-label-sm text-label-sm text-secondary uppercase tracking-wider">Delayed Projects</span>
                <span class="material-symbols-outlined text-secondary text-[20px]">schedule</span>
              </div>
              <div class="flex flex-col">
                <span class="font-display text-display text-on-surface font-tabular-data leading-none font-bold text-2xl">${formatNumber(delayedCount)}</span>
                <span class="font-body-sm text-body-sm text-secondary mt-space-xs">Exceeding scheduled timeline</span>
              </div>
            </div>

            <!-- Card 4: Fund Utilization -->
            <div class="bg-surface-container-lowest border border-outline-variant p-space-base flex flex-col justify-between h-32 shadow-sm rounded-DEFAULT">
              <div class="flex items-center justify-between">
                <span class="font-label-sm text-label-sm text-secondary uppercase tracking-wider">Fund Utilization</span>
                <span class="material-symbols-outlined text-secondary text-[20px]">account_balance</span>
              </div>
              <div class="flex flex-col">
                <span class="font-display text-display text-on-surface font-tabular-data leading-none font-bold text-2xl">${utilizationPct}%</span>
                <span class="font-body-sm text-body-sm text-secondary mt-space-xs">Of ₹${totalSanctionedCr} Cr total allocation</span>
              </div>
            </div>
          </div>

          <!-- Middle Row: Risk Distribution (40%) & Recent High-Risk Projects Table (60%) -->
          <div class="grid grid-cols-1 lg:grid-cols-12 gap-space-xl mb-space-2xl items-start">
            <!-- Left Column: Risk Distribution Donut Chart -->
            <div class="lg:col-span-5 bg-surface-container-lowest border border-outline-variant p-space-lg flex flex-col shadow-sm rounded-DEFAULT">
              <div class="pb-space-sm border-b border-outline-variant mb-space-lg flex items-center justify-between">
                <h2 class="font-title-md text-title-md text-on-surface font-bold">Risk Distribution</h2>
                <span class="font-label-sm text-label-sm text-secondary font-tabular-data">Total: ${formatNumber(totalProjects)} Units</span>
              </div>
              <div class="flex flex-col sm:flex-row items-center gap-space-lg">
                <!-- SVG Donut Chart -->
                <div class="relative w-40 h-40 flex-shrink-0 flex items-center justify-center">
                  <svg aria-label="Risk breakdown donut chart" class="w-full h-full -rotate-90" viewBox="0 0 100 100">
                    <circle cx="50" cy="50" fill="none" r="38" stroke="#e5eeff" stroke-width="16"></circle>
                    <!-- Low Risk (Green) -->
                    <circle cx="50" cy="50" fill="none" r="38" stroke="#16a34a" stroke-dasharray="${lowLen} ${circumference}" stroke-dashoffset="${lowOffset}" stroke-width="16"></circle>
                    <!-- Moderate (Amber) -->
                    <circle cx="50" cy="50" fill="none" r="38" stroke="#d97706" stroke-dasharray="${medLen} ${circumference}" stroke-dashoffset="${medOffset}" stroke-width="16"></circle>
                    <!-- High (Orange) -->
                    <circle cx="50" cy="50" fill="none" r="38" stroke="#ea580c" stroke-dasharray="${highLen} ${circumference}" stroke-dashoffset="${highOffset}" stroke-width="16"></circle>
                    <!-- Critical (Red) -->
                    <circle cx="50" cy="50" fill="none" r="38" stroke="#dc2626" stroke-dasharray="${critLen} ${circumference}" stroke-dashoffset="${critOffset}" stroke-width="16"></circle>
                  </svg>
                  <div class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                    <span class="font-label-sm text-label-sm text-secondary uppercase font-semibold">Low Risk</span>
                    <span class="font-title-sm text-title-sm text-on-surface font-tabular-data font-bold">${lowPct}%</span>
                  </div>
                </div>

                <!-- Legend Table / List -->
                <div class="flex-1 w-full flex flex-col gap-space-xs">
                  <!-- Low -->
                  <div class="flex items-center justify-between py-space-2xs border-b border-outline-variant">
                    <div class="flex items-center gap-space-xs">
                      <span class="w-3 h-3 bg-[#16a34a] rounded-[1px] flex-shrink-0"></span>
                      <span class="font-body-sm text-body-sm text-on-surface">Low</span>
                    </div>
                    <div class="text-right">
                      <span class="font-tabular-data text-tabular-data text-on-surface font-semibold">${formatNumber(lowCount)}</span>
                      <span class="font-label-sm text-label-sm text-secondary ml-space-xs">(${lowPct}%)</span>
                    </div>
                  </div>
                  <!-- Moderate / Medium -->
                  <div class="flex items-center justify-between py-space-2xs border-b border-outline-variant">
                    <div class="flex items-center gap-space-xs">
                      <span class="w-3 h-3 bg-[#d97706] rounded-[1px] flex-shrink-0"></span>
                      <span class="font-body-sm text-body-sm text-on-surface">Moderate</span>
                    </div>
                    <div class="text-right">
                      <span class="font-tabular-data text-tabular-data text-on-surface font-semibold">${formatNumber(medCount)}</span>
                      <span class="font-label-sm text-label-sm text-secondary ml-space-xs">(${medPct}%)</span>
                    </div>
                  </div>
                  <!-- High -->
                  <div class="flex items-center justify-between py-space-2xs border-b border-outline-variant">
                    <div class="flex items-center gap-space-xs">
                      <span class="w-3 h-3 bg-[#ea580c] rounded-[1px] flex-shrink-0"></span>
                      <span class="font-body-sm text-body-sm text-on-surface">High</span>
                    </div>
                    <div class="text-right">
                      <span class="font-tabular-data text-tabular-data text-on-surface font-semibold">${formatNumber(highCount)}</span>
                      <span class="font-label-sm text-label-sm text-secondary ml-space-xs">(${highPct}%)</span>
                    </div>
                  </div>
                  <!-- Critical -->
                  <div class="flex items-center justify-between py-space-2xs">
                    <div class="flex items-center gap-space-xs">
                      <span class="w-3 h-3 bg-[#dc2626] rounded-[1px] flex-shrink-0"></span>
                      <span class="font-body-sm text-body-sm text-on-surface">Critical</span>
                    </div>
                    <div class="text-right">
                      <span class="font-tabular-data text-tabular-data text-error font-semibold">${formatNumber(critCount)}</span>
                      <span class="font-label-sm text-label-sm text-secondary ml-space-xs">(${critPct}%)</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Right Column: Recent High-Risk Projects Table -->
            <div class="lg:col-span-7 bg-surface-container-lowest border border-outline-variant p-space-lg flex flex-col shadow-sm rounded-DEFAULT">
              <div class="pb-space-sm border-b border-outline-variant mb-space-md flex items-center justify-between">
                <div>
                  <h2 class="font-title-md text-title-md text-on-surface font-bold">Recent High-Risk Projects</h2>
                  <span class="font-body-sm text-body-sm text-secondary">Immediate attention required by District Authority</span>
                </div>
                <a class="font-label-sm text-label-sm text-primary hover:underline flex items-center gap-space-2xs font-semibold" href="#/investigations">
                  <span>View Queue</span>
                  <span class="material-symbols-outlined text-[16px]">arrow_forward</span>
                </a>
              </div>
              <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse">
                  <thead>
                    <tr class="bg-surface-container-low border-b-2 border-outline-variant">
                      <th class="py-2.5 px-3 font-label-md text-label-md text-secondary uppercase tracking-wider" scope="col">Project ID</th>
                      <th class="py-2.5 px-3 font-label-md text-label-md text-secondary uppercase tracking-wider" scope="col">Risk</th>
                      <th class="py-2.5 px-3 font-label-md text-label-md text-secondary uppercase tracking-wider" scope="col">Status</th>
                      <th class="py-2.5 px-3 font-label-md text-label-md text-secondary uppercase tracking-wider text-right" scope="col">Action</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-outline-variant">
                    ${highRiskList.length === 0 ? `
                      <tr>
                        <td colspan="4" class="py-6 text-center text-secondary font-body-sm">No high-risk projects currently flagged.</td>
                      </tr>
                    ` : highRiskList.map(item => {
                      const tier = (item.risk_level || 'Moderate').toUpperCase();
                      const tierBadge = tier === 'CRITICAL'
                        ? '<span class="inline-flex items-center px-2 py-0.5 border border-[#fecaca] bg-[#fef2f2] text-[#dc2626] font-label-sm font-bold">Critical</span>'
                        : tier === 'HIGH'
                          ? '<span class="inline-flex items-center px-2 py-0.5 border border-[#fed7aa] bg-[#fff7ed] text-[#ea580c] font-label-sm font-bold">High</span>'
                          : '<span class="inline-flex items-center px-2 py-0.5 border border-[#fde68a] bg-[#fffbeb] text-[#d97706] font-label-sm font-bold">Moderate</span>';

                      return `
                        <tr class="hover:bg-surface-container-low transition-colors">
                          <td class="py-2.5 px-3 font-tabular-data text-tabular-data text-on-surface font-semibold">
                            <a href="#/projects/${encodeURIComponent(item.project_id)}" class="hover:underline text-primary">${item.project_id}</a>
                            <div class="text-[11px] text-secondary truncate max-w-xs font-normal">${item.project_name || item.project_title || ''}</div>
                          </td>
                          <td class="py-2.5 px-3">
                            ${tierBadge}
                            <span class="ml-1 text-[11px] font-mono text-secondary">${Number(item.risk_score || 0).toFixed(1)}</span>
                          </td>
                          <td class="py-2.5 px-3 font-body-sm text-body-sm text-on-surface">${item.current_status || 'In Progress'}</td>
                          <td class="py-2.5 px-3 text-right">
                            <a href="#/projects/${encodeURIComponent(item.project_id)}" class="text-primary hover:text-primary-container font-label-sm font-semibold underline">Inspect</a>
                          </td>
                        </tr>
                      `;
                    }).join('')}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <!-- Bottom: Projects by Risk Category / Sector Breakdown -->
          <div class="bg-surface-container-lowest border border-outline-variant p-space-lg flex flex-col mb-space-xl shadow-sm rounded-DEFAULT">
            <div class="pb-space-sm border-b border-outline-variant mb-space-lg flex flex-col sm:flex-row sm:items-center justify-between gap-space-xs">
              <div>
                <h2 class="font-title-md text-title-md text-on-surface font-bold">Developmental Sector Surveillance</h2>
                <span class="font-body-sm text-body-sm text-secondary">Categorized breakdown of project counts and financial utilization</span>
              </div>
              <div class="font-tabular-data text-tabular-data text-secondary">
                Baseline: Fiscal 2024-25 Audit Standards
              </div>
            </div>

            <!-- Horizontal Bar Chart -->
            <div class="flex flex-col gap-space-md max-w-4xl">
              ${(sectors.length > 0 ? sectors.slice(0, 5) : [
                { sector: 'Roads & Bridges', project_count: 6, average_risk_score: 55.2 },
                { sector: 'Drinking Water', project_count: 5, average_risk_score: 42.0 },
                { sector: 'Education & Schools', project_count: 4, average_risk_score: 28.5 },
                { sector: 'Health & Family Welfare', project_count: 3, average_risk_score: 35.0 },
                { sector: 'Sanitation', project_count: 2, average_risk_score: 30.0 }
              ]).map(sec => {
                const count = sec.project_count || 1;
                const maxCount = Math.max(...sectors.map(s => s.project_count || 1), 10);
                const barWidth = Math.min(100, Math.max(12, (count / maxCount) * 100)).toFixed(1);
                return `
                  <div class="flex flex-col sm:flex-row sm:items-center gap-space-xs sm:gap-space-base">
                    <div class="w-56 font-body-sm text-body-sm text-on-surface flex items-center justify-between sm:justify-start gap-space-xs">
                      <span class="font-medium">${sec.sector}</span>
                      <span class="text-secondary sm:hidden font-tabular-data font-semibold">${count} projects</span>
                    </div>
                    <div class="flex-1 bg-surface-container-low border border-outline-variant h-7 flex items-center p-0.5 rounded-sm">
                      <div class="bg-primary-container h-full flex items-center px-2 text-on-primary font-tabular-data text-label-sm font-semibold rounded-sm transition-all duration-500" style="width: ${barWidth}%;">
                        ${count}
                      </div>
                    </div>
                    <div class="w-28 text-right hidden sm:block font-tabular-data text-tabular-data text-on-surface font-semibold">
                      ${count} works
                    </div>
                  </div>
                `;
              }).join('')}
            </div>
          </div>
        </main>
      `;
    } catch (err) {
      console.error('[DashboardView] Error loading dashboard:', err);
      container.innerHTML = `
        <main class="pl-64 pt-16 min-h-screen bg-background p-space-xl">
          <div class="p-8 max-w-xl mx-auto my-12 bg-surface-container-lowest border border-error rounded-lg">
            <h3 class="text-lg font-bold text-error mb-2">Unable to Load Dashboard</h3>
            <p class="text-sm text-secondary mb-4">${err.message || 'Error communicating with backend.'}</p>
            <button onclick="window.location.reload()" class="px-4 py-2 bg-primary text-on-primary rounded text-sm font-semibold">Retry</button>
          </div>
        </main>
      `;
    }
  }

  window.renderDashboardView = renderDashboardView;
})();
