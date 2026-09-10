/**
 * frontend/js/router.js
 * =============================================================================
 * Client-Side Router for Stitch Multi-Screen Experience.
 * Maps routes to views, parses route params, and synchronizes sidebar active state.
 * =============================================================================
 */

(function () {
  'use strict';

  class Router {
    constructor() {
      this.routes = [];
      this.currentRoute = null;
      this.container = null;
      this.sidebarNav = null;

      window.addEventListener('hashchange', () => this.resolve());
      window.addEventListener('popstate', () => this.resolve());
    }

    init(containerId = 'app-content') {
      this.container = document.getElementById(containerId);
      this.sidebarNav = document.getElementById('sidebarNav');
      this.resolve();
    }

    addRoute(pattern, handler, viewName) {
      // Convert pattern to regex e.g. '/projects/:id' -> /^\/projects\/([^\/]+)$/
      const paramNames = [];
      const regexPath = pattern.replace(/:([a-zA-Z0-9_]+)/g, (_, name) => {
        paramNames.push(name);
        return '([^\\/]+)';
      });
      const regex = new RegExp(`^${regexPath}$`);

      this.routes.push({
        pattern,
        regex,
        paramNames,
        handler,
        viewName,
      });
    }

    navigate(path) {
      if (!path.startsWith('#')) {
        path = '#' + (path.startsWith('/') ? path : '/' + path);
      }
      window.location.hash = path;
    }

    parseHash() {
      let hash = window.location.hash || '#/';
      if (hash.startsWith('#')) hash = hash.slice(1);
      if (!hash.startsWith('/')) hash = '/' + hash;

      // Extract query string if present
      const [path, queryString] = hash.split('?');
      const queryParams = {};
      if (queryString) {
        new URLSearchParams(queryString).forEach((val, key) => {
          queryParams[key] = val;
        });
      }

      return { path: path || '/', queryParams };
    }

    async resolve() {
      const { path, queryParams } = this.parseHash();

      for (const route of this.routes) {
        const match = path.match(route.regex);
        if (match) {
          const params = {};
          route.paramNames.forEach((name, idx) => {
            params[name] = decodeURIComponent(match[idx + 1]);
          });

          this.updateActiveNav(route.viewName);

          if (this.container) {
            window.scrollTo({ top: 0, behavior: 'instant' });
            try {
              await route.handler({ params, queryParams, container: this.container });
            } catch (err) {
              console.error(`[Router] Error mounting view ${route.viewName}:`, err);
              this.renderErrorState(err);
            }
          }
          this.currentRoute = route;
          return;
        }
      }

      // Default fallback: 404 or redirect to home
      console.warn(`[Router] Route not found for path: ${path}, redirecting to #/`);
      this.navigate('/');
    }

    updateActiveNav(activeViewName) {
      const navLinks = document.querySelectorAll('[data-nav-item]');
      navLinks.forEach(link => {
        const targetView = link.getAttribute('data-nav-item');
        if (targetView === activeViewName) {
          link.classList.remove('text-secondary', 'hover:bg-surface-container', 'hover:text-on-surface', 'font-body-md');
          link.classList.add('bg-primary-container', 'text-on-primary', 'font-title-sm');
          link.setAttribute('aria-current', 'page');
        } else {
          link.classList.remove('bg-primary-container', 'text-on-primary', 'font-title-sm');
          link.classList.add('text-secondary', 'hover:bg-surface-container', 'hover:text-on-surface', 'font-body-md');
          link.removeAttribute('aria-current');
        }
      });
    }

    renderErrorState(err) {
      if (!this.container) return;
      this.container.innerHTML = `
        <div class="p-8 max-w-2xl mx-auto my-12 bg-surface-container-lowest border border-error rounded-lg shadow-sm">
          <div class="flex items-start gap-4">
            <span class="material-symbols-outlined text-error text-3xl">error</span>
            <div class="flex-1">
              <h3 class="font-bold text-lg text-on-surface mb-2">Unable to Load Screen</h3>
              <p class="text-sm text-secondary mb-4">${err.message || 'An unexpected error occurred while communicating with the backend.'}</p>
              <div class="flex gap-3">
                <button onclick="window.location.reload()" class="px-4 py-2 bg-primary text-on-primary rounded text-sm font-semibold hover:bg-primary-container">
                  Retry
                </button>
                <a href="#/" class="px-4 py-2 bg-surface-container border border-outline-variant text-on-surface rounded text-sm font-semibold hover:bg-surface-container-high">
                  Return to Dashboard
                </a>
              </div>
            </div>
          </div>
        </div>
      `;
    }
  }

  window.router = new Router();
})();
