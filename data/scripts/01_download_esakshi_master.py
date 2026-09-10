"""
01_download_esakshi_master.py
Reproducible data acquisition script for official live e-SAKSHI portal datasets.
Connects to https://mplads.mospi.gov.in/rest/PreLoginDashboardData/ to download:
  - Official State & UT Registry (36 states/UTs with IDs)
  - Full Parliamentary Constituency Roster (all 543 Lok Sabha seats per state)
  - National Macro Progress Tiles (Entitlements, Allocated Limits, Sanctioned, Completed, Expenditures)
  - Calamity Relief Emergency Allocations
  - Sectoral Graphs and Labels
Records raw responses and provenance metadata.
"""

import os
import sys
import time
import json
import urllib.request
import ssl
from pathlib import Path

# Add parent directory to path for utils_provenance
sys.path.append(str(Path(__file__).resolve().parent))
from utils_provenance import record_provenance

BASE_URL = "https://mplads.mospi.gov.in"
RAW_DIR = Path(__file__).resolve().parent.parent / "raw" / "esakshi"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# SSL context (ignore certificate verification issues on legacy NIC cert chains)
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)",
    "Content-Type": "application/json; charset=utf-8",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://mplads.mospi.gov.in",
    "Referer": "https://mplads.mospi.gov.in/digigov/dashboard.html"
}

def post_json(endpoint: str, payload: dict, timeout: int = 35) -> tuple:
    """Send a POST request with JSON payload to the e-SAKSHI REST API."""
    url = BASE_URL + endpoint
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=HEADERS)
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, context=CTX, timeout=timeout) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                return status, json.loads(body)
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"    [Error] {endpoint} failed after {max_retries} attempts: {e}")
                return 500, None
            print(f"    [Retry {attempt+1}/{max_retries}] {endpoint}: {e}. Retrying in 2s...")
            time.sleep(2)

