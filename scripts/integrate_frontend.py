"""
scripts/integrate_frontend.py

Standardizes and integrates all 12 frontend modules with the backend:
1. Embeds the 3 Stakeholder Portals (Consumer, Nodal Head, Site Executer) in the sidebar navigation of all screens.
2. Injects the Universal Role Switcher bar into every page.
3. Removes mobile-mockup style attributes on <html> to ensure full responsive width and scrolling.
4. Generates clean alias folders (e.g., consumer, nodal-head, site-executer) so all URLs resolve seamlessly.
5. Injects frontend/assets/api.js and live data telemetry.
"""

import os
import re
import shutil

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

MODULES = {
    "consumer": {
        "folder": "consumer_portal",
        "title": "Consumer (Citizen)",
        "icon": "person"
    },
    "nodal": {
        "folder": "nodal_head_portal",
        "title": "Nodal Head (Sanctions)",
        "icon": "account_balance"
    },
    "executer": {
        "folder": "site_executer_portal",
        "title": "Site Executer (Field)",
        "icon": "engineering"
    },
    "overview": {
        "folder": "overview_dashboard_mplads_sentinel",
        "title": "HQ Overview",
        "icon": "dashboard"
    },
    "projects": {
        "folder": "projects_explorer_mplads_sentinel",
        "title": "Projects Explorer",
        "icon": "folder_managed"
    },
    "analytics": {
        "folder": "risk_analytics_portfolio_risk_telemetry_anomaly_intelligence",
        "title": "Risk Analytics",
        "icon": "query_stats"
    },
    "spatial": {
        "folder": "geographic_analysis_spatial_risk_intelligence",
        "title": "Spatial Risk",
        "icon": "travel_explore"
    },
    "audits": {
        "folder": "investigation_queue_case_management_review_triage",
        "title": "Audits & Cases",
        "icon": "fact_check"
    },
    "assistant": {
        "folder": "ai_audit_assistant_mplads_sentinel",
        "title": "AI Assistant",
        "icon": "smart_toy"
    },
    "system-status": {
        "folder": "data_system_status_mplads_sentinel",
        "title": "System Status",
        "icon": "dns"
    },
    "login": {
        "folder": "authorized_officer_login_mplads_sentinel",
        "title": "Officer Portal",
        "icon": "badge"
    }
}


def build_nav_html(current_key: str) -> str:
    """Builds a standardized <nav> element with relative links and active classes."""
    items_stakeholders = [
        ("consumer", "Consumer (Citizen)", "person"),
        ("nodal", "Nodal Head (Sanctions)", "account_balance"),
        ("executer", "Site Executer (Field)", "engineering"),
    ]
    items_operational = [
        ("overview", "HQ Overview", "dashboard"),
        ("projects", "Projects Explorer", "folder_managed"),
        ("analytics", "Risk Analytics", "query_stats"),
        ("spatial", "Spatial Risk", "travel_explore"),
        ("audits", "Audits & Cases", "fact_check"),
        ("assistant", "AI Assistant", "smart_toy"),
    ]
    items_governance = [
        ("system-status", "System Status", "dns"),
        ("login", "Officer Sign Out", "logout")
    ]

    def render_link(k, title, icon):
        folder = MODULES[k]["folder"]
        href = f"../{folder}/"
        if k == "login":
            href = f"../{MODULES['login']['folder']}/"

        if k == current_key:
            return f'''<a aria-current="page" class="flex items-center gap-unit-12 px-unit-12 py-unit-8 rounded-lg transition-colors bg-primary-container text-on-primary font-body-strong shadow-sm" data-path="{k}" href="{href}">
  <span class="material-symbols-outlined text-lg">{icon}</span>
  <span class="font-body-default text-body-default">{title}</span>
</a>'''
        else:
            return f'''<a class="flex items-center gap-unit-12 px-unit-12 py-unit-8 rounded-lg text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-colors" data-path="{k}" href="{href}">
  <span class="material-symbols-outlined text-lg">{icon}</span>
  <span class="font-body-default text-body-default">{title}</span>
</a>'''

    stk_links = "\n".join(render_link(k, t, ic) for k, t, ic in items_stakeholders)
    op_links = "\n".join(render_link(k, t, ic) for k, t, ic in items_operational)
    gov_links = "\n".join(render_link(k, t, ic) for k, t, ic in items_governance)

    return f'''<nav class="flex-1 px-unit-8 py-unit-8 space-y-unit-4 overflow-y-auto" data-active-classes="bg-primary-container text-on-primary font-body-strong">
  <div class="px-unit-8 pb-unit-2 font-micro-badge text-micro-badge uppercase text-blue-700 font-bold tracking-wider">Stakeholder Portals</div>
{stk_links}
  <div class="pt-unit-8 px-unit-8 pb-unit-2 font-micro-badge text-micro-badge uppercase text-outline tracking-wider">Operational Units</div>
{op_links}
  <div class="pt-unit-8 px-unit-8 pb-unit-2 font-micro-badge text-micro-badge uppercase text-outline tracking-wider">Governance</div>
{gov_links}
</nav>'''


