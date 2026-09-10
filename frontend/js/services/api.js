/**
 * frontend/js/services/api.js
 * =============================================================================
 * Centralized API Service Layer for MPLADS Risk Detection & Governance.
 * Handles base URL configuration, query serialization, timeouts, and error handling.
 * =============================================================================
 */

(function () {
  'use strict';

  class ApiError extends Error {
    constructor(message, status = 500, data = null) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
      this.data = data;
    }
  }

  class ApiClient {
    constructor() {
      this.timeoutMs = 15000;
    }

    get baseUrl() {
      return (window.MPLADS_CONFIG?.API_BASE_URL || window.location.origin).replace(/\/+$/, '');
    }

    /**
     * Internal robust request handler with timeout and structured error handling.
     */
    async request(endpoint, options = {}) {
      const url = new URL(endpoint.startsWith('http') ? endpoint : `${this.baseUrl}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`);

      // Append query parameters
      if (options.params) {
        Object.entries(options.params).forEach(([key, val]) => {
          if (val !== undefined && val !== null && val !== '') {
            url.searchParams.append(key, String(val));
          }
        });
      }

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

      const fetchOptions = {
        method: options.method || 'GET',
        headers: {
          'Accept': 'application/json',
          ...(options.body ? { 'Content-Type': 'application/json' } : {}),
          ...options.headers,
        },
        signal: controller.signal,
      };

      if (options.body) {
        fetchOptions.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
      }

      try {
        const response = await fetch(url.toString(), fetchOptions);
        clearTimeout(timeoutId);

        let data = null;
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
          data = await response.json();
        } else {
          data = await response.text();
        }

        if (!response.ok) {
          const errMsg = data?.detail || `API request failed with HTTP ${response.status} (${response.statusText})`;
          throw new ApiError(errMsg, response.status, data);
        }

        return data;
      } catch (err) {
        clearTimeout(timeoutId);
        if (err.name === 'AbortError') {
          throw new ApiError('Request timed out after 15 seconds. Please verify backend connection.', 408);
        }
        if (err instanceof ApiError) {
          throw err;
        }
        throw new ApiError(err.message || 'Unable to connect to MPLADS backend service.', 0, err);
      }
    }

    // =========================================================================
    // Project Registry & Details
    // =========================================================================

    /**
     * Lists developmental projects with multi-criteria filtering, search, and pagination.
     * GET /projects
     */
    async getProjects(params = {}) {
      return this.request('/projects', { params });
    }

    /**
     * Retrieves 360-degree project details by ID.
     * GET /projects/{id}
     */
    async getProject(id) {
      if (!id) throw new ApiError('Project ID is required', 400);
      return this.request(`/projects/${encodeURIComponent(id)}`);
    }

    /**
     * Phase 8 Structured Explainability: Why was this project flagged?
     * GET /projects/{id}/explanation
     */
    async getProjectExplanation(id, recalculate = false, onlyTriggered = false) {
      if (!id) throw new ApiError('Project ID is required', 400);
      return this.request(`/projects/${encodeURIComponent(id)}/explanation`, {
        params: { recalculate, only_triggered: onlyTriggered }
      });
    }

    /**
     * Mathematical Risk Score Decomposition: Itemized contributions and reconciliation.
     * GET /projects/{id}/decomposition
     */
    async getProjectDecomposition(id, recalculate = false) {
      if (!id) throw new ApiError('Project ID is required', 400);
      return this.request(`/projects/${encodeURIComponent(id)}/decomposition`, {
        params: { recalculate }
      });
    }

    /**
     * Project event and audit timeline ledger.
     * GET /projects/{id}/timeline
     */
    async getProjectTimeline(id) {
      if (!id) throw new ApiError('Project ID is required', 400);
      return this.request(`/projects/${encodeURIComponent(id)}/timeline`);
    }

    /**
     * Physical milestone and inspection progress history.
     * GET /projects/{id}/progress
     */
    async getProjectProgress(id) {
      if (!id) throw new ApiError('Project ID is required', 400);
      return this.request(`/projects/${encodeURIComponent(id)}/progress`);
    }

    /**
     * Phase 5 Engineered governance features.
     * GET /projects/{id}/features
     */
    async getProjectFeatures(id) {
      if (!id) throw new ApiError('Project ID is required', 400);
      return this.request(`/projects/${encodeURIComponent(id)}/features`);
    }

    /**
     * Forces on-demand risk re-evaluation and persistence across all 6 engines.
     * POST /projects/{id}/risk/recalculate
     */
    async recalculateProjectRisk(id) {
      if (!id) throw new ApiError('Project ID is required', 400);
      return this.request(`/projects/${encodeURIComponent(id)}/risk/recalculate`, {
        method: 'POST'
      });
    }

    // =========================================================================
    // Phase 11 Historical Tracking & Risk History
    // =========================================================================

    /**
     * Retrieves chronological immutable project snapshots.
     * GET /projects/{id}/history
     */
    async getProjectHistory(id, params = {}) {
      if (!id) throw new ApiError('Project ID is required', 400);
      return this.request(`/projects/${encodeURIComponent(id)}/history`, { params });
    }

    /**
     * Retrieves chronological multi-detector risk assessment history.
     * GET /projects/{id}/risk-history
     */
    async getProjectRiskHistory(id, params = {}) {
      if (!id) throw new ApiError('Project ID is required', 400);
      return this.request(`/projects/${encodeURIComponent(id)}/risk-history`, { params });
    }

    /**
     * Retrieves structured meaningful deltas between project updates.
     * GET /projects/{id}/changes
     */
    async getProjectChanges(id, params = {}) {
      if (!id) throw new ApiError('Project ID is required', 400);
      return this.request(`/projects/${encodeURIComponent(id)}/changes`, { params });
    }

    // =========================================================================
    // Analytics & Macro Surveillance
    // =========================================================================

    /**
     * Macro portfolio analytics, financial aggregates, status and risk distribution.
     * GET /analytics
     */
    async getAnalytics() {
      return this.request('/analytics');
    }

    /**
     * National and portfolio KPI overview metrics.
     * GET /analytics/kpis
     */
    async getKPIs() {
      return this.request('/analytics/kpis');
    }

    /**
     * Developmental sector financial and physical progress breakdown.
     * GET /analytics/sectors
     */
    async getSectorAnalytics() {
      return this.request('/analytics/sectors');
    }

    /**
     * Real-time surveillance of delayed and stalled projects.
     * GET /analytics/delayed
     */
    async getDelayedProjects(params = {}) {
      return this.request('/analytics/delayed', { params });
    }

    /**
     * Prioritized high-risk project triage queue.
     * GET /high-risk
     */
    async getHighRiskProjects(params = {}) {
      return this.request('/high-risk', { params });
    }

    /**
     * Filtered macro portfolio overview KPIs.
     * GET /analytics/overview
     */
    async getAnalyticsOverview(params = {}) {
      return this.request('/analytics/overview', { params });
    }

    /**
     * Risk tier distribution and engine averages with filters.
     * GET /analytics/risk-distribution
     */
    async getRiskDistribution(params = {}) {
      return this.request('/analytics/risk-distribution', { params });
    }

    /**
     * State-level comparative risk, delay, and financial rankings.
     * GET /analytics/states
     */
    async getStateAnalytics(params = {}) {
      return this.request('/analytics/states', { params });
    }

    /**
     * District-level rankings and multi-criteria filters.
     * GET /analytics/districts
     */
    async getDistrictAnalytics(params = {}) {
      return this.request('/analytics/districts', { params });
    }

    /**
     * Project delay statistics, duration buckets histogram, and top overdue projects.
     * GET /analytics/delays
     */
    async getDelayAnalytics(params = {}) {
      return this.request('/analytics/delays', { params });
    }

    /**
     * Cost anomaly rates, peer median comparisons, and deviation histogram.
     * GET /analytics/cost-anomalies
     */
    async getCostAnomalyAnalytics(params = {}) {
      return this.request('/analytics/cost-anomalies', { params });
    }

    /**
     * Longitudinal time-series trends over sanction dates.
     * GET /analytics/trends
     */
    async getTemporalTrends(params = {}) {
      return this.request('/analytics/trends', { params });
    }

    /**
     * Geospatial choropleth data for India map visualization.
     * GET /analytics/map
     */
    async getMapAnalytics(params = {}) {
      return this.request('/analytics/map', { params });
    }

    /**
     * Backend and database health check.
     * GET /health
     */
    async checkHealth() {
      return this.request('/health');
    }
  }

  // Export singleton instance to global scope
  window.api = new ApiClient();
  window.ApiError = ApiError;
})();
