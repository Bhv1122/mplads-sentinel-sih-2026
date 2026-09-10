/**
 * frontend/js/app.js
 * =============================================================================
 * Main Application Orchestrator for MPLADS Sentinel (Stitch Frontend).
 * Registers client-side routes, binds global header search, and manages app lifecycle.
 * =============================================================================
 */

(function () {
  'use strict';

  function initApp() {
    console.log('[MPLADS Sentinel] Initializing Stitch SPA...');

    const router = window.router;
    if (!router) {
      console.error('[MPLADS Sentinel] Router not loaded.');
      return;
    }

    // Register Routes
    router.addRoute('/', window.renderDashboardView, 'dashboard');
    router.addRoute('/projects', window.renderProjectsView, 'projects');
    router.addRoute('/projects/:id', window.renderProjectDetailView, 'projects');
    router.addRoute('/investigations', window.renderInvestigationsView, 'investigations');
    router.addRoute('/analytics', window.renderAnalyticsView, 'analytics');

    // Bind Global Header Search
    const searchInput = document.getElementById('globalSearchInput');
    if (searchInput) {
      searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          const query = searchInput.value.trim();
          if (query) {
            window.location.hash = `#/projects?q=${encodeURIComponent(query)}`;
          } else {
            window.location.hash = '#/projects';
          }
        }
      });
    }

    // Initialize Router against #app-content container
    router.init('app-content');

    // Check Backend & PostgreSQL Connectivity
    if (window.api) {
      window.api.checkHealth().then(health => {
        console.log('[MPLADS Sentinel] Backend health check passed:', health);
        const indicator = document.getElementById('systemHealthDot');
        const text = document.getElementById('systemHealthText');
        if (indicator) indicator.className = 'w-2 h-2 rounded-full bg-tertiary-container animate-pulse';
        if (text) text.textContent = 'PostgreSQL Connected • Live';
      }).catch(err => {
        console.warn('[MPLADS Sentinel] Backend health check warning:', err);
        const indicator = document.getElementById('systemHealthDot');
        const text = document.getElementById('systemHealthText');
        if (indicator) indicator.className = 'w-2 h-2 rounded-full bg-error';
        if (text) text.textContent = 'Backend Offline';
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
  } else {
    initApp();
  }
})();