def process_screen(key: str, folder_name: str):
    code_path = os.path.join(FRONTEND_DIR, folder_name, "code.html")
    if not os.path.exists(code_path):
        # might be index.html only (e.g. consumer_portal)
        index_src = os.path.join(FRONTEND_DIR, folder_name, "index.html")
        if os.path.exists(index_src):
            shutil.copyfile(index_src, code_path)
        else:
            print(f"Skipping {folder_name}: neither code.html nor index.html found.")
            return

    with open(code_path, "r", encoding="utf-8") as f:
        html = f.read()

    # 1. Clean restrictive <html> style
    html = re.sub(r'<html[^>]*>', '<html lang="en" class="h-full">', html, count=1)

    # 2. Inject assets/api.js into <head> if not present
    if "assets/api.js" not in html:
        html = html.replace("</head>", '<script src="../assets/api.js"></script>\n</head>')

    # 3. Replace <nav> block for non-login pages
    if key != "login" and "<nav" in html:
        nav_replacement = build_nav_html(key)
        html = re.sub(r'<nav[^>]*>.*?</nav>', nav_replacement, html, flags=re.DOTALL)

    # 4. Inject auto role switcher call on DOMContentLoaded if not present
    switcher_code = f'''
<script>
document.addEventListener("DOMContentLoaded", () => {{
  if (window.SentinelAPI && window.SentinelAPI.renderRoleSwitcher) {{
    window.SentinelAPI.renderRoleSwitcher("{key}");
  }}
}});
</script>
'''
    if 'renderRoleSwitcher' not in html:
        html = html.replace("</body>", switcher_code + "\n</body>")

    # Write updated code.html
    with open(code_path, "w", encoding="utf-8") as f:
        f.write(html)

    # Mirror to index.html in the same directory
    index_path = os.path.join(FRONTEND_DIR, folder_name, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[OK] Processed {key} -> {folder_name}")


def create_alias_directories():
    """Creates short alias folders so /ui/consumer, /ui/consumer/, etc. work natively."""
    aliases = {
        "consumer": "consumer_portal",
        "nodal-head": "nodal_head_portal",
        "site-executer": "site_executer_portal",
        "overview": "overview_dashboard_mplads_sentinel",
        "projects": "projects_explorer_mplads_sentinel",
        "analytics": "risk_analytics_portfolio_risk_telemetry_anomaly_intelligence",
        "spatial": "geographic_analysis_spatial_risk_intelligence",
        "audits": "investigation_queue_case_management_review_triage",
        "assistant": "ai_audit_assistant_mplads_sentinel",
        "system-status": "data_system_status_mplads_sentinel",
        "login": "authorized_officer_login_mplads_sentinel"
    }

    for alias, target_folder in aliases.items():
        alias_dir = os.path.join(FRONTEND_DIR, alias)
        os.makedirs(alias_dir, exist_ok=True)
        target_index = os.path.join(FRONTEND_DIR, target_folder, "index.html")
        if os.path.exists(target_index):
            shutil.copyfile(target_index, os.path.join(alias_dir, "index.html"))
            print(f"[OK] Alias created: frontend/{alias}/index.html from {target_folder}")


def main():
    print("Standardizing all frontend screens and role portals...")
    # Project detail
    project_profile_folder = "project_risk_profile_p_10291_multi_purpose_community_hall"
    MODULES["project-detail"] = {
        "folder": project_profile_folder,
        "title": "Project Detail",
        "icon": "analytics"
    }

    for key, mod in MODULES.items():
        process_screen(key, mod["folder"])

    create_alias_directories()
    print("Frontend synchronization complete.")


if __name__ == "__main__":
    main()
