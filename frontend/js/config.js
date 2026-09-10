/**
 * frontend/js/config.js
 * =============================================================================
 * Environment Configuration for MPLADS Sentinel Stitch Application.
 * Resolves API Base URL dynamically without hardcoding localhost.
 * =============================================================================
 */

(function () {
  'use strict';

  // Check for externally injected env, localStorage override, or default to current origin
  const origin = window.location.origin && window.location.origin !== 'null'
    ? window.location.origin
    : 'http://127.0.0.1:8000';

  const defaultApiBase = (window.VITE_API_URL || window.__ENV?.API_BASE_URL || localStorage.getItem('MPLADS_API_URL') || origin).replace(/\/+$/, '');

  window.MPLADS_CONFIG = {
    API_BASE_URL: defaultApiBase,
    APP_NAME: 'MPLADS Sentinel',
    APP_SUBTITLE: 'Ministry of Statistics & Programme Implementation | Govt. of India',
    VERSION: '1.0.0',
    DEFAULT_PAGE_SIZE: 15,
    REFRESH_INTERVAL_MS: 60000,
    CURRENCY_LOCALE: 'en-IN',
  };

  // Allow runtime override via console for testing/staging deployments:
  // window.setApiUrl('https://api.example.gov.in')
  window.setApiUrl = function (url) {
    if (!url) return;
    const clean = url.replace(/\/+$/, '');
    localStorage.setItem('MPLADS_API_URL', clean);
    window.MPLADS_CONFIG.API_BASE_URL = clean;
    console.log(`[MPLADS Config] API Base URL set to: ${clean}`);
    window.location.reload();
  };
})();