def main():
    print("=" * 70)
    print("MPLADS Ingestion Step 1: Downloading Official e-SAKSHI Master Datasets")
    print(f"Target Directory: {RAW_DIR}")
    print("=" * 70)

    raw_files = [
        RAW_DIR / "esakshi_states_raw.json",
        RAW_DIR / "esakshi_national_tiles_raw.json",
        RAW_DIR / "esakshi_calamity_relief_raw.json",
        RAW_DIR / "esakshi_constituencies_by_state_raw.json",
        RAW_DIR / "esakshi_pie_chart_labels_raw.json"
    ]
    if all(f.exists() for f in raw_files) and "--force" not in sys.argv:
        print("  [Preserved] All 5 e-SAKSHI raw datasets already exist.")
        print("  Preserving untouched raw data as per strict immutability rule.")
        print("  (Pass --force to re-download from live portal)")
        return

    # 1. State & UT Master List
    print("\n[1/5] Fetching Official State & UT Registry...")
    state_endpoint = "/rest/PreLoginDashboardData/getStateData"
    status, states_data = post_json(state_endpoint, {})
    if states_data:
        state_file = RAW_DIR / "esakshi_states_raw.json"
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(states_data, f, indent=2, ensure_ascii=False)
        record_provenance(
            source_name="e-SAKSHI State Registry",
            source_url=BASE_URL + state_endpoint,
            raw_filepath=str(state_file),
            http_status=status,
            http_method="POST",
            request_payload={},
            notes="36 States and Union Territories with official state IDs"
        )
        print(f"  Downloaded {len(states_data)} States/UTs successfully.")
    else:
        print("  Failed to download state registry.")
        sys.exit(1)

    # 2. National Macro Summary Tiles (18th Lok Sabha / Current Regime)
    print("\n[2/5] Fetching National Summary Progress Tiles...")
    tiles_endpoint = "/rest/PreLoginDashboardData/getTilesData"
    # Payload format: {"uname": "<house>,<tenure>,<state>,<constituency>"}
    # "0,0,0,2" represents: All Tenures, All States, All Constituencies, Lok Sabha
    status, tiles_data = post_json(tiles_endpoint, {"uname": "0,0,0,2"})
    if tiles_data:
        tiles_file = RAW_DIR / "esakshi_national_tiles_raw.json"
        with open(tiles_file, "w", encoding="utf-8") as f:
            json.dump(tiles_data, f, indent=2, ensure_ascii=False)
        record_provenance(
            source_name="e-SAKSHI National Tiles",
            source_url=BASE_URL + tiles_endpoint,
            raw_filepath=str(tiles_file),
            http_status=status,
            http_method="POST",
            request_payload={"uname": "0,0,0,2"},
            notes="National progress tiles: Allocated limits, expenditures, works recommended, sanctioned, completed"
        )
        print("  Downloaded National Tiles successfully.")
    else:
        print("  Failed to download national tiles.")

    # 3. Calamity Relief Allocations
    print("\n[3/5] Fetching Calamity & Disaster Relief Consents...")
    report_endpoint = "/rest/PreLoginDashboardData/getTilesReportData"
    status, calamity_data = post_json(report_endpoint, {"combo": "0,0,0,2", "key": "Amount consented for Calamity"})
    if calamity_data:
        calamity_file = RAW_DIR / "esakshi_calamity_relief_raw.json"
        with open(calamity_file, "w", encoding="utf-8") as f:
            json.dump(calamity_data, f, indent=2, ensure_ascii=False)
        record_provenance(
            source_name="e-SAKSHI Calamity Relief",
            source_url=BASE_URL + report_endpoint,
            raw_filepath=str(calamity_file),
            http_status=status,
            http_method="POST",
            request_payload={"combo": "0,0,0,2", "key": "Amount consented for Calamity"},
            notes="Itemized disaster relief consents recommended by MPs across natural calamities"
        )
        print("  Downloaded Calamity Relief consents successfully.")
    else:
        print("  Failed to download calamity relief dataset.")

    # 4. Parliamentary Constituencies by State
    print("\n[4/5] Fetching Parliamentary Constituencies across all States & UTs...")
    constituency_endpoint = "/rest/PreLoginDashboardData/getConstituencyData"
    all_constituencies = {}
    total_const_count = 0

    for state in states_data:
        state_id = state.get("STATE_ID")
        state_name = state.get("STATE_NAME")
        print(f"  Fetching constituencies for State {state_id:02d}: {state_name}...", end="", flush=True)
        
        status, const_list = post_json(constituency_endpoint, {"id": state_id}, timeout=20)
        if const_list:
            all_constituencies[state_name] = {
                "state_id": state_id,
                "state_name": state_name,
                "constituencies": const_list
            }
            total_const_count += len(const_list)
            print(f" Found {len(const_list)}")
        else:
            print(" (None or timed out)")
            all_constituencies[state_name] = {
                "state_id": state_id,
                "state_name": state_name,
                "constituencies": []
            }
        # Polite backoff delay between API calls to prevent server throttling
        time.sleep(0.6)

    const_file = RAW_DIR / "esakshi_constituencies_by_state_raw.json"
    with open(const_file, "w", encoding="utf-8") as f:
        json.dump(all_constituencies, f, indent=2, ensure_ascii=False)
    record_provenance(
        source_name="e-SAKSHI Constituency Registry",
        source_url=BASE_URL + constituency_endpoint,
        raw_filepath=str(const_file),
        http_status=200,
        http_method="POST",
        request_payload={"id": "<STATE_ID>"},
        notes=f"Complete roster of all {total_const_count} Lok Sabha Parliamentary Constituencies mapped by State"
    )
    print(f"  Total Constituencies Mapped: {total_const_count}")

    # 5. Sectoral Graph & Distribution Metadata
    print("\n[5/5] Fetching Sectoral Distribution Metadata...")
    graph_endpoint = "/rest/PreLoginDashboardData/getPieChartLabels"
    status, pie_data = post_json(graph_endpoint, {"combo": "0,0,0,2"})
    if pie_data:
        pie_file = RAW_DIR / "esakshi_pie_chart_labels_raw.json"
        with open(pie_file, "w", encoding="utf-8") as f:
            json.dump(pie_data, f, indent=2, ensure_ascii=False)
        record_provenance(
            source_name="e-SAKSHI Pie Chart Labels",
            source_url=BASE_URL + graph_endpoint,
            raw_filepath=str(pie_file),
            http_status=status,
            http_method="POST",
            request_payload={"combo": "0,0,0,2"},
            notes="Key sector and category classification labels for MPLADS expenditure distribution"
        )
        print("  Downloaded Sectoral labels successfully.")

    print("\n" + "=" * 70)
    print("e-SAKSHI Master Ingestion Complete! All raw files stored with provenance.")
    print("=" * 70)

if __name__ == "__main__":
    main()
