"""
scripts/fix_portals.py
Fixes:
1. Replaces any 'surveillance' font text with bulletproof inline SVG in all consumer templates.
2. Ensures the Universal Role Switcher Bar is directly present in the static HTML of all 3 portals and all alias folders.
3. Synchronizes consumer, nodal-head, and site-executer folders.
"""

import os
import shutil

FRONTEND_DIR = r"d:\SIH2026\mplads-sentinel-sih-2026\frontend"

# Clean inline SVG for Card 3 (Surveillance / Audit)
SVG_CARD3 = """<div class="w-12 h-12 rounded-lg bg-amber-50 text-amber-800 flex items-center justify-center flex-shrink-0 overflow-hidden">
          <svg class="w-6 h-6 text-amber-700" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/>
          </svg>
        </div>"""

ROLE_SWITCHER_HTML = """<!-- Universal Role Switcher Bar (Direct in DOM) -->
  <div id="sentinel-role-switcher" class="w-full bg-slate-900 text-slate-200 border-b border-slate-700 py-2 px-4 sm:px-8 text-xs flex flex-wrap items-center justify-between z-50 sticky top-0 shadow-md">
    <div class="flex items-center gap-2">
      <span class="font-bold tracking-wider text-white uppercase text-[10px] bg-blue-600 px-2 py-0.5 rounded shadow-xs font-mono">PORTAL PERSONA</span>
      <span class="text-slate-400 hidden sm:inline">Switch Stakeholder View:</span>
    </div>
    <div class="flex items-center gap-1.5 mt-1 sm:mt-0 flex-wrap">
      <a href="/ui/consumer/" class="px-3 py-1 rounded font-semibold text-xs transition-all inline-flex items-center gap-1.5 {consumer_class}">
        🟢 Consumer (Citizen Portal)
      </a>
      <a href="/ui/nodal-head/" class="px-3 py-1 rounded font-semibold text-xs transition-all inline-flex items-center gap-1.5 {nodal_class}">
        🏛️ Nodal Head (Sanction & Admin)
      </a>
      <a href="/ui/site-executer/" class="px-3 py-1 rounded font-semibold text-xs transition-all inline-flex items-center gap-1.5 {executer_class}">
        🏗️ Site Executer (Field Progress)
      </a>
      <a href="/ui/overview/" class="px-3 py-1 rounded font-semibold text-xs transition-all inline-flex items-center gap-1.5 text-slate-300 hover:text-white hover:bg-slate-800">
        📊 Statutory Sentinel (HQ)
      </a>
    </div>
  </div>"""

ACTIVE_CLASS = "bg-blue-600 text-white shadow-sm ring-1 ring-blue-400"
INACTIVE_CLASS = "text-slate-300 hover:text-white hover:bg-slate-800"


def fix_consumer_file(filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()

    # Replace surveillance icon block with bulletproof SVG
    import re
    html = re.sub(
        r'<div class="w-12 h-12[^"]*bg-amber-50[^"]*">.*?<span[^>]*>surveillance</span>.*?</div>',
        SVG_CARD3,
        html,
        flags=re.DOTALL
    )

    # Ensure role switcher is at the top of body
    switcher = ROLE_SWITCHER_HTML.format(
        consumer_class=ACTIVE_CLASS,
        nodal_class=INACTIVE_CLASS,
        executer_class=INACTIVE_CLASS
    )

    if 'id="sentinel-role-switcher"' not in html:
        html = re.sub(r'<body[^>]*>', r'\g<0>\n\n  ' + switcher, html, count=1)
    else:
        # replace existing switcher
        html = re.sub(r'<!-- Universal Role Switcher Bar.*?</div>\s*</div>', switcher, html, flags=re.DOTALL)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[FIXED] {filepath}")


def fix_nodal_file(filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()

    switcher = ROLE_SWITCHER_HTML.format(
        consumer_class=INACTIVE_CLASS,
        nodal_class=ACTIVE_CLASS,
        executer_class=INACTIVE_CLASS
    )

    if 'id="sentinel-role-switcher"' not in html:
        import re
        html = re.sub(r'<body[^>]*>', r'\g<0>\n\n  ' + switcher, html, count=1)
    else:
        import re
        html = re.sub(r'<!-- Universal Role Switcher Bar.*?</div>\s*</div>', switcher, html, flags=re.DOTALL)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[FIXED] {filepath}")


def fix_executer_file(filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()

    switcher = ROLE_SWITCHER_HTML.format(
        consumer_class=INACTIVE_CLASS,
        nodal_class=INACTIVE_CLASS,
        executer_class=ACTIVE_CLASS
    )

    if 'id="sentinel-role-switcher"' not in html:
        import re
        html = re.sub(r'<body[^>]*>', r'\g<0>\n\n  ' + switcher, html, count=1)
    else:
        import re
        html = re.sub(r'<!-- Universal Role Switcher Bar.*?</div>\s*</div>', switcher, html, flags=re.DOTALL)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[FIXED] {filepath}")


def main():
    # 1. Fix Consumer files
    c_files = [
        os.path.join(FRONTEND_DIR, "consumer_portal", "index.html"),
        os.path.join(FRONTEND_DIR, "consumer_portal", "code.html"),
        os.path.join(FRONTEND_DIR, "consumer", "index.html")
    ]
    for p in c_files:
        fix_consumer_file(p)

    # 2. Fix Nodal files
    n_files = [
        os.path.join(FRONTEND_DIR, "nodal_head_portal", "index.html"),
        os.path.join(FRONTEND_DIR, "nodal_head_portal", "code.html"),
        os.path.join(FRONTEND_DIR, "nodal-head", "index.html")
    ]
    for p in n_files:
        fix_nodal_file(p)

    # 3. Fix Executer files
    e_files = [
        os.path.join(FRONTEND_DIR, "site_executer_portal", "index.html"),
        os.path.join(FRONTEND_DIR, "site_executer_portal", "code.html"),
        os.path.join(FRONTEND_DIR, "site-executer", "index.html")
    ]
    for p in e_files:
        fix_executer_file(p)

    print("All role portal files updated and synchronized successfully.")


if __name__ == "__main__":
    main()
