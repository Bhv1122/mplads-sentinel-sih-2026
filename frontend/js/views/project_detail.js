/**
 * frontend/js/views/project_detail.js
 * =============================================================================
 * 360-Degree Project Audit Dossier & Explainability View (Stitch Design).
 * Connects to:
 *   - GET /projects/{id}
 *   - GET /projects/{id}/explanation
 *   - POST /projects/{id}/risk/recalculate
 * 
 * Preserves 100% of the Google Stitch visual layout, Material Design 3 tokens,
 * typography, gauge dials, discrepancy cards, and evidence presentation.
 * =============================================================================
 */

(function () {
  'use strict';

  function formatLakh(amount) {
    if (amount === null || amount === undefined || isNaN(Number(amount))) return '₹0.00 Lakh';
    const val = Number(amount);
    if (val >= 10000000) {
      return `₹${(val / 10000000).toFixed(2)} Cr`;
    }
    return `₹${(val / 100000).toFixed(2)} Lakh`;
  }

  function formatCurrencyFull(amount) {
    if (amount === null || amount === undefined || isNaN(Number(amount))) return '₹0.00';
    return '₹' + Number(amount).toLocaleString('en-IN', { maximumFractionDigits: 2 });
  }

  function formatDate(dStr) {
    if (!dStr) return 'Not Recorded';
    try {
      const d = new Date(dStr);
      if (isNaN(d.getTime())) return dStr;
      return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
    } catch {
      return dStr;
    }
  }

  function getRiskTheme(level) {
    const l = (level || '').toUpperCase();
    if (l === 'CRITICAL') {
      return {
        badgeBg: 'bg-error-container',
        badgeText: 'text-error',
        border: 'border-error',
        dotBg: 'bg-error',
        stroke: '#ba1a1a',
        label: 'Critical Risk',
        subtext: 'Severe variance detected',
        showRibbon: true
      };
    }
    if (l === 'HIGH') {
      return {
        badgeBg: 'bg-[#ffdad6]',
        badgeText: 'text-[#ba1a1a]',
        border: 'border-[#ba1a1a]',
        dotBg: 'bg-[#ba1a1a]',
        stroke: '#dc2626',
        label: 'High Risk',
        subtext: 'Material audit variance flagged',
        showRibbon: true
      };
    }
    if (l === 'MODERATE' || l === 'MEDIUM') {
      return {
        badgeBg: 'bg-[#ffe082]/30',
        badgeText: 'text-[#b45309]',
        border: 'border-[#f59e0b]',
        dotBg: 'bg-[#f59e0b]',
        stroke: '#d97706',
        label: 'Moderate Risk',
        subtext: 'Minor operational variance',
        showRibbon: false
      };
    }
    return {
      badgeBg: 'bg-surface-container',
      badgeText: 'text-[#00504a]',
      border: 'border-outline-variant',
      dotBg: 'bg-[#00504a]',
      stroke: '#006a60',
      label: 'Low Risk',
      subtext: 'Optimal compliance verified',
      showRibbon: false
    };
  }

  async function renderProjectDetailView({ params, container }) {
    const projectId = params?.id;

    if (!projectId) {
      container.innerHTML = `
        <main class="pl-64 pt-16 min-h-screen bg-background p-space-xl">
          <div class="bg-surface-container-lowest border border-outline-variant p-space-xl rounded-lg text-center max-w-xl mx-auto my-12">
            <span class="material-symbols-outlined text-outline text-5xl mb-space-sm">find_in_page</span>
            <h2 class="font-headline-sm text-headline-sm text-on-surface mb-space-xs">No Project ID Specified</h2>
            <p class="font-body-md text-body-md text-secondary mb-space-lg">Please select a project from the Master Registry.</p>
            <a href="#/projects" class="px-space-base py-space-sm bg-primary text-on-primary rounded font-title-sm">Return to Projects</a>
          </div>
        </main>
      `;
      return;
    }

    // 1. Loading Skeleton
    container.innerHTML = `
      <main class="pl-64 pt-16 min-h-screen bg-background p-space-xl">
        <div class="flex flex-col w-full gap-space-lg">
          <!-- Skeleton Caution Ribbon -->
          <div class="bg-surface-container-low border-l-4 border-outline p-space-md rounded-DEFAULT flex items-center justify-between animate-pulse">
            <div class="h-5 w-64 bg-surface-container rounded"></div>
            <div class="h-6 w-24 bg-surface-container rounded"></div>
          </div>
          <!-- Skeleton Header Card -->
          <div class="bg-surface-container-lowest border border-outline-variant p-space-xl rounded-lg animate-pulse flex flex-col lg:flex-row justify-between gap-space-xl">
            <div class="flex-1">
              <div class="h-4 w-36 bg-surface-container rounded mb-3"></div>
              <div class="h-8 w-3/4 bg-surface-container rounded mb-4"></div>
              <div class="h-4 w-1/2 bg-surface-container rounded"></div>
            </div>
            <div class="w-32 h-32 rounded-full bg-surface-container shrink-0"></div>
          </div>
        </div>
      </main>
    `;

    try {
      // 2. Fetch Project 360 view, Explanation, and Historical Risk Trackers in parallel
      const [projectRes, explanationRes, riskHistoryRes, projectHistoryRes] = await Promise.all([
        window.api.getProject(projectId),
        window.api.getProjectExplanation(projectId, false, false).catch(err => {
          console.warn('[ProjectDetail] Could not load structured explanation:', err);
          return null;
        }),
        window.api.getProjectRiskHistory(projectId, { sort_order: 'asc' }).catch(err => {
          console.warn('[ProjectDetail] Could not load risk history:', err);
          return [];
        }),
        window.api.getProjectHistory(projectId, { sort_order: 'asc' }).catch(err => {
          console.warn('[ProjectDetail] Could not load snapshot history:', err);
          return [];
        })
      ]);

      const project = projectRes || {};
      const explanation = explanationRes || {};

      const riskScore = Math.round(Number(explanation.risk_score ?? project.risk?.risk_score ?? 0));
      const riskLevel = (explanation.risk_level ?? project.risk?.risk_level ?? 'LOW').toUpperCase();
      const theme = getRiskTheme(riskLevel);

      // Assemble Chronological Historical Snapshots (Merging Risk History & Snapshots)
      const rawRiskHistory = Array.isArray(riskHistoryRes) ? riskHistoryRes : [];
      const rawSnapshots = Array.isArray(projectHistoryRes) ? projectHistoryRes : [];

      const snapshotMap = new Map();
      rawSnapshots.forEach(s => {
        if (s.snapshot_id) snapshotMap.set(s.snapshot_id, s);
      });

      const combinedSnapshots = rawRiskHistory.map(rh => {
        const matchingSnap = rh.snapshot_id ? snapshotMap.get(rh.snapshot_id) : null;
        return {
          ...rh,
          snapshot_date: matchingSnap?.snapshot_date || (rh.calculated_at ? rh.calculated_at.split('T')[0] : null),
          snapshot_datetime: matchingSnap?.snapshot_datetime || rh.calculated_at,
          project_status: matchingSnap?.project_status || project.current_status || 'In Progress',
          change_summary: matchingSnap?.change_summary || rh.change_summary || 'Audit evaluation checkpoint.',
          physical_progress_pct: matchingSnap?.physical_progress_pct,
          financial_progress_pct: matchingSnap?.financial_progress_pct,
          days_delayed: matchingSnap?.days_delayed,
          milestone_status: matchingSnap?.milestone_status
        };
      });

      if (combinedSnapshots.length === 0 && rawSnapshots.length > 0) {
        rawSnapshots.forEach(s => {
          combinedSnapshots.push({
            ...s,
            calculated_at: s.snapshot_datetime
          });
        });
      }

      // Generate Historical Trajectory Chart & Detector Breakdown
      const trajectoryChartHtml = window.ChartUtils ? window.ChartUtils.renderHistoricalRiskTrajectoryChart({
        snapshots: combinedSnapshots,
        currentRiskScore: riskScore,
        currentRiskLevel: riskLevel,
        height: 250,
        chartId: 'project-risk-trajectory-svg'
      }) : '';

      const detectorBreakdownHtml = (window.ChartUtils && combinedSnapshots.length > 0) ? window.ChartUtils.renderDetectorEvolutionBreakdown({
        snapshots: combinedSnapshots,
        height: 240,
        chartId: 'project-detector-evolution-svg'
      }) : '';

      // SVG Gauge Math (circumference = 2 * PI * 40 = 251.32)
      const circumference = 251.32;
      const progressOffset = Math.max(0, Math.min(circumference, circumference * (1 - riskScore / 100)));

      // Financials
      const fin = project.financial || {};
      const sanctioned = Number(fin.sanctioned_amount || 0);
      const released = Number(fin.released_amount || 0);
      const spent = Number(fin.expenditure_amount || 0);
      const balance = Number(fin.unspent_balance || (sanctioned - spent));
      const overrun = Number(fin.cost_overrun_amount || 0);
      const utilRate = sanctioned > 0 ? Math.min(100, (spent / sanctioned) * 100).toFixed(1) : 0;

      // Progress
      const prog = project.progress || {};
      const physicalPct = Number(prog.physical_percentage || 0).toFixed(1);
      const financialPct = Number(prog.financial_percentage || utilRate).toFixed(1);
      const progressGap = (Number(financialPct) - Number(physicalPct)).toFixed(1);

      // Extract Factors / Detectors
      const factors = explanation.factors || [];
      const getFactor = (detectorName) => factors.find(f => f.detector === detectorName || f.name?.toLowerCase().includes(detectorName.replace('_', ' ')));

      const costFactor = getFactor('cost_anomaly');
      const delayFactor = getFactor('delay_detection');
      const progressFactor = getFactor('progress_mismatch');
      const duplicateFactor = getFactor('duplicate_detection');
      const agencyFactor = getFactor('agency_pattern');

      // 3. Render Stitch View
      container.innerHTML = `
        <main class="pl-64 pt-16 min-h-screen bg-background p-space-xl">
          <div class="flex flex-col w-full gap-space-lg">

            <!-- Statutory Caution Ribbon (Visible if High/Critical) -->
            ${theme.showRibbon ? `
              <div class="bg-surface-container-low border-l-4 ${theme.border} p-space-md rounded-DEFAULT flex items-center justify-between shadow-sm">
                <div class="flex items-center gap-space-sm">
                  <span class="material-symbols-outlined text-error text-[20px]" style="font-variation-settings: 'FILL' 1;">warning</span>
                  <div class="flex flex-col">
                    <span class="font-title-sm text-title-sm text-on-surface">Statutory Audit Alert • Section 7(b) Fiscal Vigilance Protocol Invoked</span>
                    <span class="font-body-sm text-body-sm text-secondary">Material discrepancies detected against DPR guidelines. Disbursals require Nodal Officer sign-off.</span>
                  </div>
                </div>
                <span class="font-label-sm text-label-sm text-error uppercase font-bold tracking-wider px-space-sm py-space-2xs bg-error-container/60 rounded-DEFAULT border border-error/30">Action Mandatory</span>
              </div>
            ` : `
              <div class="bg-surface-container-low border-l-4 border-outline-variant p-space-md rounded-DEFAULT flex items-center justify-between shadow-sm">
                <div class="flex items-center gap-space-sm">
                  <span class="material-symbols-outlined text-secondary text-[20px]">verified_user</span>
                  <div class="flex flex-col">
                    <span class="font-title-sm text-title-sm text-on-surface">Public Works Governance Record • MoSPI MPLADS</span>
                    <span class="font-body-sm text-body-sm text-secondary">Comprehensive digital audit ledger registered under MIS Guidelines.</span>
                  </div>
                </div>
                <span class="font-label-sm text-label-sm text-secondary uppercase font-semibold px-space-sm py-space-2xs bg-surface-container-lowest rounded-DEFAULT border border-outline-variant">Verified</span>
              </div>
            `}

            <!-- Breadcrumb Navigation -->
            <nav aria-label="Administrative Ledger Path" class="flex items-center gap-space-xs font-body-sm text-body-sm text-secondary">
              <a href="#/projects" class="hover:text-primary transition-colors flex items-center gap-space-2xs">
                <span class="material-symbols-outlined text-[16px]">domain</span>
                <span>Projects</span>
              </a>
              <span class="material-symbols-outlined text-outline text-[14px]">chevron_right</span>
              <span>${project.state?.state_name || 'India'}</span>
              <span class="material-symbols-outlined text-outline text-[14px]">chevron_right</span>
              <span>${project.district_name || project.constituency?.constituency_name || 'District'}</span>
              <span class="material-symbols-outlined text-outline text-[14px]">chevron_right</span>
              <span class="font-title-sm text-title-sm text-on-surface font-semibold">${project.project_id}</span>
            </nav>

            <!-- Top Ledger Record Card -->
            <div class="bg-surface-container-lowest border border-outline-variant p-space-xl rounded-lg shadow-sm">
              <div class="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-space-xl">
                <!-- Primary Particulars -->
                <div class="flex-1 min-w-0">
                  <div class="flex flex-wrap items-center gap-space-sm mb-space-xs">
                    <span class="font-label-md text-label-md text-secondary tracking-wider uppercase font-semibold">MIS Reference ID:</span>
                    <span class="font-tabular-data text-tabular-data bg-surface-container text-primary font-bold px-space-sm py-0.5 rounded-DEFAULT border border-outline-variant/60">${project.project_id}</span>
                    <span class="inline-flex items-center gap-1 font-label-sm text-label-sm ${theme.badgeText} ${theme.badgeBg} px-space-sm py-space-2xs rounded-DEFAULT border ${theme.border} font-bold uppercase tracking-wider">
                      <span class="w-1.5 h-1.5 rounded-full ${theme.dotBg}"></span>
                      ${project.current_status || 'In Progress'}
                    </span>
                    <span class="font-label-sm text-label-sm text-secondary bg-surface-container-low px-space-sm py-0.5 rounded border border-outline-variant">${project.sector || 'General Infrastructure'}</span>
                  </div>
                  <h1 class="font-headline-lg text-headline-lg text-on-surface tracking-tight mb-space-xs text-balance font-bold">
                    ${project.project_title || 'Untitled MPLADS Developmental Work'}
                  </h1>
                  <p class="font-body-md text-body-md text-secondary mb-space-sm line-clamp-2">${project.project_description || 'No description recorded in central DPR ledger.'}</p>
                  <div class="flex flex-wrap items-center gap-x-space-lg gap-y-space-xs text-secondary font-body-sm text-body-sm mt-space-sm">
                    <div class="flex items-center gap-space-2xs">
                      <span class="material-symbols-outlined text-[18px] text-outline">location_on</span>
                      <span>${project.district_name || 'District'}, ${project.state?.state_name || 'State'} (${project.constituency?.constituency_name || 'Constituency'})</span>
                    </div>
                    <div class="flex items-center gap-space-2xs">
                      <span class="material-symbols-outlined text-[18px] text-outline">person</span>
                      <span>${project.mp_name || 'Hon Member of Parliament'} (${project.house_of_parliament || 'Lok Sabha'})</span>
                    </div>
                    <div class="flex items-center gap-space-2xs">
                      <span class="material-symbols-outlined text-[18px] text-outline">account_balance</span>
                      <span>Agency: ${project.implementing_agency || 'Unassigned Agency'}</span>
                    </div>
                    <div class="flex items-center gap-space-2xs">
                      <span class="material-symbols-outlined text-[18px] text-outline">event_available</span>
                      <span>Sanction Year: FY ${project.financial_year || '2024-25'}</span>
                    </div>
                  </div>
                </div>

                <!-- Circular Risk Score Gauge -->
                <div class="flex items-center gap-space-lg bg-surface-container-low border border-outline-variant p-space-base rounded-lg shrink-0">
                  <div class="relative w-24 h-24 flex items-center justify-center">
                    <svg aria-label="Risk assessment score circular gauge" class="w-full h-full -rotate-90" viewBox="0 0 100 100">
                      <!-- Outer Track -->
                      <circle cx="50" cy="50" fill="transparent" r="40" stroke="#e2e8f0" stroke-width="8"></circle>
                      <!-- Gauge Bar -->
                      <circle cx="50" cy="50" fill="transparent" r="40" stroke="${theme.stroke}" stroke-dasharray="251.32" stroke-dashoffset="${progressOffset}" stroke-linecap="square" stroke-width="8"></circle>
                    </svg>
                    <div class="absolute flex flex-col items-center justify-center text-center">
                      <span class="font-display text-display ${theme.badgeText} leading-none tracking-tight font-bold">${riskScore}</span>
                      <span class="font-label-sm text-label-sm text-secondary font-bold">/ 100</span>
                    </div>
                  </div>
                  <div class="flex flex-col">
                    <span class="font-label-sm text-label-sm uppercase tracking-wider ${theme.badgeText} font-bold ${theme.badgeBg} px-space-xs py-0.5 rounded-DEFAULT border ${theme.border} w-fit mb-1">${theme.label}</span>
                    <span class="font-title-sm text-title-sm text-on-surface font-semibold">Audit Health Score</span>
                    <span class="font-body-sm text-body-sm ${theme.badgeText} mt-0.5">${theme.subtext}</span>
                    <span class="font-label-sm text-label-sm text-outline mt-1">Rule Model: v3.12 (Automated MIS)</span>
                  </div>
                </div>
              </div>

              <!-- Quick Action Bar -->
              <div class="mt-space-lg pt-space-md border-t border-outline-variant flex flex-wrap items-center justify-between gap-space-md">
                <div class="flex items-center gap-space-sm text-secondary font-body-sm">
                  <span class="material-symbols-outlined text-outline text-[18px]">history</span>
                  <span>Last Automated Audit Scan: <strong>${formatDate(project.risk?.last_evaluated_at || new Date())}</strong></span>
                </div>
                <div class="flex items-center gap-space-sm">
                  <button id="recalculateBtn" type="button" class="px-space-base py-space-xs bg-primary text-on-primary font-label-md rounded border border-primary hover:bg-primary-container transition-colors flex items-center gap-space-xs shadow-sm font-semibold">
                    <span id="recalcIcon" class="material-symbols-outlined text-[16px]">bolt</span>
                    <span id="recalcText">Recalculate Live</span>
                  </button>
                  <button onclick="window.print()" type="button" class="px-space-base py-space-xs bg-surface-container-low text-on-surface font-label-md rounded border border-outline-variant hover:bg-surface-container transition-colors flex items-center gap-space-xs font-semibold">
                    <span class="material-symbols-outlined text-[16px] text-secondary">print</span>
                    <span>Print Dossier</span>
                  </button>
                </div>
              </div>
            </div>

            <!-- Historical Risk Trajectory & Multi-Detector Evolution Section -->
            <div class="flex flex-col gap-space-md">
              ${trajectoryChartHtml}
              ${detectorBreakdownHtml}
            </div>

            <!-- Primary Content Grid: Why Flagged (Left) + Financial Summary (Right) -->
            <div class="grid grid-cols-1 xl:grid-cols-12 gap-space-lg">
              
              <!-- Flag Reasons Matrix (8 Columns) -->
              <div class="xl:col-span-8 flex flex-col gap-space-md">
                <div class="bg-surface-container-lowest border border-outline-variant p-space-lg rounded-lg shadow-sm">
                  <div class="flex items-start justify-between border-b border-outline-variant pb-space-sm mb-space-base">
                    <div>
                      <h2 class="font-headline-sm text-headline-sm text-on-surface font-bold">Why was this flagged?</h2>
                      <p class="font-body-sm text-body-sm text-secondary mt-space-2xs">
                        ${explanation.summary || 'Empirical anomaly detection checks executed across fiscal, milestone, and procurement rules.'}
                      </p>
                    </div>
                    <span class="font-label-sm text-label-sm text-secondary font-mono bg-surface-container-low px-space-sm py-space-2xs rounded-DEFAULT border border-outline-variant">RULE-ENGINE-FLG</span>
                  </div>

                  <!-- 4 Exact Discrepancy Cards Grid -->
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-space-md">
                    
                    <!-- Card 1: Cost Anomaly -->
                    <div class="p-space-base bg-surface-container-lowest border border-outline-variant rounded-DEFAULT flex flex-col justify-between hover:bg-surface-container-low transition-colors">
                      <div>
                        <div class="flex items-center justify-between gap-space-sm mb-space-xs">
                          <div class="flex items-center gap-space-xs">
                            <span class="material-symbols-outlined ${costFactor?.triggered ? 'text-error' : 'text-secondary'} text-[18px]">payments</span>
                            <h3 class="font-title-sm text-title-sm text-on-surface font-semibold">Cost Anomaly</h3>
                          </div>
                          <span class="font-label-sm text-label-sm ${costFactor?.triggered ? 'text-error bg-error-container border-error/30' : 'text-secondary bg-surface-container border-outline-variant'} px-space-xs py-0.5 rounded-DEFAULT border font-bold uppercase">
                            ${costFactor?.severity || (costFactor?.triggered ? 'Critical' : 'Normal')}
                          </span>
                        </div>
                        <p class="font-body-sm text-body-sm text-on-surface-variant">
                          ${costFactor?.recommendation || (costFactor?.triggered ? 'Expenditure variance exceeds baseline peer thresholds.' : 'Expenditure aligns within normal peer median distribution.')}
                        </p>
                        ${costFactor?.evidence?.length ? `
                          <div class="mt-space-xs space-y-1">
                            ${costFactor.evidence.map(e => `
                              <div class="text-xs font-mono text-secondary flex items-start gap-1">
                                <span class="text-primary font-bold">•</span>
                                <span>${e.text}</span>
                              </div>
                            `).join('')}
                          </div>
                        ` : ''}
                      </div>
                      <div class="mt-space-md pt-space-xs border-t border-outline-variant/60 flex items-center justify-between text-secondary font-label-sm text-label-sm">
                        <span>Threshold: ${costFactor?.threshold ? costFactor.threshold.split(';')[0] : 'Ratio > 1.5×'}</span>
                        <span class="font-tabular-data font-semibold ${costFactor?.triggered ? 'text-error' : 'text-secondary'}">
                          ${costFactor?.contribution ? `+${costFactor.contribution.toFixed(1)} pts` : '0.0 pts'}
                        </span>
                      </div>
                    </div>

                    <!-- Card 2: Delay Detection -->
                    <div class="p-space-base bg-surface-container-lowest border border-outline-variant rounded-DEFAULT flex flex-col justify-between hover:bg-surface-container-low transition-colors">
                      <div>
                        <div class="flex items-center justify-between gap-space-sm mb-space-xs">
                          <div class="flex items-center gap-space-xs">
                            <span class="material-symbols-outlined ${delayFactor?.triggered ? 'text-[#ea580c]' : 'text-secondary'} text-[18px]">timer_off</span>
                            <h3 class="font-title-sm text-title-sm text-on-surface font-semibold">Delay Detection</h3>
                          </div>
                          <span class="font-label-sm text-label-sm ${delayFactor?.triggered ? 'text-[#ea580c] bg-surface-container-highest border-[#fed7aa]' : 'text-secondary bg-surface-container border-outline-variant'} px-space-xs py-0.5 rounded-DEFAULT border font-bold uppercase">
                            ${delayFactor?.severity || (delayFactor?.triggered ? 'High' : 'Normal')}
                          </span>
                        </div>
                        <p class="font-body-sm text-body-sm text-on-surface-variant">
                          ${delayFactor?.recommendation || (delayFactor?.triggered ? 'Project timeline extends significantly past planned completion.' : 'Project schedule aligns with approved milestones.')}
                        </p>
                        ${delayFactor?.evidence?.length ? `
                          <div class="mt-space-xs space-y-1">
                            ${delayFactor.evidence.map(e => `
                              <div class="text-xs font-mono text-secondary flex items-start gap-1">
                                <span class="text-primary font-bold">•</span>
                                <span>${e.text}</span>
                              </div>
                            `).join('')}
                          </div>
                        ` : ''}
                      </div>
                      <div class="mt-space-md pt-space-xs border-t border-outline-variant/60 flex items-center justify-between text-secondary font-label-sm text-label-sm">
                        <span>Expected: ${formatDate(project.expected_completion_date)}</span>
                        <span class="font-tabular-data font-semibold ${delayFactor?.triggered ? 'text-[#ea580c]' : 'text-secondary'}">
                          ${delayFactor?.contribution ? `+${delayFactor.contribution.toFixed(1)} pts` : '0.0 pts'}
                        </span>
                      </div>
                    </div>

                    <!-- Card 3: Progress Mismatch -->
                    <div class="p-space-base bg-surface-container-lowest border border-outline-variant rounded-DEFAULT flex flex-col justify-between hover:bg-surface-container-low transition-colors">
                      <div>
                        <div class="flex items-center justify-between gap-space-sm mb-space-xs">
                          <div class="flex items-center gap-space-xs">
                            <span class="material-symbols-outlined ${progressFactor?.triggered ? 'text-error' : 'text-secondary'} text-[18px]">query_stats</span>
                            <h3 class="font-title-sm text-title-sm text-on-surface font-semibold">Progress Mismatch</h3>
                          </div>
                          <span class="font-label-sm text-label-sm ${progressFactor?.triggered ? 'text-error bg-error-container border-error/30' : 'text-secondary bg-surface-container border-outline-variant'} px-space-xs py-0.5 rounded-DEFAULT border font-bold uppercase">
                            ${progressFactor?.severity || (progressFactor?.triggered ? 'Critical' : 'Normal')}
                          </span>
                        </div>
                        <p class="font-body-sm text-body-sm text-on-surface-variant">
                          ${progressFactor?.recommendation || (progressFactor?.triggered ? 'Financial disbursals substantially outpace verified physical milestone execution.' : 'Physical progress corresponds to fiscal drawdowns.')}
                        </p>
                        ${progressFactor?.evidence?.length ? `
                          <div class="mt-space-xs space-y-1">
                            ${progressFactor.evidence.map(e => `
                              <div class="text-xs font-mono text-secondary flex items-start gap-1">
                                <span class="text-primary font-bold">•</span>
                                <span>${e.text}</span>
                              </div>
                            `).join('')}
                          </div>
                        ` : ''}
                      </div>
                      <div class="mt-space-md pt-space-xs border-t border-outline-variant/60 flex items-center justify-between text-secondary font-label-sm text-label-sm">
                        <span>Physical: ${physicalPct}% | Draw: ${financialPct}%</span>
                        <span class="font-tabular-data font-semibold ${progressFactor?.triggered ? 'text-error' : 'text-secondary'}">
                          ${progressFactor?.contribution ? `+${progressFactor.contribution.toFixed(1)} pts` : '0.0 pts'}
                        </span>
                      </div>
                    </div>

                    <!-- Card 4: Duplicate / Agency Pattern -->
                    <div class="p-space-base bg-surface-container-lowest border border-outline-variant rounded-DEFAULT flex flex-col justify-between hover:bg-surface-container-low transition-colors">
                      <div>
                        <div class="flex items-center justify-between gap-space-sm mb-space-xs">
                          <div class="flex items-center gap-space-xs">
                            <span class="material-symbols-outlined ${(agencyFactor?.triggered || duplicateFactor?.triggered) ? 'text-primary' : 'text-secondary'} text-[18px]">corporate_fare</span>
                            <h3 class="font-title-sm text-title-sm text-on-surface font-semibold">Agency & Spatial Pattern</h3>
                          </div>
                          <span class="font-label-sm text-label-sm ${(agencyFactor?.triggered || duplicateFactor?.triggered) ? 'text-primary bg-primary-fixed border-outline-variant' : 'text-secondary bg-surface-container border-outline-variant'} px-space-xs py-0.5 rounded-DEFAULT border font-bold uppercase">
                            ${agencyFactor?.severity || duplicateFactor?.severity || 'Normal'}
                          </span>
                        </div>
                        <p class="font-body-sm text-body-sm text-on-surface-variant">
                          ${agencyFactor?.recommendation || duplicateFactor?.recommendation || 'Historical agency performance and spatial duplication screening show standard operational levels.'}
                        </p>
                        ${agencyFactor?.evidence?.length ? `
                          <div class="mt-space-xs space-y-1">
                            ${agencyFactor.evidence.map(e => `
                              <div class="text-xs font-mono text-secondary flex items-start gap-1">
                                <span class="text-primary font-bold">•</span>
                                <span>${e.text}</span>
                              </div>
                            `).join('')}
                          </div>
                        ` : ''}
                      </div>
                      <div class="mt-space-md pt-space-xs border-t border-outline-variant/60 flex items-center justify-between text-secondary font-label-sm text-label-sm">
                        <span>Agency: ${project.implementing_agency ? project.implementing_agency.slice(0, 22) + '...' : 'N/A'}</span>
                        <span class="font-tabular-data font-semibold text-primary">
                          ${agencyFactor?.contribution ? `+${agencyFactor.contribution.toFixed(1)} pts` : '0.0 pts'}
                        </span>
                      </div>
                    </div>

                  </div>
                </div>

                <!-- Inspection Dossier & Dual Progress Track -->
                <div class="bg-surface-container-lowest border border-outline-variant p-space-lg rounded-lg shadow-sm">
                  <h3 class="font-headline-sm text-headline-sm text-on-surface font-bold mb-space-xs">Physical vs Financial Progress Trajectory</h3>
                  <p class="font-body-sm text-body-sm text-secondary mb-space-base">Comparative reconciliation between certified site milestones and sub-treasury drawdowns.</p>
                  
                  <div class="space-y-space-md">
                    <div>
                      <div class="flex items-center justify-between font-label-md text-label-md mb-1">
                        <span class="text-secondary font-semibold">Financial Expenditure Drawdown</span>
                        <span class="font-tabular-data font-bold text-on-surface">${financialPct}% (${formatLakh(spent)} spent of ${formatLakh(sanctioned)})</span>
                      </div>
                      <div class="w-full h-3 bg-surface-container rounded-full overflow-hidden">
                        <div class="h-full bg-primary rounded-full" style="width: ${Math.min(100, Math.max(0, financialPct))}%"></div>
                      </div>
                    </div>

                    <div>
                      <div class="flex items-center justify-between font-label-md text-label-md mb-1">
                        <span class="text-secondary font-semibold">Certified Physical Ground Progress</span>
                        <span class="font-tabular-data font-bold text-on-surface">${physicalPct}% completed</span>
                      </div>
                      <div class="w-full h-3 bg-surface-container rounded-full overflow-hidden">
                        <div class="h-full bg-tertiary-container rounded-full" style="width: ${Math.min(100, Math.max(0, physicalPct))}%"></div>
                      </div>
                    </div>

                    ${Math.abs(Number(progressGap)) > 10 ? `
                      <div class="p-space-sm bg-surface-container-low border border-outline-variant rounded flex items-center justify-between text-body-sm">
                        <span class="text-secondary">Progress Lag Discrepancy Index:</span>
                        <span class="font-tabular-data font-bold ${Number(progressGap) > 0 ? 'text-error' : 'text-on-surface'}">
                          ${Number(progressGap) > 0 ? `+${progressGap}% draw surplus` : `${progressGap}% physical advance`}
                        </span>
                      </div>
                    ` : ''}
                  </div>
                </div>
              </div>

              <!-- Right Column: Financial Summary & Project Milestones (4 Columns) -->
              <div class="xl:col-span-4 flex flex-col gap-space-md">
                
                <!-- Financial Summary Card -->
                <div class="bg-surface-container-lowest border border-outline-variant p-space-lg rounded-lg shadow-sm">
                  <h3 class="font-title-sm text-title-sm text-on-surface font-bold uppercase tracking-wider mb-space-base pb-space-xs border-b border-outline-variant">
                    Fiscal Summary & Allocations
                  </h3>
                  <dl class="space-y-space-sm text-body-sm">
                    <div class="flex justify-between py-1 border-b border-outline-variant/40">
                      <dt class="text-secondary">Sanctioned Budget</dt>
                      <dd class="font-tabular-data font-bold text-on-surface">${formatCurrencyFull(sanctioned)}</dd>
                    </div>
                    <div class="flex justify-between py-1 border-b border-outline-variant/40">
                      <dt class="text-secondary">Released Funds</dt>
                      <dd class="font-tabular-data font-bold text-primary">${formatCurrencyFull(released)}</dd>
                    </div>
                    <div class="flex justify-between py-1 border-b border-outline-variant/40">
                      <dt class="text-secondary">Total Expenditure</dt>
                      <dd class="font-tabular-data font-bold text-on-surface">${formatCurrencyFull(spent)}</dd>
                    </div>
                    <div class="flex justify-between py-1 border-b border-outline-variant/40">
                      <dt class="text-secondary">Unspent Treasury Balance</dt>
                      <dd class="font-tabular-data font-bold text-secondary">${formatCurrencyFull(balance)}</dd>
                    </div>
                    ${overrun > 0 ? `
                      <div class="flex justify-between py-1 border-b border-outline-variant/40">
                        <dt class="text-error font-semibold">Cost Overrun</dt>
                        <dd class="font-tabular-data font-bold text-error">+${formatCurrencyFull(overrun)}</dd>
                      </div>
                    ` : ''}
                    <div class="flex justify-between pt-2 font-title-sm">
                      <dt class="text-on-surface font-semibold">Fund Utilization Rate</dt>
                      <dd class="font-tabular-data font-bold text-primary">${utilRate}%</dd>
                    </div>
                  </dl>
                </div>

                <!-- Milestone & Timeline Particulars -->
                <div class="bg-surface-container-lowest border border-outline-variant p-space-lg rounded-lg shadow-sm">
                  <h3 class="font-title-sm text-title-sm text-on-surface font-bold uppercase tracking-wider mb-space-base pb-space-xs border-b border-outline-variant">
                    Milestones & Dates
                  </h3>
                  <div class="space-y-space-sm font-body-sm">
                    <div class="flex items-center justify-between">
                      <span class="text-secondary">Sanction Date</span>
                      <span class="font-tabular-data font-medium text-on-surface">${formatDate(project.sanction_date)}</span>
                    </div>
                    <div class="flex items-center justify-between">
                      <span class="text-secondary">Work Order Date</span>
                      <span class="font-tabular-data font-medium text-on-surface">${formatDate(project.work_order_date)}</span>
                    </div>
                    <div class="flex items-center justify-between">
                      <span class="text-secondary">Target Completion</span>
                      <span class="font-tabular-data font-medium text-on-surface">${formatDate(project.expected_completion_date)}</span>
                    </div>
                    <div class="flex items-center justify-between">
                      <span class="text-secondary">Actual Completion</span>
                      <span class="font-tabular-data font-medium ${project.actual_completion_date ? 'text-on-surface' : 'text-secondary'}">
                        ${formatDate(project.actual_completion_date)}
                      </span>
                    </div>
                  </div>
                </div>

                <!-- Action Button: View In Queue -->
                <div class="bg-surface-container-low border border-outline-variant p-space-base rounded-lg text-center">
                  <p class="font-body-sm text-body-sm text-secondary mb-space-sm">Need formal audit triage or inquiry notice issuance?</p>
                  <a href="#/investigations" class="block w-full py-space-xs bg-surface-container-lowest border border-outline-variant hover:bg-surface-container rounded text-on-surface font-label-md font-semibold text-center transition-colors">
                    Open Investigation Queue
                  </a>
                </div>

              </div>

            </div>

          </div>
        </main>
      `;

      // 4. Bind Recalculate Live Button
      const recalcBtn = document.getElementById('recalculateBtn');
      if (recalcBtn) {
        recalcBtn.addEventListener('click', async () => {
          const icon = document.getElementById('recalcIcon');
          const text = document.getElementById('recalcText');
          if (icon) icon.classList.add('animate-spin');
          if (text) text.textContent = 'Evaluating Engine...';
          recalcBtn.disabled = true;

          try {
            await window.api.recalculateProjectRisk(projectId);
            // Re-render view with fresh live data
            await renderProjectDetailView({ params, container });
          } catch (err) {
            console.error('[ProjectDetail] Recalculate failed:', err);
            alert(`Unable to recalculate risk: ${err.message}`);
            if (icon) icon.classList.remove('animate-spin');
            if (text) text.textContent = 'Recalculate Live';
            recalcBtn.disabled = false;
          }
        });
      }

      // 5. Bind Historical Risk Trajectory Node Hover Tooltips
      const trajectoryNodes = container.querySelectorAll('.trajectory-node-group');
      trajectoryNodes.forEach(node => {
        node.addEventListener('mouseenter', (e) => {
          const raw = node.getAttribute('data-snapshot-payload');
          if (!raw) return;
          try {
            const data = JSON.parse(decodeURIComponent(raw));
            const tierTheme = getRiskTheme(data.level);
            const html = `
              <div class="p-2 space-y-1 text-xs">
                <div class="flex items-center justify-between gap-2 border-b border-outline-variant/60 pb-1">
                  <span class="font-bold text-on-surface font-tabular-data">Snapshot #${data.rev} • ${data.date}</span>
                  <span class="px-1.5 py-0.5 rounded text-[10px] font-bold ${tierTheme.badgeText} ${tierTheme.badgeBg} border ${tierTheme.border}">
                    ${data.level} (${data.score}/100)
                  </span>
                </div>
                <div class="text-secondary">
                  <span class="font-semibold text-on-surface">Status:</span> ${data.status}
                </div>
                ${data.phys !== null && data.fin !== null ? `
                  <div class="text-secondary font-tabular-data">
                    <span class="font-semibold text-on-surface">Progress:</span> ${data.phys}% physical / ${data.fin}% financial
                  </div>
                ` : ''}
                ${data.delay !== null && Number(data.delay) > 0 ? `
                  <div class="text-error font-tabular-data">
                    <span class="font-semibold">Schedule Slippage:</span> +${data.delay} days
                  </div>
                ` : ''}
                <div class="text-on-surface mt-1 border-t border-outline-variant/40 pt-1 text-[11px] leading-snug">
                  ${data.summary}
                </div>
              </div>
            `;
            window.ChartUtils?.showTooltip(e, html);
          } catch (err) {
            console.error('Error rendering snapshot tooltip:', err);
          }
        });
        node.addEventListener('mousemove', (e) => {
          const tip = document.getElementById('mplads-chart-tooltip');
          if (tip && tip.style.opacity === '1') {
            const x = e.clientX + 14;
            const y = e.clientY + 14;
            tip.style.left = `${Math.min(x, window.innerWidth - 300)}px`;
            tip.style.top = `${Math.min(y, window.innerHeight - 100)}px`;
          }
        });
        node.addEventListener('mouseleave', () => {
          window.ChartUtils?.hideTooltip();
        });
      });

      // 6. Bind Detector Node Circle Tooltips
      const detectorCircles = container.querySelectorAll('#project-detector-evolution-svg circle[data-detector-name]');
      detectorCircles.forEach(circle => {
        circle.addEventListener('mouseenter', (e) => {
          const name = circle.getAttribute('data-detector-name');
          const score = circle.getAttribute('data-detector-score');
          const rev = circle.getAttribute('data-milestone-rev');
          const color = circle.getAttribute('fill');
          const html = `
            <div class="p-1.5 text-xs">
              <div class="flex items-center gap-1.5 font-bold mb-0.5" style="color: ${color};">
                <span class="w-2 h-2 rounded-full" style="background-color: ${color};"></span>
                <span>${name}</span>
              </div>
              <div class="text-secondary">Snapshot #${rev}: <b class="text-on-surface font-tabular-data">${score} / 100</b></div>
            </div>
          `;
          window.ChartUtils?.showTooltip(e, html);
        });
        circle.addEventListener('mouseleave', () => {
          window.ChartUtils?.hideTooltip();
        });
      });

      // 7. Bind Detector Toggle Buttons (interactive curve show/hide)
      const toggleButtons = container.querySelectorAll('.detector-toggle-btn');
      toggleButtons.forEach(btn => {
        btn.addEventListener('click', () => {
          const key = btn.getAttribute('data-detector-key');
          const seriesGroup = document.getElementById(`detector-series-${key}`);
          if (!seriesGroup) return;
          const isHidden = seriesGroup.classList.contains('hidden');
          if (isHidden) {
            seriesGroup.classList.remove('hidden');
            btn.style.opacity = '1';
            btn.classList.remove('line-through');
          } else {
            seriesGroup.classList.add('hidden');
            btn.style.opacity = '0.4';
            btn.classList.add('line-through');
          }
        });
      });

    } catch (err) {
      console.error('[ProjectDetail] View render error:', err);
      container.innerHTML = `
        <main class="pl-64 pt-16 min-h-screen bg-background p-space-xl">
          <div class="bg-surface-container-lowest border border-error p-space-xl rounded-lg text-center max-w-xl mx-auto my-12">
            <span class="material-symbols-outlined text-error text-5xl mb-space-sm">error</span>
            <h2 class="font-headline-sm text-headline-sm text-on-surface mb-space-xs">Unable to Load Project Details</h2>
            <p class="font-body-md text-body-md text-secondary mb-space-lg">${err.message || 'Project not found in central database.'}</p>
            <div class="flex justify-center gap-space-sm">
              <button onclick="window.location.reload()" class="px-space-base py-space-sm bg-primary text-on-primary rounded font-title-sm">Retry</button>
              <a href="#/projects" class="px-space-base py-space-sm bg-surface-container border border-outline-variant text-on-surface rounded font-title-sm">Back to Registry</a>
            </div>
          </div>
        </main>
      `;
    }
  }

  // Export to global scope
  window.renderProjectDetailView = renderProjectDetailView;
})();
