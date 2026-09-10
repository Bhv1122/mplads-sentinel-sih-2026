/**
 * frontend/js/components/chart_utils.js
 * =============================================================================
 * Lightweight, Production-Grade SVG Chart Utilities for MPLADS Governance.
 * Built for high-performance server-aggregated data visualization.
 * Adheres strictly to the Google Stitch Design Tokens:
 * Primary: #00236f, Critical: #ba1a1a, High: #d97706, Medium: #eab308, Low: #00312d.
 * =============================================================================
 */

(function () {
  'use strict';

  // Floating tooltip singleton
  let tooltipEl = null;

  function getOrCreateTooltip() {
    if (!tooltipEl) {
      tooltipEl = document.createElement('div');
      tooltipEl.id = 'mplads-chart-tooltip';
      tooltipEl.className = 'fixed z-50 pointer-events-none px-3 py-2 text-xs rounded shadow-lg bg-surface-container-highest text-on-surface border border-outline-variant opacity-0 transition-opacity duration-150 backdrop-blur-sm';
      tooltipEl.style.maxWidth = '280px';
      document.body.appendChild(tooltipEl);
    }
    return tooltipEl;
  }

  function showTooltip(e, html) {
    const tip = getOrCreateTooltip();
    tip.innerHTML = html;
    tip.style.opacity = '1';
    const x = e.clientX + 14;
    const y = e.clientY + 14;
    tip.style.left = `${Math.min(x, window.innerWidth - 300)}px`;
    tip.style.top = `${Math.min(y, window.innerHeight - 100)}px`;
  }

  function hideTooltip() {
    if (tooltipEl) {
      tooltipEl.style.opacity = '0';
    }
  }

  const ChartUtils = {
    showTooltip,
    hideTooltip,

    /**
     * Renders a responsive SVG Donut Chart with segmented arcs.
     */
    renderDonutChart({
      slices = [],
      total = 0,
      size = 180,
      strokeWidth = 14,
      centerText = '',
      centerSubtext = 'Assessed',
      onClick = null,
    }) {
      const radius = 40;
      const circumference = 2 * Math.PI * radius; // ~251.327
      const effectiveTotal = total > 0 ? total : slices.reduce((sum, s) => sum + (s.value || 0), 0) || 1;

      let accumulatedOffset = 0;
      const arcElements = slices.map((slice, idx) => {
        const val = Math.max(0, slice.value || 0);
        const ratio = val / effectiveTotal;
        const strokeDash = ratio * circumference;
        const offset = -accumulatedOffset;
        accumulatedOffset += strokeDash;

        const sliceColor = slice.color || '#00236f';
        const pct = ((val / effectiveTotal) * 100).toFixed(1);

        return `
          <circle
            cx="50" cy="50" r="${radius}"
            fill="transparent"
            stroke="${sliceColor}"
            stroke-width="${strokeWidth}"
            stroke-dasharray="${strokeDash.toFixed(2)} ${circumference.toFixed(2)}"
            stroke-dashoffset="${offset.toFixed(2)}"
            class="transition-all duration-300 cursor-pointer hover:opacity-80"
            data-tier="${slice.key || slice.label}"
            data-value="${val}"
            data-pct="${pct}"
            data-label="${slice.label}"
          />
        `;
      }).join('');

      return `
        <div class="relative flex items-center justify-center" style="width: ${size}px; height: ${size}px;">
          <svg class="w-full h-full -rotate-90" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="${radius}" fill="transparent" stroke="#f1f5f9" stroke-width="${strokeWidth}" />
            ${arcElements}
          </svg>
          <div class="absolute flex flex-col items-center justify-center text-center pointer-events-none">
            <span class="font-display text-2xl font-bold text-on-surface font-tabular-data leading-none">${centerText || total}</span>
            <span class="font-label-sm text-[10px] text-secondary uppercase font-semibold tracking-wider mt-1">${centerSubtext}</span>
          </div>
        </div>
      `;
    },

    /**
     * Renders a ranked horizontal bar chart (e.g. for States or Districts).
     */
    renderHorizontalBarChart({
      items = [],
      valueKey = 'value',
      labelKey = 'label',
      sublabelKey = null,
      maxVal = null,
      barColor = '#00236f',
      highlightKey = null,
      highlightValue = null,
      onClickItem = null,
      formatValue = (v) => v,
    }) {
      if (!items || items.length === 0) {
        return `
          <div class="py-8 text-center text-secondary text-sm">
            <span class="material-symbols-outlined text-3xl mb-1 text-outline">bar_chart</span>
            <p>No comparative records match the applied criteria.</p>
          </div>
        `;
      }

      const calculatedMax = maxVal !== null ? maxVal : Math.max(...items.map(it => Number(it[valueKey]) || 0), 1);

      return `
        <div class="flex flex-col gap-2.5 w-full">
          ${items.map((item, idx) => {
            const rawVal = Number(item[valueKey]) || 0;
            const pct = Math.min(100, Math.max(0, (rawVal / calculatedMax) * 100));
            const label = item[labelKey] || 'Unknown';
            const sublabel = sublabelKey && item[sublabelKey] ? item[sublabelKey] : '';
            const isHighlighted = highlightKey && item[highlightKey] === highlightValue;

            let dynamicBarColor = barColor;
            if (typeof barColor === 'function') {
              dynamicBarColor = barColor(item);
            }

            return `
              <div class="group flex flex-col gap-1 cursor-pointer transition-colors p-1.5 rounded hover:bg-surface-container-low"
                   data-chart-item="${encodeURIComponent(JSON.stringify(item))}"
                   data-idx="${idx}">
                <div class="flex items-center justify-between text-xs">
                  <div class="flex items-center gap-1.5 overflow-hidden max-w-[70%]">
                    <span class="font-semibold text-on-surface truncate" title="${label}">${label}</span>
                    ${sublabel ? `<span class="text-secondary text-[11px] truncate">(${sublabel})</span>` : ''}
                  </div>
                  <span class="font-tabular-data font-bold text-on-surface">${formatValue(rawVal, item)}</span>
                </div>
                <div class="w-full bg-surface-container h-2 rounded-full overflow-hidden flex">
                  <div class="h-full rounded-full transition-all duration-500"
                       style="width: ${pct}%; background-color: ${dynamicBarColor};"></div>
                </div>
              </div>
            `;
          }).join('')}
        </div>
      `;
    },

    /**
     * Renders a vertical histogram / column chart (e.g. for Delay or Cost Anomaly buckets).
     */
    renderHistogramChart({
      buckets = {},
      height = 160,
      activeBucket = null,
      barColor = '#00236f',
      formatLabel = (l) => l,
      formatValue = (v) => v,
    }) {
      const entries = Object.entries(buckets);
      if (entries.length === 0) {
        return `<div class="text-center py-6 text-secondary text-sm">No histogram data available.</div>`;
      }

      const maxVal = Math.max(...entries.map(([_, count]) => count), 1);

      return `
        <div class="w-full flex flex-col justify-end pt-4" style="height: ${height}px;">
          <div class="flex items-end justify-between gap-2 h-full pb-2 border-b border-outline-variant">
            ${entries.map(([rangeLabel, count]) => {
              const heightPct = Math.max(4, (count / maxVal) * 100);
              const isSelected = activeBucket === rangeLabel;
              const color = typeof barColor === 'function' ? barColor(rangeLabel, count) : barColor;

              return `
                <div class="flex-1 flex flex-col items-center justify-end h-full group relative cursor-pointer"
                     data-bucket="${rangeLabel}"
                     data-count="${count}">
                  <span class="text-[10px] font-tabular-data font-semibold text-secondary mb-1 opacity-80 group-hover:opacity-100 group-hover:text-primary">
                    ${formatValue(count)}
                  </span>
                  <div class="w-full max-w-[48px] rounded-t transition-all duration-300 ${isSelected ? 'ring-2 ring-primary ring-offset-1' : ''}"
                       style="height: ${heightPct}%; background-color: ${color};">
                  </div>
                  <div class="absolute -top-7 px-2 py-0.5 rounded text-[10px] bg-surface-container-highest text-on-surface shadow-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-20">
                    ${rangeLabel}: <b>${count}</b> works
                  </div>
                </div>
              `;
            }).join('')}
          </div>
          <!-- X Axis Labels -->
          <div class="flex items-center justify-between gap-2 pt-2 text-[10px] text-secondary">
            ${entries.map(([rangeLabel]) => `
              <div class="flex-1 text-center font-medium truncate" title="${rangeLabel}">
                ${formatLabel(rangeLabel)}
              </div>
            `).join('')}
          </div>
        </div>
      `;
    },

    /**
     * Renders an interactive SVG multi-series temporal trend line chart.
     */
    renderTrendLineChart({
      points = [],
      series = [
        { key: 'project_count', label: 'Works Intake', color: '#00236f' },
        { key: 'high_risk_count', label: 'High/Critical Works', color: '#ba1a1a' }
      ],
      height = 200,
    }) {
      if (!points || points.length === 0) {
        return `
          <div class="py-12 text-center text-secondary text-sm">
            <span class="material-symbols-outlined text-4xl mb-1 text-outline">show_chart</span>
            <p>Insufficient historical data points to plot temporal trends for selected filters.</p>
          </div>
        `;
      }

      // Chart margins inside SVG viewbox (600 x 220)
      const svgWidth = 600;
      const svgHeight = 220;
      const padLeft = 45;
      const padRight = 20;
      const padTop = 20;
      const padBottom = 35;
      const plotWidth = svgWidth - padLeft - padRight;
      const plotHeight = svgHeight - padTop - padBottom;

      // Find max value across all requested series
      let globalMax = 1;
      series.forEach(s => {
        points.forEach(p => {
          const v = Number(p[s.key]) || 0;
          if (v > globalMax) globalMax = v;
        });
      });
      // Round max up slightly for nice top gridline
      const yMax = Math.ceil(globalMax * 1.15) || 1;

      // Calculate coordinates for each series
      const n = points.length;
      const stepX = n > 1 ? plotWidth / (n - 1) : plotWidth / 2;

      const seriesPaths = series.map(s => {
        const coords = points.map((p, idx) => {
          const val = Number(p[s.key]) || 0;
          const x = padLeft + (n > 1 ? idx * stepX : plotWidth / 2);
          const y = padTop + plotHeight - (val / yMax) * plotHeight;
          return { x, y, val, period: p.period, point: p };
        });

        // SVG polyline points string
        const polyPoints = coords.map(c => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ');

        // Area path
        const first = coords[0];
        const last = coords[coords.length - 1];
        const zeroY = padTop + plotHeight;
        const areaPath = `M ${first.x.toFixed(1)},${zeroY} ` +
          coords.map(c => `L ${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ') +
          ` L ${last.x.toFixed(1)},${zeroY} Z`;

        // Points circles
        const circles = coords.map(c => `
          <circle cx="${c.x.toFixed(1)}" cy="${c.y.toFixed(1)}" r="4"
                  fill="${s.color}" stroke="#ffffff" stroke-width="2"
                  class="cursor-pointer transition-transform hover:scale-150"
                  data-period="${c.period}"
                  data-label="${s.label}"
                  data-val="${c.val}" />
        `).join('');

        return {
          color: s.color,
          label: s.label,
          polyPoints,
          areaPath,
          circles,
          coords
        };
      });

      // Grid lines (4 horizontal steps)
      const gridSteps = 4;
      const gridLines = [];
      for (let i = 0; i <= gridSteps; i++) {
        const yVal = Math.round((yMax / gridSteps) * i);
        const yPos = padTop + plotHeight - (i / gridSteps) * plotHeight;
        gridLines.push(`
          <line x1="${padLeft}" y1="${yPos}" x2="${svgWidth - padRight}" y2="${yPos}"
                stroke="#e2e8f0" stroke-width="1" stroke-dasharray="3,3" />
          <text x="${padLeft - 6}" y="${yPos + 3}" text-anchor="end"
                class="text-[9px] fill-secondary font-tabular-data">${yVal}</text>
        `);
      }

      // X-axis period labels
      const xLabels = points.map((p, idx) => {
        // Show max ~6 labels to prevent clutter
        const step = Math.max(1, Math.floor(points.length / 6));
        if (idx % step !== 0 && idx !== points.length - 1) return '';
        const x = padLeft + (n > 1 ? idx * stepX : plotWidth / 2);
        return `
          <text x="${x}" y="${svgHeight - 10}" text-anchor="middle"
                class="text-[9px] fill-secondary font-medium">${p.period}</text>
        `;
      }).join('');

      return `
        <div class="w-full relative">
          <svg viewBox="0 0 ${svgWidth} ${svgHeight}" class="w-full h-auto overflow-visible" style="max-height: ${height}px;">
            <!-- Gridlines -->
            ${gridLines.join('')}

            <!-- Axis lines -->
            <line x1="${padLeft}" y1="${padTop + plotHeight}" x2="${svgWidth - padRight}" y2="${padTop + plotHeight}" stroke="#cbd5e1" stroke-width="1" />
            <line x1="${padLeft}" y1="${padTop}" x2="${padLeft}" y2="${padTop + plotHeight}" stroke="#cbd5e1" stroke-width="1" />

            <!-- Series Areas & Lines -->
            ${seriesPaths.map(s => `
              <path d="${s.areaPath}" fill="${s.color}" fill-opacity="0.08" />
              <polyline fill="none" stroke="${s.color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" points="${s.polyPoints}" />
              ${s.circles}
            `).join('')}

            <!-- X Labels -->
            ${xLabels}
          </svg>

          <!-- Legend -->
          <div class="flex items-center justify-center gap-6 mt-3 text-xs text-secondary border-t border-outline-variant/60 pt-2">
            ${series.map(s => `
              <div class="flex items-center gap-1.5">
                <span class="w-3 h-1 rounded-full" style="background-color: ${s.color};"></span>
                <span class="font-medium text-on-surface">${s.label}</span>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    },

    /**
     * Renders a chronological project historical risk trajectory line chart.
     * Displays every available snapshot without downsampling or averaging.
     * Includes threshold bands, current vs baseline metrics, and interactive nodes.
     */
    renderHistoricalRiskTrajectoryChart({
      snapshots = [],
      currentRiskScore = null,
      currentRiskLevel = null,
      height = 240,
      chartId = 'risk-trajectory-svg',
    }) {
      if (!snapshots || snapshots.length === 0) {
        return `
          <div class="py-10 px-6 text-center bg-surface-container-low rounded-lg border border-outline-variant/60">
            <span class="material-symbols-outlined text-4xl text-outline mb-2">history_toggle_off</span>
            <h4 class="font-title-sm text-title-sm text-on-surface font-semibold">Initial Baseline Snapshot Registered</h4>
            <p class="font-body-sm text-body-sm text-secondary max-w-md mx-auto mt-1">
              No historical revisions have been recorded for this project yet. Longitudinal temporal trajectory
              tracking will activate continuously as subsequent milestone inspections and fiscal updates are ingested.
            </p>
          </div>
        `;
      }

      // Sort snapshots chronologically ascending (oldest to newest)
      const sortedSnapshots = [...snapshots].sort((a, b) => {
        const tA = new Date(a.snapshot_datetime || a.calculated_at || a.snapshot_date || 0).getTime();
        const tB = new Date(b.snapshot_datetime || b.calculated_at || b.snapshot_date || 0).getTime();
        return tA - tB;
      });

      const n = sortedSnapshots.length;
      const firstSnap = sortedSnapshots[0];
      const lastSnap = sortedSnapshots[n - 1];

      const baselineScore = Number(firstSnap.overall_risk_score ?? 0);
      const latestScore = Number(currentRiskScore !== null && currentRiskScore !== undefined ? currentRiskScore : lastSnap.overall_risk_score ?? 0);
      const scoreDelta = latestScore - baselineScore;

      // Peak & Min Risk
      let peakScore = -1;
      let peakDate = '';
      let minScore = 101;
      let minDate = '';

      sortedSnapshots.forEach(s => {
        const sc = Number(s.overall_risk_score ?? 0);
        const dtStr = s.snapshot_date || s.calculated_at || s.snapshot_datetime;
        if (sc > peakScore) {
          peakScore = sc;
          peakDate = dtStr;
        }
        if (sc < minScore) {
          minScore = sc;
          minDate = dtStr;
        }
      });

      function formatShortDate(dStr) {
        if (!dStr) return 'N/A';
        try {
          const d = new Date(dStr);
          if (isNaN(d.getTime())) return dStr;
          return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' });
        } catch {
          return dStr;
        }
      }

      function getTierColor(score) {
        const num = Number(score) || 0;
        if (num >= 70) return { stroke: '#ba1a1a', fill: '#ba1a1a', bg: 'bg-error-container', text: 'text-error', label: 'Critical' };
        if (num >= 50) return { stroke: '#dc2626', fill: '#dc2626', bg: 'bg-[#ffdad6]', text: 'text-[#ba1a1a]', label: 'High' };
        if (num >= 30) return { stroke: '#d97706', fill: '#d97706', bg: 'bg-[#ffe082]/30', text: 'text-[#b45309]', label: 'Moderate' };
        return { stroke: '#006a60', fill: '#006a60', bg: 'bg-surface-container', text: 'text-[#00504a]', label: 'Low' };
      }

      // Delta Pill styling
      let deltaBadge = '';
      if (scoreDelta > 0) {
        deltaBadge = `
          <span class="inline-flex items-center gap-1 font-label-sm text-label-sm font-bold text-error bg-error-container/70 border border-error/30 px-2 py-0.5 rounded-full">
            <span class="material-symbols-outlined text-[14px]">trending_up</span>
            +${scoreDelta.toFixed(1)} pts Escalation
          </span>
        `;
      } else if (scoreDelta < 0) {
        deltaBadge = `
          <span class="inline-flex items-center gap-1 font-label-sm text-label-sm font-bold text-[#006a60] bg-[#e6f4ea] border border-[#a8dab5] px-2 py-0.5 rounded-full">
            <span class="material-symbols-outlined text-[14px]">trending_down</span>
            ${scoreDelta.toFixed(1)} pts De-escalation
          </span>
        `;
      } else {
        deltaBadge = `
          <span class="inline-flex items-center gap-1 font-label-sm text-label-sm font-semibold text-secondary bg-surface-container border border-outline-variant px-2 py-0.5 rounded-full">
            <span class="material-symbols-outlined text-[14px]">trending_flat</span>
            Stable (0.0 pts drift)
          </span>
        `;
      }

      // SVG Dimensions & Margins
      const svgWidth = 720;
      const svgHeight = 250;
      const padLeft = 46;
      const padRight = 32;
      const padTop = 22;
      const padBottom = 48;
      const plotWidth = svgWidth - padLeft - padRight;
      const plotHeight = svgHeight - padTop - padBottom;

      // Risk score is strictly 0 to 100
      const yMax = 100;

      // Threshold Horizontal Bands (0-30 Low, 30-50 Moderate, 50-70 High, 70-100 Critical)
      const yForScore = (s) => padTop + plotHeight - (Math.max(0, Math.min(100, s)) / yMax) * plotHeight;

      const y0 = yForScore(0);
      const y30 = yForScore(30);
      const y50 = yForScore(50);
      const y70 = yForScore(70);
      const y100 = yForScore(100);

      // Coordinates for every snapshot
      const stepX = n > 1 ? plotWidth / (n - 1) : plotWidth / 2;
      const coords = sortedSnapshots.map((snap, idx) => {
        const score = Number(snap.overall_risk_score ?? 0);
        const x = padLeft + (n > 1 ? idx * stepX : plotWidth / 2);
        const y = yForScore(score);
        const tier = getTierColor(score);
        const dateFormatted = formatShortDate(snap.snapshot_date || snap.calculated_at || snap.snapshot_datetime);
        return {
          x,
          y,
          score,
          tier,
          idx: idx + 1,
          dateFormatted,
          snap
        };
      });

      // SVG polyline points
      const polylinePoints = coords.map(c => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ');

      // Area fill path
      const firstCoord = coords[0];
      const lastCoord = coords[coords.length - 1];
      const areaPath = `M ${firstCoord.x.toFixed(1)},${padTop + plotHeight} ` +
        coords.map(c => `L ${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ') +
        ` L ${lastCoord.x.toFixed(1)},${padTop + plotHeight} Z`;

      // Gradient definition ID unique per chart
      const gradId = `riskTrajGrad_${chartId}_${Date.now()}`;

      // X-Axis tick labels & vertical milestone markers
      const xMarkers = coords.map((c, idx) => {
        return `
          <!-- Vertical subtle guide line -->
          <line x1="${c.x.toFixed(1)}" y1="${padTop}" x2="${c.x.toFixed(1)}" y2="${padTop + plotHeight}"
                stroke="#e2e8f0" stroke-width="1" stroke-dasharray="2,2" class="opacity-60" />
          <!-- Snapshot milestone pill text -->
          <text x="${c.x.toFixed(1)}" y="${svgHeight - 24}" text-anchor="middle"
                class="text-[10px] fill-on-surface font-semibold font-tabular-data">#${c.idx}</text>
          <!-- Date text -->
          <text x="${c.x.toFixed(1)}" y="${svgHeight - 10}" text-anchor="middle"
                class="text-[9px] fill-secondary font-medium">${c.dateFormatted}</text>
        `;
      }).join('');

      // Data Circles
      const circleElements = coords.map((c, idx) => {
        const isLatest = idx === coords.length - 1;
        const snapPayload = encodeURIComponent(JSON.stringify({
          rev: c.idx,
          date: c.dateFormatted,
          score: c.score.toFixed(1),
          level: c.snap.risk_level || c.tier.label,
          status: c.snap.project_status || 'In Progress',
          summary: c.snap.change_summary || 'Audit evaluation checkpoint.',
          phys: c.snap.physical_progress_pct !== undefined ? Number(c.snap.physical_progress_pct).toFixed(1) : null,
          fin: c.snap.financial_progress_pct !== undefined ? Number(c.snap.financial_progress_pct).toFixed(1) : null,
          delay: c.snap.days_delayed !== undefined ? c.snap.days_delayed : null
        }));

        return `
          <g class="trajectory-node-group cursor-pointer group" data-snapshot-payload="${snapPayload}">
            ${isLatest ? `
              <!-- Pulse ring for latest live snapshot -->
              <circle cx="${c.x.toFixed(1)}" cy="${c.y.toFixed(1)}" r="10"
                      fill="${c.tier.fill}" fill-opacity="0.2" class="animate-ping" />
            ` : ''}
            <!-- Outer border ring -->
            <circle cx="${c.x.toFixed(1)}" cy="${c.y.toFixed(1)}" r="6"
                    fill="${c.tier.fill}" stroke="#ffffff" stroke-width="2.5"
                    class="transition-all duration-200 group-hover:r-[8px] group-hover:stroke-primary" />
            <!-- Inner dot -->
            <circle cx="${c.x.toFixed(1)}" cy="${c.y.toFixed(1)}" r="2" fill="#ffffff" />
            <!-- Score label above point -->
            <text x="${c.x.toFixed(1)}" y="${(c.y - 10).toFixed(1)}" text-anchor="middle"
                  class="text-[10px] font-tabular-data font-bold ${c.tier.text} opacity-90 group-hover:opacity-100 group-hover:text-primary">
              ${c.score.toFixed(0)}
            </text>
          </g>
        `;
      }).join('');

      return `
        <div class="w-full bg-surface-container-lowest border border-outline-variant p-space-lg rounded-lg shadow-sm">
          
          <!-- Top KPI Header: Current Score vs Baseline & Evolution Delta -->
          <div class="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-space-md pb-space-md border-b border-outline-variant/70">
            <div class="flex flex-col">
              <div class="flex items-center gap-space-xs">
                <span class="material-symbols-outlined text-primary text-[20px]">show_chart</span>
                <h2 class="font-headline-sm text-headline-sm text-on-surface font-bold">Historical Risk Trajectory</h2>
                <span class="font-label-sm text-label-sm text-secondary bg-surface-container px-2 py-0.5 rounded border border-outline-variant font-mono">
                  ${n} ${n === 1 ? 'Snapshot' : 'Snapshots Plotted'}
                </span>
              </div>
              <p class="font-body-sm text-body-sm text-secondary mt-0.5">
                Continuous point-in-time risk evaluation recorded across verified audit checkpoints.
              </p>
            </div>

            <!-- Trajectory Metrics Strip -->
            <div class="flex flex-wrap items-center gap-space-md bg-surface-container-low border border-outline-variant/60 px-space-base py-space-xs rounded-lg text-xs">
              <div class="flex flex-col">
                <span class="text-secondary text-[11px] font-semibold uppercase tracking-wider">Sanction Baseline</span>
                <span class="font-tabular-data font-bold text-on-surface text-sm">${baselineScore.toFixed(1)} <span class="text-[10px] text-secondary">/ 100</span></span>
              </div>
              <div class="h-6 w-px bg-outline-variant/80"></div>
              <div class="flex flex-col">
                <span class="text-secondary text-[11px] font-semibold uppercase tracking-wider">Current Score</span>
                <span class="font-tabular-data font-bold ${getTierColor(latestScore).text} text-sm">${latestScore.toFixed(1)} <span class="text-[10px] text-secondary">(${getTierColor(latestScore).label})</span></span>
              </div>
              <div class="h-6 w-px bg-outline-variant/80"></div>
              <div class="flex flex-col">
                <span class="text-secondary text-[11px] font-semibold uppercase tracking-wider">Net Evolution</span>
                <div>${deltaBadge}</div>
              </div>
              <div class="h-6 w-px bg-outline-variant/80"></div>
              <div class="flex flex-col">
                <span class="text-secondary text-[11px] font-semibold uppercase tracking-wider">Peak Trajectory</span>
                <span class="font-tabular-data font-semibold text-on-surface">${peakScore.toFixed(1)} <span class="text-secondary font-normal text-[10px]">(${formatShortDate(peakDate)})</span></span>
              </div>
            </div>
          </div>

          <!-- Main SVG Chronological Line Chart -->
          <div class="w-full relative mt-space-md overflow-x-auto">
            <svg id="${chartId}" viewBox="0 0 ${svgWidth} ${svgHeight}" class="w-full h-auto min-w-[600px] overflow-visible select-none" style="max-height: ${height}px;">
              <defs>
                <linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#00236f" stop-opacity="0.22" />
                  <stop offset="60%" stop-color="#00236f" stop-opacity="0.06" />
                  <stop offset="100%" stop-color="#00236f" stop-opacity="0.0" />
                </linearGradient>
              </defs>

              <!-- Threshold Background Bands -->
              <!-- Critical Band (70 - 100) -->
              <rect x="${padLeft}" y="${y100}" width="${plotWidth}" height="${y70 - y100}" fill="#ba1a1a" fill-opacity="0.04" />
              <!-- High Band (50 - 70) -->
              <rect x="${padLeft}" y="${y70}" width="${plotWidth}" height="${y50 - y70}" fill="#dc2626" fill-opacity="0.03" />
              <!-- Moderate Band (30 - 50) -->
              <rect x="${padLeft}" y="${y50}" width="${plotWidth}" height="${y30 - y50}" fill="#d97706" fill-opacity="0.03" />
              <!-- Low Band (0 - 30) -->
              <rect x="${padLeft}" y="${y30}" width="${plotWidth}" height="${y0 - y30}" fill="#006a60" fill-opacity="0.03" />

              <!-- Horizontal Gridlines & Threshold Labels -->
              <!-- Line 70 (Critical) -->
              <line x1="${padLeft}" y1="${y70}" x2="${padLeft + plotWidth}" y2="${y70}" stroke="#ba1a1a" stroke-width="1" stroke-dasharray="3,3" stroke-opacity="0.4" />
              <text x="${padLeft + plotWidth - 4}" y="${y70 - 4}" text-anchor="end" class="text-[8px] fill-[#ba1a1a] font-bold tracking-wider uppercase opacity-70">Critical Threshold (70)</text>

              <!-- Line 50 (High) -->
              <line x1="${padLeft}" y1="${y50}" x2="${padLeft + plotWidth}" y2="${y50}" stroke="#dc2626" stroke-width="1" stroke-dasharray="3,3" stroke-opacity="0.4" />
              <text x="${padLeft + plotWidth - 4}" y="${y50 - 4}" text-anchor="end" class="text-[8px] fill-[#dc2626] font-bold tracking-wider uppercase opacity-70">High Risk (50)</text>

              <!-- Line 30 (Moderate) -->
              <line x1="${padLeft}" y1="${y30}" x2="${padLeft + plotWidth}" y2="${y30}" stroke="#d97706" stroke-width="1" stroke-dasharray="3,3" stroke-opacity="0.4" />
              <text x="${padLeft + plotWidth - 4}" y="${y30 - 4}" text-anchor="end" class="text-[8px] fill-[#d97706] font-bold tracking-wider uppercase opacity-70">Moderate (30)</text>

              <!-- Line 0 (Base) -->
              <line x1="${padLeft}" y1="${y0}" x2="${padLeft + plotWidth}" y2="${y0}" stroke="#94a3b8" stroke-width="1.5" />

              <!-- Y-Axis Numeric Ticks -->
              <text x="${padLeft - 8}" y="${y100 + 4}" text-anchor="end" class="text-[9px] fill-secondary font-tabular-data font-medium">100</text>
              <text x="${padLeft - 8}" y="${y70 + 3}" text-anchor="end" class="text-[9px] fill-[#ba1a1a] font-tabular-data font-semibold">70</text>
              <text x="${padLeft - 8}" y="${y50 + 3}" text-anchor="end" class="text-[9px] fill-[#dc2626] font-tabular-data font-semibold">50</text>
              <text x="${padLeft - 8}" y="${y30 + 3}" text-anchor="end" class="text-[9px] fill-[#d97706] font-tabular-data font-semibold">30</text>
              <text x="${padLeft - 8}" y="${y0 + 3}" text-anchor="end" class="text-[9px] fill-secondary font-tabular-data font-medium">0</text>

              <!-- Y-Axis Title -->
              <text x="${padLeft - 24}" y="${padTop + plotHeight / 2}" text-anchor="middle" transform="rotate(-90 ${padLeft - 24} ${padTop + plotHeight / 2})"
                    class="text-[9px] fill-secondary font-semibold uppercase tracking-widest">Risk Score (0–100)</text>

              <!-- Vertical Snapshot Guides & X Labels -->
              ${xMarkers}

              <!-- Area Gradient Fill -->
              <path d="${areaPath}" fill="url(#${gradId})" />

              <!-- Polyline Curve Connecting All Points -->
              <polyline fill="none" stroke="#00236f" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" points="${polylinePoints}" />

              <!-- Data Point Nodes -->
              ${circleElements}
            </svg>
          </div>

          <!-- Bottom Visual Legend & User Interaction Hint -->
          <div class="flex flex-wrap items-center justify-between gap-space-sm pt-space-sm mt-space-sm border-t border-outline-variant/50 text-xs text-secondary">
            <div class="flex items-center gap-space-md">
              <span class="font-semibold text-on-surface text-[11px] uppercase tracking-wider">Severity Tiers:</span>
              <div class="flex items-center gap-1.5">
                <span class="w-2.5 h-2.5 rounded-full bg-[#006a60]"></span>
                <span>Low (0–29)</span>
              </div>
              <div class="flex items-center gap-1.5">
                <span class="w-2.5 h-2.5 rounded-full bg-[#d97706]"></span>
                <span>Moderate (30–49)</span>
              </div>
              <div class="flex items-center gap-1.5">
                <span class="w-2.5 h-2.5 rounded-full bg-[#dc2626]"></span>
                <span>High (50–69)</span>
              </div>
              <div class="flex items-center gap-1.5">
                <span class="w-2.5 h-2.5 rounded-full bg-[#ba1a1a]"></span>
                <span>Critical (70–100)</span>
              </div>
            </div>
            <div class="flex items-center gap-1 text-[11px] text-outline">
              <span class="material-symbols-outlined text-[14px]">touch_app</span>
              <span>Hover milestone nodes to inspect audit details</span>
            </div>
          </div>

        </div>
      `;
    },

    /**
     * Renders an expandable secondary view showing the historical evolution
     * of all 6 independent modular risk detectors:
     * 1. Cost Anomaly (#ea580c)
     * 2. Delay Detection (#dc2626)
     * 3. Progress Mismatch (#7c3aed)
     * 4. Fund Utilization (#0891b2)
     * 5. Duplicate Detection (#2563eb)
     * 6. Agency Pattern (#059669)
     */
    renderDetectorEvolutionBreakdown({
      snapshots = [],
      height = 230,
      chartId = 'detector-evolution-svg',
    }) {
      if (!snapshots || snapshots.length === 0) return '';

      // Sorted chronologically ascending
      const sortedSnapshots = [...snapshots].sort((a, b) => {
        const tA = new Date(a.snapshot_datetime || a.calculated_at || a.snapshot_date || 0).getTime();
        const tB = new Date(b.snapshot_datetime || b.calculated_at || b.snapshot_date || 0).getTime();
        return tA - tB;
      });

      const n = sortedSnapshots.length;

      function formatShortDate(dStr) {
        if (!dStr) return 'N/A';
        try {
          const d = new Date(dStr);
          if (isNaN(d.getTime())) return dStr;
          return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' });
        } catch {
          return dStr;
        }
      }

      // Helper to safely extract detector score from snapshot
      function extractDetectorScore(snap, key) {
        if (snap.detector_scores && snap.detector_scores[key]) {
          const ds = snap.detector_scores[key];
          if (typeof ds === 'object' && ds !== null) {
            if (ds.score !== undefined) return Number(ds.score);
            if (ds.delay_risk_score !== undefined) return Number(ds.delay_risk_score);
            if (ds.anomaly_score !== undefined) return Number(ds.anomaly_score);
            if (ds.mismatch_score !== undefined) return Number(ds.mismatch_score);
            if (ds.cluster_risk_score !== undefined) return Number(ds.cluster_risk_score);
          } else if (typeof ds === 'number') {
            return Number(ds);
          }
        }
        // Column fallback
        if (key === 'delay_detection' && snap.delay_risk_score !== undefined) return Number(snap.delay_risk_score);
        if (key === 'cost_anomaly' && snap.cost_overrun_risk_score !== undefined) return Number(snap.cost_overrun_risk_score);
        if (key === 'progress_mismatch' && snap.non_completion_risk_score !== undefined) return Number(snap.non_completion_risk_score);
        if (key === 'fund_utilization' && snap.leakage_risk_score !== undefined) return Number(snap.leakage_risk_score);
        return 0;
      }

      // Configuration of the 6 modular detectors
      const detectors = [
        { key: 'cost_anomaly', label: 'Cost Anomaly', color: '#ea580c', icon: 'payments' },
        { key: 'delay_detection', label: 'Delay Slippage', color: '#dc2626', icon: 'timer_off' },
        { key: 'progress_mismatch', label: 'Progress Mismatch', color: '#7c3aed', icon: 'query_stats' },
        { key: 'fund_utilization', label: 'Fund Utilization', color: '#0891b2', icon: 'account_balance_wallet' },
        { key: 'duplicate_detection', label: 'Duplicate Detection', color: '#2563eb', icon: 'content_copy' },
        { key: 'agency_pattern', label: 'Agency Risk Pattern', color: '#059669', icon: 'corporate_fare' },
      ];

      // SVG Dimensions
      const svgWidth = 720;
      const svgHeight = 240;
      const padLeft = 46;
      const padRight = 32;
      const padTop = 20;
      const padBottom = 45;
      const plotWidth = svgWidth - padLeft - padRight;
      const plotHeight = svgHeight - padTop - padBottom;
      const yMax = 100;
      const yForScore = (s) => padTop + plotHeight - (Math.max(0, Math.min(100, s)) / yMax) * plotHeight;
      const stepX = n > 1 ? plotWidth / (n - 1) : plotWidth / 2;

      // Build coordinates for each detector series
      const seriesData = detectors.map(det => {
        const points = sortedSnapshots.map((snap, idx) => {
          const score = extractDetectorScore(snap, det.key);
          const x = padLeft + (n > 1 ? idx * stepX : plotWidth / 2);
          const y = yForScore(score);
          return { x, y, score, snap, idx: idx + 1 };
        });

        const polylinePoints = points.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

        return {
          ...det,
          points,
          polylinePoints
        };
      });

      // Grid lines (0, 25, 50, 75, 100)
      const gridTicks = [0, 25, 50, 75, 100];
      const gridSvg = gridTicks.map(t => {
        const y = yForScore(t);
        return `
          <line x1="${padLeft}" y1="${y}" x2="${padLeft + plotWidth}" y2="${y}"
                stroke="#e2e8f0" stroke-width="1" stroke-dasharray="3,3" />
          <text x="${padLeft - 8}" y="${y + 3}" text-anchor="end" class="text-[9px] fill-secondary font-tabular-data">${t}</text>
        `;
      }).join('');

      // X-Axis Labels
      const xLabelsSvg = sortedSnapshots.map((snap, idx) => {
        const x = padLeft + (n > 1 ? idx * stepX : plotWidth / 2);
        const dt = formatShortDate(snap.snapshot_date || snap.calculated_at || snap.snapshot_datetime);
        return `
          <text x="${x.toFixed(1)}" y="${svgHeight - 20}" text-anchor="middle" class="text-[10px] fill-on-surface font-bold font-tabular-data">#${idx + 1}</text>
          <text x="${x.toFixed(1)}" y="${svgHeight - 8}" text-anchor="middle" class="text-[9px] fill-secondary font-medium">${dt}</text>
        `;
      }).join('');

      // Polylines & Nodes per detector
      const detectorLinesSvg = seriesData.map(s => {
        const circles = s.points.map(p => {
          return `
            <circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="4.5"
                    fill="${s.color}" stroke="#ffffff" stroke-width="2"
                    class="cursor-pointer transition-transform hover:scale-150"
                    data-detector-key="${s.key}"
                    data-detector-name="${s.label}"
                    data-detector-score="${p.score.toFixed(1)}"
                    data-milestone-rev="${p.idx}" />
          `;
        }).join('');

        return `
          <g id="detector-series-${s.key}" class="detector-series-group">
            <polyline fill="none" stroke="${s.color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" points="${s.polylinePoints}" />
            ${circles}
          </g>
        `;
      }).join('');

      // Tabular audit breakdown rows
      const tableRows = sortedSnapshots.map((snap, idx) => {
        const dt = formatShortDate(snap.snapshot_date || snap.calculated_at || snap.snapshot_datetime);
        const overall = Number(snap.overall_risk_score ?? 0).toFixed(1);
        const cost = extractDetectorScore(snap, 'cost_anomaly').toFixed(1);
        const delay = extractDetectorScore(snap, 'delay_detection').toFixed(1);
        const progress = extractDetectorScore(snap, 'progress_mismatch').toFixed(1);
        const fund = extractDetectorScore(snap, 'fund_utilization').toFixed(1);
        const duplicate = extractDetectorScore(snap, 'duplicate_detection').toFixed(1);
        const agency = extractDetectorScore(snap, 'agency_pattern').toFixed(1);
        const summary = snap.change_summary || 'Inspection audit logged.';

        return `
          <tr class="hover:bg-surface-container-low transition-colors border-b border-outline-variant/40">
            <td class="py-2 px-3 font-mono font-bold text-primary">#${idx + 1}</td>
            <td class="py-2 px-3 whitespace-nowrap text-secondary font-medium">${dt}</td>
            <td class="py-2 px-3 whitespace-nowrap">
              <span class="font-label-sm text-label-sm px-2 py-0.5 rounded border border-outline-variant bg-surface-container font-semibold">
                ${snap.project_status || 'In Progress'}
              </span>
            </td>
            <td class="py-2 px-3 font-tabular-data font-bold text-on-surface">${overall}</td>
            <td class="py-2 px-3 font-tabular-data text-[#ea580c] font-semibold">${cost}</td>
            <td class="py-2 px-3 font-tabular-data text-[#dc2626] font-semibold">${delay}</td>
            <td class="py-2 px-3 font-tabular-data text-[#7c3aed] font-semibold">${progress}</td>
            <td class="py-2 px-3 font-tabular-data text-[#0891b2] font-semibold">${fund}</td>
            <td class="py-2 px-3 font-tabular-data text-[#2563eb] font-semibold">${duplicate}</td>
            <td class="py-2 px-3 font-tabular-data text-[#059669] font-semibold">${agency}</td>
            <td class="py-2 px-3 text-secondary text-xs truncate max-w-[220px]" title="${summary}">${summary}</td>
          </tr>
        `;
      }).join('');

      return `
        <!-- Expandable Details Container -->
        <details class="w-full bg-surface-container-lowest border border-outline-variant rounded-lg shadow-sm group" id="detectorBreakdownDetails">
          <summary class="p-space-base flex items-center justify-between cursor-pointer select-none hover:bg-surface-container-low transition-colors rounded-lg">
            <div class="flex items-center gap-space-sm">
              <span class="material-symbols-outlined text-primary text-[20px]">tune</span>
              <div class="flex flex-col">
                <span class="font-title-sm text-title-sm text-on-surface font-bold">Multi-Detector Historical Breakdown (6 Engines)</span>
                <span class="font-body-sm text-body-sm text-secondary">
                  Compare how Cost Anomaly, Delay, Progress Mismatch, Fund Utilization, Duplicate Detection, and Agency Pattern evolved over time.
                </span>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <span class="font-label-sm text-label-sm text-secondary bg-surface-container px-2 py-0.5 rounded border border-outline-variant">
                6 Modular Engines
              </span>
              <span class="material-symbols-outlined text-outline text-[20px] transition-transform group-open:rotate-180">expand_more</span>
            </div>
          </summary>

          <div class="p-space-lg pt-0 border-t border-outline-variant/60 mt-space-xs space-y-space-lg">
            
            <!-- Interactive Legend with Detector Visibility Toggles -->
            <div class="flex flex-wrap items-center gap-x-4 gap-y-2 pt-space-sm">
              <span class="font-label-sm text-label-sm text-secondary uppercase font-semibold">Active Engines:</span>
              ${detectors.map(d => `
                <button type="button" class="detector-toggle-btn inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border transition-all"
                        style="color: ${d.color}; border-color: ${d.color}40; background-color: ${d.color}10;"
                        data-detector-key="${d.key}">
                  <span class="w-2 h-2 rounded-full" style="background-color: ${d.color};"></span>
                  <span>${d.label}</span>
                </button>
              `).join('')}
            </div>

            <!-- Multi-Series Secondary Chart -->
            <div class="w-full relative overflow-x-auto bg-surface-container-low/40 p-2 rounded-lg border border-outline-variant/40">
              <svg id="${chartId}" viewBox="0 0 ${svgWidth} ${svgHeight}" class="w-full h-auto min-w-[600px] overflow-visible select-none" style="max-height: ${height}px;">
                <!-- Grid Lines -->
                ${gridSvg}

                <!-- Base Line -->
                <line x1="${padLeft}" y1="${yForScore(0)}" x2="${padLeft + plotWidth}" y2="${yForScore(0)}" stroke="#94a3b8" stroke-width="1.5" />

                <!-- X Axis Labels -->
                ${xLabelsSvg}

                <!-- Y Axis Title -->
                <text x="${padLeft - 24}" y="${padTop + plotHeight / 2}" text-anchor="middle" transform="rotate(-90 ${padLeft - 24} ${padTop + plotHeight / 2})"
                      class="text-[9px] fill-secondary font-semibold uppercase tracking-widest">Engine Score (0–100)</text>

                <!-- Detector Polylines & Nodes -->
                ${detectorLinesSvg}
              </svg>
            </div>

            <!-- Point-in-Time Audit Ledger Table -->
            <div class="overflow-x-auto">
              <h4 class="font-title-sm text-title-sm text-on-surface font-semibold mb-space-xs">
                Historical Milestone Audit Ledger
              </h4>
              <table class="w-full text-left text-xs border border-outline-variant rounded-DEFAULT overflow-hidden">
                <thead class="bg-surface-container-low border-b border-outline-variant text-secondary font-semibold uppercase tracking-wider text-[10px]">
                  <tr>
                    <th class="py-2 px-3">Snap</th>
                    <th class="py-2 px-3">Date</th>
                    <th class="py-2 px-3">Status</th>
                    <th class="py-2 px-3">Overall</th>
                    <th class="py-2 px-3 text-[#ea580c]">Cost</th>
                    <th class="py-2 px-3 text-[#dc2626]">Delay</th>
                    <th class="py-2 px-3 text-[#7c3aed]">Prog Lag</th>
                    <th class="py-2 px-3 text-[#0891b2]">Fund Util</th>
                    <th class="py-2 px-3 text-[#2563eb]">Duplicate</th>
                    <th class="py-2 px-3 text-[#059669]">Agency</th>
                    <th class="py-2 px-3">Milestone Change Audit</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-outline-variant/30 bg-surface-container-lowest">
                  ${tableRows}
                </tbody>
              </table>
            </div>

          </div>
        </details>
      `;
    }
  };

  window.ChartUtils = ChartUtils;
})();
