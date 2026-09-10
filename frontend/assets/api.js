/**
 * MPLADS Sentinel - Civic Oversight Platform
 * Centralized API Client & Multi-Role Governance Engine
 */

const API_BASE = window.location.origin;

const SentinelAPI = {
  // 1. Health & Database Connectivity
  async getHealth() {
    try {
      const res = await fetch(`${API_BASE}/health`);
      return await res.json();
    } catch (e) {
      return { status: "offline", backend: "unreachable", database: "disconnected" };
    }
  },

  // 2. Portfolio KPIs
  async getKPIs() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/analytics/kpis`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn("Falling back to cached KPIs:", e);
    }
    return {
      total_sanctioned_cr: 3950.40,
      total_released_cr: 3780.20,
      total_expenditure_cr: 3120.85,
      overall_utilization_rate_pct: 82.55,
      active_delayed_count: 342,
      critical_risk_count: 78
    };
  },

  // 3. Projects List with Filtering and Search
  async getProjects(params = {}) {
    try {
      const query = new URLSearchParams();
      if (params.page) query.append("page", params.page);
      if (params.limit) query.append("limit", params.limit || 20);
      if (params.q) query.append("q", params.q);
      if (params.status) query.append("current_status", params.status);
      if (params.sector) query.append("sector", params.sector);
      if (params.risk_level) query.append("risk_level", params.risk_level);
      if (params.state_id) query.append("state_id", params.state_id);

      const res = await fetch(`${API_BASE}/api/v1/projects?${query.toString()}`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn("Failed fetching live projects:", e);
    }
    return null;
  },

  // 4. Project Detail by ID
  async getProjectDetail(id) {
    try {
      const res = await fetch(`${API_BASE}/api/v1/projects/${id}`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn(`Failed fetching project ${id}:`, e);
    }
    return null;
  },

  // 5. High-Risk Projects Queue
  async getHighRiskProjects(limit = 20) {
    try {
      const res = await fetch(`${API_BASE}/api/v1/high-risk?limit=${limit}`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn("Failed fetching high risk projects:", e);
    }
    return [];
  },

  // 6. Sector Breakdown
  async getSectorAnalytics() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/analytics/sectors`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn("Failed fetching sector analytics:", e);
    }
    return [];
  },

  // 7. Risk Distribution
  async getRiskDistribution() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/analytics/risk-distribution`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn("Failed fetching risk distribution:", e);
    }
    return {
      tier_counts: { LOW: 1420, MEDIUM: 680, HIGH: 215, CRITICAL: 42 },
      portfolio_average_score: 28.4
    };
  },

  // 8. State-Level Performance & Ranking
  async getStateAnalytics() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/analytics/states?limit=36`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn("Failed fetching states analytics:", e);
    }
    return [];
  },

  // 9. Semantic & Full-text Search
  async searchProjects(queryStr) {
    try {
      const res = await fetch(`${API_BASE}/api/v1/projects/search?q=${encodeURIComponent(queryStr)}`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn("Failed searching projects:", e);
    }
    return null;
  },

  // 10. Recalculate Risk Trigger
  async recalculateRisk(projectId) {
    try {
      const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/recalculate-risk`, {
        method: "POST"
      });
      if (res.ok) return await res.json();
    } catch (e) {
      console.error(`Error recalculating risk for ${projectId}:`, e);
    }
    return null;
  },

  // =========================================================================
  // ROLE 1: NODAL HEAD ACTIONS
  // =========================================================================

  async getNodalPendingSanctions() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/roles/nodal/pending-sanctions`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn("Failed fetching pending sanctions:", e);
    }
    return [];
  },

  async nodalSanctionProject(projectId, data) {
    try {
      const res = await fetch(`${API_BASE}/api/v1/roles/nodal/sanction/${projectId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
      });
      return await res.json();
    } catch (e) {
      console.error("Nodal sanction error:", e);
      return { status: "error", message: e.message };
    }
  },

  async nodalReleaseFunds(projectId, data) {
    try {
      const res = await fetch(`${API_BASE}/api/v1/roles/nodal/release-funds/${projectId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
      });
      return await res.json();
    } catch (e) {
      console.error("Nodal fund release error:", e);
      return { status: "error", message: e.message };
    }
  },

  // =========================================================================
  // ROLE 2: SITE EXECUTER ACTIONS
  // =========================================================================

  async getExecuterAssignedProjects(agency = "") {
    try {
      const res = await fetch(`${API_BASE}/api/v1/roles/executer/assigned-projects?agency=${encodeURIComponent(agency)}`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn("Failed fetching executer works:", e);
    }
    return [];
  },

  async executerUpdateProgress(projectId, data) {
    try {
      const res = await fetch(`${API_BASE}/api/v1/roles/executer/update-progress/${projectId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
      });
      return await res.json();
    } catch (e) {
      console.error("Executer progress update error:", e);
      return { status: "error", message: e.message };
    }
  },

  async executerLogExpenditure(projectId, data) {
    try {
      const res = await fetch(`${API_BASE}/api/v1/roles/executer/log-expenditure/${projectId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
      });
      return await res.json();
    } catch (e) {
      console.error("Executer expenditure log error:", e);
      return { status: "error", message: e.message };
    }
  },

  // =========================================================================
  // ROLE 3: CONSUMER (CITIZEN) ACTIONS
  // =========================================================================

  async consumerTrackProject(query) {
    try {
      const res = await fetch(`${API_BASE}/api/v1/roles/consumer/track/${encodeURIComponent(query)}`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn("Consumer track error:", e);
    }
    return null;
  },

  async consumerReportIssue(projectId, data) {
    try {
      const res = await fetch(`${API_BASE}/api/v1/roles/consumer/report-issue/${projectId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
      });
      return await res.json();
    } catch (e) {
      console.error("Consumer report issue error:", e);
      return { status: "error", message: e.message };
    }
  },

  async getRecentCitizenReports() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/roles/consumer/recent-reports`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn("Recent reports fetch error:", e);
    }
    return [];
  },

  // =========================================================================
  // Formatting & Universal UI Helpers
  // =========================================================================

  formatCurrencyINR(val) {
    if (val === null || val === undefined) return "₹0";
    const num = Number(val);
    if (num >= 10000000) {
      return `₹${(num / 10000000).toFixed(2)} Cr`;
    } else if (num >= 100000) {
      return `₹${(num / 100000).toFixed(2)} L`;
    }
    return `₹${num.toLocaleString("en-IN")}`;
  },

  renderRoleSwitcher(activeRole = "overview") {
    // Check if switcher container exists, if not prepend to body
    let bar = document.getElementById("sentinel-role-switcher");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "sentinel-role-switcher";
      bar.className = "w-full bg-slate-900 text-slate-200 border-b border-slate-700 py-1.5 px-4 text-xs flex flex-wrap items-center justify-between z-50 sticky top-0 shadow-sm";
      document.body.prepend(bar);
    }

    const roles = [
      { id: "consumer", label: "🟢 Consumer (Citizen Portal)", url: "/ui/consumer/" },
      { id: "nodal", label: "🏛️ Nodal Head (Sanction & Admin)", url: "/ui/nodal-head/" },
      { id: "executer", label: "🏗️ Site Executer (Field Progress)", url: "/ui/site-executer/" },
      { id: "overview", label: "📊 Statutory Sentinel (HQ)", url: "/ui/overview/" }
    ];

    const pillsHtml = roles.map(r => {
      const isActive = r.id === activeRole;
      const baseClass = "px-3 py-1 rounded font-medium transition-all inline-flex items-center gap-1.5";
      const activeClass = isActive 
        ? "bg-blue-600 text-white shadow-sm ring-1 ring-blue-400" 
        : "text-slate-300 hover:text-white hover:bg-slate-800";
      return `<a href="${r.url}" class="${baseClass} ${activeClass}">${r.label}</a>`;
    }).join("");

    bar.innerHTML = `
      <div class="flex items-center gap-2">
        <span class="font-bold tracking-tight text-white uppercase text-[10px] bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700">Role Mode</span>
        <span class="text-slate-400 hidden sm:inline">Switch persona to inspect & edit:</span>
      </div>
      <div class="flex items-center gap-1 mt-1 sm:mt-0">
        ${pillsHtml}
      </div>
    `;
  }
};

window.SentinelAPI = SentinelAPI;
