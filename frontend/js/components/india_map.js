/**
 * frontend/js/components/india_map.js
 * =============================================================================
 * Interactive SVG India Choropleth Map Component.
 * Supports:
 * - Dynamic choropleth color intensity based on density score (0-100)
 * - Metric toggling: Project Volume, Avg Risk Score, Delay Days, Sanctioned Outlay
 * - Hover card with rich state-level KPIs and risk severity breakdown
 * - Click-to-filter drilldown: clicking a state sets the global state filter
 * - High-accessibility Tabular Matrix fallback mode
 * =============================================================================
 */

(function () {
  'use strict';

  // Simplified geographic paths for India States & UTs (optimized for fast vector rendering)
  // Normalized viewbox 0 0 600 660
  const INDIA_STATE_PATHS = {
    "IN-JK": { name: "Jammu and Kashmir", d: "M 200,60 L 250,55 L 280,85 L 260,115 L 220,125 L 185,100 Z" },
    "IN-LA": { name: "Ladakh", d: "M 250,55 L 320,50 L 340,90 L 300,120 L 260,115 L 280,85 Z" },
    "IN-HP": { name: "Himachal Pradesh", d: "M 220,125 L 260,115 L 280,140 L 255,160 L 225,145 Z" },
    "IN-PB": { name: "Punjab", d: "M 185,125 L 225,125 L 220,165 L 180,160 Z" },
    "IN-UT": { name: "Uttarakhand", d: "M 260,140 L 300,150 L 310,185 L 270,180 L 255,160 Z" },
    "IN-HR": { name: "Haryana", d: "M 200,165 L 240,165 L 245,195 L 205,200 L 195,175 Z" },
    "IN-DL": { name: "Delhi", d: "M 233,185 L 243,185 L 243,195 L 233,195 Z" },
    "IN-RJ": { name: "Rajasthan", d: "M 120,180 L 200,175 L 220,230 L 180,285 L 125,270 L 105,215 Z" },
    "IN-UP": { name: "Uttar Pradesh", d: "M 240,180 L 320,185 L 375,230 L 345,270 L 260,260 L 230,225 Z" },
    "IN-BR": { name: "Bihar", d: "M 375,230 L 440,235 L 435,275 L 370,270 Z" },
    "IN-SK": { name: "Sikkim", d: "M 445,200 L 460,198 L 462,215 L 447,215 Z" },
    "IN-WB": { name: "West Bengal", d: "M 435,240 L 450,230 L 455,290 L 425,325 L 415,290 L 435,275 Z" },
    "IN-JH": { name: "Jharkhand", d: "M 370,270 L 430,275 L 415,325 L 360,315 Z" },
    "IN-OD": { name: "Odisha", d: "M 360,320 L 425,325 L 400,395 L 350,375 Z" },
    "IN-CT": { name: "Chhattisgarh", d: "M 315,285 L 365,295 L 350,380 L 310,385 L 305,320 Z" },
    "IN-MP": { name: "Madhya Pradesh", d: "M 200,235 L 315,235 L 330,300 L 260,320 L 195,285 Z" },
    "IN-GJ": { name: "Gujarat", d: "M 80,260 L 140,260 L 165,315 L 120,335 L 75,310 Z" },
    "IN-MH": { name: "Maharashtra", d: "M 155,320 L 275,320 L 285,395 L 205,425 L 150,375 Z" },
    "IN-TG": { name: "Telangana", d: "M 245,395 L 305,385 L 300,450 L 240,440 Z" },
    "IN-AP": { name: "Andhra Pradesh", d: "M 265,435 L 330,400 L 310,505 L 255,490 Z" },
    "IN-KA": { name: "Karnataka", d: "M 185,420 L 245,420 L 255,510 L 200,520 L 175,465 Z" },
    "IN-GA": { name: "Goa", d: "M 175,445 L 185,445 L 182,458 L 173,455 Z" },
    "IN-KL": { name: "Kerala", d: "M 195,520 L 225,525 L 215,595 L 190,560 Z" },
    "IN-TN": { name: "Tamil Nadu", d: "M 225,505 L 275,505 L 255,600 L 215,595 Z" },
    "IN-AS": { name: "Assam", d: "M 465,225 L 530,220 L 525,255 L 465,255 Z" },
    "IN-AR": { name: "Arunachal Pradesh", d: "M 490,180 L 560,195 L 545,225 L 485,215 Z" },
    "IN-NL": { name: "Nagaland", d: "M 535,225 L 555,235 L 545,260 L 530,250 Z" },
    "IN-MN": { name: "Manipur", d: "M 530,255 L 550,260 L 545,285 L 525,280 Z" },
    "IN-MZ": { name: "Mizoram", d: "M 515,285 L 535,285 L 530,320 L 512,315 Z" },
    "IN-TR": { name: "Tripura", d: "M 495,275 L 512,275 L 508,300 L 493,295 Z" },
    "IN-ML": { name: "Meghalaya", d: "M 470,250 L 515,250 L 510,265 L 468,265 Z" }
  };

  class IndiaMapComponent {
    constructor({ container, mapData = null, selectedState = '', onStateClick = null }) {
      this.container = container;
      this.mapData = mapData || { states: [], max_value: 1, active_metric: 'projects' };
      this.selectedState = selectedState || '';
      this.onStateClick = onStateClick;
      this.activeMetric = 'projects';
      this.viewMode = 'map'; // 'map' or 'table'
      this.stateDataMap = new Map();
      this.buildStateDataMap();
    }

    buildStateDataMap() {
      this.stateDataMap.clear();
      if (this.mapData && Array.isArray(this.mapData.states)) {
        this.mapData.states.forEach(s => {
          if (s.state_code) {
            this.stateDataMap.set(s.state_code.toUpperCase(), s);
          }
          if (s.state_name) {
            this.stateDataMap.set(s.state_name.toLowerCase(), s);
          }
        });
      }
    }

    updateData(newMapData, selectedState = undefined) {
      this.mapData = newMapData;
      if (selectedState !== undefined) {
        this.selectedState = selectedState || '';
      }
      this.buildStateDataMap();
      this.render();
    }

    setSelectedState(selectedState) {
      this.selectedState = selectedState || '';
      this.render();
    }

    setMetric(metric) {
      this.activeMetric = metric;
      this.render();
    }

    getColorForState(stateCode, stateName) {
      const state = this.stateDataMap.get(stateCode) || this.stateDataMap.get((stateName || '').toLowerCase());
      if (!state || state.total_projects === 0) {
        return '#f1f5f9'; // Slate-100: No assessed projects
      }

      // Compute intensity based on metric
      let score = state.density_score || 0;
      if (this.activeMetric === 'risk_score') {
        score = (state.average_risk_score / 100) * 100;
        if (score >= 60) return '#ba1a1a'; // Critical crimson
        if (score >= 40) return '#ea580c'; // High orange
        if (score >= 25) return '#eab308'; // Moderate yellow
        return '#16a34a'; // Low green
      } else if (this.activeMetric === 'delays') {
        const delay = state.average_delay_days || 0;
        if (delay > 90) return '#ba1a1a';
        if (delay > 30) return '#ea580c';
        if (delay > 0) return '#eab308';
        return '#16a34a';
      }

      // Default: Project volume density gradient using primary navy (#00236f)
      const alpha = Math.max(0.15, Math.min(1.0, score / 100));
      return `rgba(0, 35, 111, ${alpha.toFixed(2)})`;
    }

    render() {
      if (!this.container) return;

      const totalMapped = this.mapData.states ? this.mapData.states.reduce((acc, s) => acc + (s.total_projects || 0), 0) : 0;
      const assessedStatesCount = this.mapData.states ? this.mapData.states.filter(s => s.total_projects > 0).length : 0;

      this.container.innerHTML = `
        <div class="bg-surface-container-lowest border border-outline-variant rounded-lg p-space-base shadow-sm flex flex-col gap-space-md">
          
          <!-- Header & Controls -->
          <div class="flex flex-col sm:flex-row sm:items-center justify-between pb-space-xs border-b border-outline-variant gap-space-xs">
            <div>
              <div class="flex items-center gap-2">
                <span class="material-symbols-outlined text-primary text-[20px]">public</span>
                <h3 class="font-title-sm text-title-sm text-on-surface font-bold">Geographic Surveillance • India Risk Map</h3>
              </div>
              <p class="font-body-sm text-body-sm text-secondary mt-0.5">
                ${assessedStatesCount} States active • ${totalMapped} works plotted with server-side aggregation
              </p>
            </div>

            <!-- Controls: Metric Toggle & View Mode -->
            <div class="flex items-center gap-2 flex-wrap">
              <!-- Metric Selector -->
              <div class="inline-flex rounded-lg border border-outline-variant p-0.5 bg-surface-container text-xs">
                <button class="px-2 py-1 rounded font-medium transition-colors ${this.activeMetric === 'projects' ? 'bg-primary text-on-primary shadow-xs' : 'text-secondary hover:text-on-surface'}"
                        data-map-metric="projects">
                  Projects
                </button>
                <button class="px-2 py-1 rounded font-medium transition-colors ${this.activeMetric === 'risk_score' ? 'bg-primary text-on-primary shadow-xs' : 'text-secondary hover:text-on-surface'}"
                        data-map-metric="risk_score">
                  Risk Score
                </button>
                <button class="px-2 py-1 rounded font-medium transition-colors ${this.activeMetric === 'delays' ? 'bg-primary text-on-primary shadow-xs' : 'text-secondary hover:text-on-surface'}"
                        data-map-metric="delays">
                  Delays
                </button>
              </div>

              <!-- View Switcher -->
              <div class="inline-flex rounded-lg border border-outline-variant p-0.5 bg-surface-container text-xs">
                <button class="px-2 py-1 rounded font-medium transition-colors ${this.viewMode === 'map' ? 'bg-surface-container-lowest text-on-surface shadow-xs' : 'text-secondary hover:text-on-surface'}"
                        data-map-view="map" title="Interactive Map">
                  <span class="material-symbols-outlined text-[16px] leading-none">map</span>
                </button>
                <button class="px-2 py-1 rounded font-medium transition-colors ${this.viewMode === 'table' ? 'bg-surface-container-lowest text-on-surface shadow-xs' : 'text-secondary hover:text-on-surface'}"
                        data-map-view="table" title="Data Table">
                  <span class="material-symbols-outlined text-[16px] leading-none">table_chart</span>
                </button>
              </div>
            </div>
          </div>

          <!-- Main View Container -->
          ${this.viewMode === 'map' ? this.renderMapSvg() : this.renderTableView()}

          <!-- Bottom Legend & Interaction Hint -->
          <div class="flex flex-col sm:flex-row items-center justify-between pt-space-xs border-t border-outline-variant text-xs text-secondary gap-2">
            <div class="flex items-center gap-2">
              <span class="font-medium text-on-surface">Intensity:</span>
              <div class="flex items-center gap-1">
                <span class="w-3 h-3 rounded bg-slate-100 border border-slate-300" title="0 Projects"></span>
                <span class="text-[10px]">None</span>
              </div>
              <div class="w-20 h-2 rounded-full bg-gradient-to-r from-[#00236f]/20 via-[#00236f]/60 to-[#00236f]"></div>
              <span class="text-[10px]">High Concentration</span>
            </div>
            <span class="text-primary font-medium flex items-center gap-1">
              <span class="material-symbols-outlined text-[16px]">touch_app</span>
              Click state polygon to filter district triage
            </span>
          </div>

        </div>
      `;

      this.attachEventListeners();
    }

    renderMapSvg() {
      const pathsHtml = Object.entries(INDIA_STATE_PATHS).map(([code, def]) => {
        const fillColor = this.getColorForState(code, def.name);
        const stateInfo = this.stateDataMap.get(code) || this.stateDataMap.get(def.name.toLowerCase());
        const hasData = stateInfo && stateInfo.total_projects > 0;
        const isSelected = Boolean(this.selectedState && def.name.toLowerCase() === this.selectedState.toLowerCase());

        const strokeColor = isSelected ? '#ba1a1a' : '#ffffff';
        const strokeWidth = isSelected ? '3.5' : '1.5';
        const extraClass = isSelected
          ? 'drop-shadow-[0_0_6px_rgba(186,26,26,0.8)] z-10'
          : (hasData ? 'hover:stroke-primary hover:stroke-2' : 'opacity-60');

        return `
          <path
            id="map-path-${code}"
            d="${def.d}"
            fill="${fillColor}"
            stroke="${strokeColor}"
            stroke-width="${strokeWidth}"
            class="transition-all duration-200 cursor-pointer ${extraClass}"
            data-state-code="${code}"
            data-state-name="${def.name}"
          />
        `;
      }).join('');

      return `
        <div class="relative w-full flex items-center justify-center min-h-[380px] py-2">
          <svg viewBox="50 30 520 590" class="w-full max-w-[500px] h-auto max-h-[460px] drop-shadow-sm">
            ${pathsHtml}
          </svg>
        </div>
      `;
    }

    renderTableView() {
      const states = this.mapData.states || [];
      if (states.length === 0) {
        return `<div class="py-12 text-center text-secondary text-sm">No state geographic data matching current filters.</div>`;
      }

      return `
        <div class="overflow-x-auto max-h-[380px]">
          <table class="w-full text-left font-body-sm text-xs border-collapse">
            <thead>
              <tr class="border-b border-outline-variant bg-surface-container-low text-secondary font-semibold uppercase">
                <th class="py-2 px-3">State / UT</th>
                <th class="py-2 px-3 text-right">Works</th>
                <th class="py-2 px-3 text-right">High Risk</th>
                <th class="py-2 px-3 text-right">Avg Risk</th>
                <th class="py-2 px-3 text-right">Avg Delay</th>
                <th class="py-2 px-3 text-right">Sanctioned</th>
                <th class="py-2 px-3 text-center">Action</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-outline-variant/50">
              ${states.map(s => {
                const isSelected = Boolean(this.selectedState && s.state_name.toLowerCase() === this.selectedState.toLowerCase());
                return `
                <tr class="transition-colors cursor-pointer ${isSelected ? 'bg-primary/10 font-bold border-l-4 border-l-primary' : 'hover:bg-surface-container-low'}" data-state-row="${s.state_name}">
                  <td class="py-2 px-3 font-semibold text-on-surface flex items-center gap-1.5">
                    <span class="w-2 h-2 rounded-full ${s.critical_risk_projects > 0 ? 'bg-error' : (s.high_risk_projects > 0 ? 'bg-warning' : 'bg-primary')}"></span>
                    ${s.state_name}
                    ${isSelected ? '<span class="text-[10px] bg-primary text-on-primary px-1.5 py-0.5 rounded font-bold uppercase ml-1">Active</span>' : ''}
                  </td>
                  <td class="py-2 px-3 text-right font-tabular-data font-bold">${s.total_projects}</td>
                  <td class="py-2 px-3 text-right font-tabular-data ${s.high_risk_projects > 0 ? 'text-error font-bold' : 'text-secondary'}">${s.high_risk_projects}</td>
                  <td class="py-2 px-3 text-right font-tabular-data font-semibold">${Number(s.average_risk_score).toFixed(1)}</td>
                  <td class="py-2 px-3 text-right font-tabular-data">${Number(s.average_delay_days).toFixed(0)}d</td>
                  <td class="py-2 px-3 text-right font-tabular-data text-primary font-semibold">₹${Number(s.sanctioned_amount_cr || 0).toFixed(2)} Cr</td>
                  <td class="py-2 px-3 text-center">
                    <button class="px-2 py-0.5 text-[11px] font-semibold text-primary hover:bg-primary hover:text-on-primary rounded transition-colors"
                            data-filter-state="${s.state_name}">
                      ${isSelected ? 'Selected' : 'Filter'}
                    </button>
                  </td>
                </tr>
              `;
              }).join('')}
            </tbody>
          </table>
        </div>
      `;
    }

    attachEventListeners() {
      // Metric switcher buttons
      this.container.querySelectorAll('[data-map-metric]').forEach(btn => {
        btn.addEventListener('click', (e) => {
          this.activeMetric = e.currentTarget.getAttribute('data-map-metric');
          this.render();
        });
      });

      // View mode switcher buttons
      this.container.querySelectorAll('[data-map-view]').forEach(btn => {
        btn.addEventListener('click', (e) => {
          this.viewMode = e.currentTarget.getAttribute('data-map-view');
          this.render();
        });
      });

      // SVG path hover and click
      this.container.querySelectorAll('path[data-state-code]').forEach(path => {
        const code = path.getAttribute('data-state-code');
        const name = path.getAttribute('data-state-name');
        const stateInfo = this.stateDataMap.get(code) || this.stateDataMap.get(name.toLowerCase());

        path.addEventListener('mouseenter', (e) => {
          if (!window.ChartUtils) return;
          const projects = stateInfo ? stateInfo.total_projects : 0;
          const highRisk = stateInfo ? stateInfo.high_risk_projects : 0;
          const critical = stateInfo ? stateInfo.critical_risk_projects : 0;
          const avgRisk = stateInfo ? Number(stateInfo.average_risk_score).toFixed(1) : '0.0';
          const avgDelay = stateInfo ? Number(stateInfo.average_delay_days).toFixed(0) : '0';
          const sanctioned = stateInfo ? Number(stateInfo.sanctioned_amount_cr || 0).toFixed(2) : '0.00';

          const html = `
            <div class="flex flex-col gap-1">
              <div class="flex items-center justify-between font-bold border-b border-outline-variant pb-1">
                <span>${name}</span>
                <span class="text-secondary text-[10px]">${code}</span>
              </div>
              <div class="grid grid-cols-2 gap-x-2 gap-y-1 text-[11px] pt-1">
                <span class="text-secondary">Assessed Works:</span>
                <span class="font-tabular-data font-bold text-right">${projects}</span>
                <span class="text-secondary">High / Critical:</span>
                <span class="font-tabular-data font-bold text-right ${critical + highRisk > 0 ? 'text-error' : ''}">${critical + highRisk}</span>
                <span class="text-secondary">Avg Risk Score:</span>
                <span class="font-tabular-data font-bold text-right">${avgRisk}</span>
                <span class="text-secondary">Avg Overdue:</span>
                <span class="font-tabular-data font-bold text-right">${avgDelay} days</span>
                <span class="text-secondary">Sanctioned:</span>
                <span class="font-tabular-data font-bold text-primary text-right">₹${sanctioned} Cr</span>
              </div>
            </div>
          `;
          window.ChartUtils.showTooltip(e, html);
        });

        path.addEventListener('mousemove', (e) => {
          if (window.ChartUtils) {
            const tip = document.getElementById('mplads-chart-tooltip');
            if (tip) {
              tip.style.left = `${Math.min(e.clientX + 14, window.innerWidth - 280)}px`;
              tip.style.top = `${Math.min(e.clientY + 14, window.innerHeight - 80)}px`;
            }
          }
        });

        path.addEventListener('mouseleave', () => {
          if (window.ChartUtils) window.ChartUtils.hideTooltip();
        });

        path.addEventListener('click', () => {
          if (this.onStateClick && name) {
            this.onStateClick(name, code);
          }
        });
      });

      // Table row click
      this.container.querySelectorAll('[data-filter-state]').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const state = e.currentTarget.getAttribute('data-filter-state');
          if (this.onStateClick && state) {
            this.onStateClick(state, null);
          }
        });
      });
    }
  }

  window.IndiaMapComponent = IndiaMapComponent;
})();
