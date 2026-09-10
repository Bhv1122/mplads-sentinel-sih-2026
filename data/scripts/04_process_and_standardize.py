"""
04_process_and_standardize.py
Transformation and normalization pipeline for raw MPLADS datasets.
Reads from data/raw/ and generates analytics-ready relational CSV files in data/processed/:
  - esakshi_states.csv
  - esakshi_constituencies.csv
  - esakshi_national_summary.csv
  - esakshi_calamity_relief.csv
  - union_budget_mplads_1993_2025.csv
  - parliament_qa_state_expenditure.csv
  - master_dim_states_constituencies.csv
Computes statutory benchmarks (SC/ST reservation classification, utilization %, completion rates).
"""

import os
import sys
import re
import csv
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "raw"
PROCESSED_DIR = BASE_DIR / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

def clean_name(text: str) -> str:
    """Standardize entity names to title case, stripping reservation markers."""
    if not text:
        return ""
    clean = re.sub(r"\s*\((?:SC|ST)\)\s*", "", text, flags=re.IGNORECASE)
    return clean.strip().title()

def extract_reservation(caption: str) -> str:
    """Extract reservation status from constituency caption."""
    if "(SC)" in caption.upper():
        return "SC"
    elif "(ST)" in caption.upper():
        return "ST"
    return "General"

def parse_currency_string(curr_str: str) -> float:
    """Extract numeric value from Indian currency strings like ' 83,33,66,73,298.01'."""
    if not curr_str:
        return 0.0
    clean = re.sub(r"[^\d.]", "", curr_str)
    try:
        return float(clean)
    except ValueError:
        return 0.0

def process_states():
    raw_path = RAW_DIR / "esakshi" / "esakshi_states_raw.json"
    if not raw_path.exists():
        print("  [Skip] States raw file not found.")
        return []
    with open(raw_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    out_file = PROCESSED_DIR / "esakshi_states.csv"
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["state_id", "state_name", "category"])
        for row in data:
            name = row.get("STATE_NAME", "").strip()
            sid = row.get("STATE_ID")
            cat = "Union Territory" if any(u in name.lower() for u in ["islands", "chandigarh", "delhi", "haveli", "ladakh", "lakshadweep", "puducherry", "jammu and kashmir"]) else "State"
            writer.writerow([sid, name, cat])
    print(f"  Generated {out_file.name} ({len(data)} rows)")
    return data

def process_constituencies():
    raw_path = RAW_DIR / "esakshi" / "esakshi_constituencies_by_state_raw.json"
    if not raw_path.exists():
        print("  [Skip] Constituencies raw file not found.")
        return
    with open(raw_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    out_file = PROCESSED_DIR / "esakshi_constituencies.csv"
    rows_written = 0
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["constituency_id", "state_id", "state_name", "constituency_name", "raw_caption", "reservation_category"])
        for state_name, info in data.items():
            state_id = info.get("state_id")
            for c in info.get("constituencies", []):
                cid = c.get("ID")
                caption = c.get("CAPTION", "")
                c_name = clean_name(caption)
                res = extract_reservation(caption)
                writer.writerow([cid, state_id, state_name, c_name, caption, res])
                rows_written += 1
    print(f"  Generated {out_file.name} ({rows_written} rows)")

def process_national_tiles():
    raw_path = RAW_DIR / "esakshi" / "esakshi_national_tiles_raw.json"
    if not raw_path.exists():
        print("  [Skip] National tiles raw file not found.")
        return
    with open(raw_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    out_file = PROCESSED_DIR / "esakshi_national_summary.csv"
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric_key", "metric_description", "count_works", "amount_inr", "amount_crores"])
        
        for k, v in data.items():
            if k == "Current Tenure":
                continue
            count_val = None
            amount_inr = None
            amount_cr = None
            
            if isinstance(v, list):
                if len(v) == 2:
                    amount_inr = parse_currency_string(v[0])
                    amount_cr = parse_currency_string(v[1].replace("Crore", ""))
                elif len(v) == 3:
                    count_val = int(v[0])
                    amount_inr = parse_currency_string(v[1])
                    amount_cr = parse_currency_string(v[2].replace("Crore", ""))
            
            writer.writerow([k, k, count_val if count_val is not None else "", f"{amount_inr:.2f}" if amount_inr else "", f"{amount_cr:.2f}" if amount_cr else ""])
    print(f"  Generated {out_file.name}")

def process_calamity_relief():
    raw_path = RAW_DIR / "esakshi" / "esakshi_calamity_relief_raw.json"
    if not raw_path.exists():
        print("  [Skip] Calamity relief raw file not found.")
        return
    with open(raw_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    records = data.get("Total Calimity Consent", [])
    if isinstance(records, str):
        try:
            records = json.loads(records)
        except Exception:
            records = []
    out_file = PROCESSED_DIR / "esakshi_calamity_relief.csv"
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["s_no", "mp_name", "house_of_parliament", "tenure", "calamity_name", "calamity_type", "consented_amount_inr", "consented_amount_lakhs", "consent_date", "tenure_start_date", "tenure_end_date"])
        
        for r in records:
            if "Total_Amt" in r:
                continue
            sno = r.get("Sno")
            mp = r.get("MP_NAME", "").strip().title()
            house_code = r.get("HOUSE_OF_PARLIAMENT")
            house = "Lok Sabha" if house_code == 2 else "Rajya Sabha"
            tenure = r.get("TENURE")
            c_name = r.get("CALAMITY_NAME")
            c_type = r.get("TYPE")
            amt = float(r.get("CONSENTED_AMOUNT", 0))
            amt_lakhs = round(amt / 100000, 2)
            c_date = r.get("CRT_DT")
            t_start = r.get("TENURE_START_DATE")
            t_end = r.get("TENURE_END_DATE")
            writer.writerow([sno, mp, house, tenure, c_name, c_type, f"{amt:.2f}", amt_lakhs, c_date, t_start, t_end])
    print(f"  Generated {out_file.name} ({len(records)-1} items)")

def process_union_budget():
    raw_path = RAW_DIR / "union_budget" / "union_budget_mospi_demand91_raw.json"
    if not raw_path.exists():
        print("  [Skip] Union budget raw file not found.")
        return
    with open(raw_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    out_file = PROCESSED_DIR / "union_budget_mplads_1993_2025.csv"
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["financial_year", "entitlement_per_mp_cr", "budget_estimate_cr", "revised_estimate_cr", "actual_expenditure_cr", "be_vs_actual_variance_cr", "major_head", "status_notes"])
        
        for r in data:
            be = r.get("budget_estimate_cr")
            act = r.get("actual_expenditure_cr")
            var = round(act - be, 2) if (act is not None and be is not None) else ""
            writer.writerow([
                r.get("financial_year"),
                r.get("scheme_entitlement_per_mp_cr"),
                be if be is not None else "",
                r.get("revised_estimate_cr") if r.get("revised_estimate_cr") is not None else "",
                act if act is not None else "",
                var,
                r.get("major_head"),
                r.get("status")
            ])
    print(f"  Generated {out_file.name} ({len(data)} fiscal years)")

def process_parliament_qa():
    raw_path = RAW_DIR / "parliament_sansad" / "parliament_qa_state_expenditures_raw.json"
    if not raw_path.exists():
        print("  [Skip] Parliament QA raw file not found.")
        return
    with open(raw_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    out_file = PROCESSED_DIR / "parliament_qa_state_expenditure.csv"
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "state_id", "state_name", "entitlement_cr", "released_cr", "expenditure_cr",
            "unspent_balance_cr", "utilization_rate_pct", "works_recommended",
            "works_sanctioned", "works_completed", "sanction_rate_pct", "completion_rate_pct"
        ])
        
        for r in data:
            ent = r.get("entitlement_cr", 0)
            rel = r.get("released_cr", 0)
            exp = r.get("expenditure_cr", 0)
            unspent = r.get("unspent_balance_cr", 0)
            util_pct = round((exp / rel * 100), 2) if rel > 0 else 0.0
            
            w_rec = r.get("works_recommended", 0)
            w_sanc = r.get("works_sanctioned", 0)
            w_comp = r.get("works_completed", 0)
            sanc_rate = round((w_sanc / w_rec * 100), 2) if w_rec > 0 else 0.0
            comp_rate = round((w_comp / w_sanc * 100), 2) if w_sanc > 0 else 0.0
            
            writer.writerow([
                r.get("state_id"),
                r.get("state_name"),
                f"{ent:.2f}",
                f"{rel:.2f}",
                f"{exp:.2f}",
                f"{unspent:.2f}",
                util_pct,
                w_rec,
                w_sanc,
                w_comp,
                sanc_rate,
                comp_rate
            ])
    print(f"  Generated {out_file.name} ({len(data)} state profiles)")

def normalize_state_key(name: str) -> str:
    """Normalize state names for cross-dataset entity resolution."""
    if not name:
        return ""
    n = name.lower()
    n = re.sub(r"^the\s+", "", n)
    n = n.replace("&", "and")
    n = re.sub(r"\s+", " ", n)
    return n.strip()

def process_master_dimension():
    """Builds a consolidated master dimension table joining states, total seats, SC/ST seat counts, and audited spending."""
    const_file = PROCESSED_DIR / "esakshi_constituencies.csv"
    qa_file = PROCESSED_DIR / "parliament_qa_state_expenditure.csv"
    states_file = PROCESSED_DIR / "esakshi_states.csv"
    
    if not (const_file.exists() and qa_file.exists() and states_file.exists()):
        return
        
    state_seats = {}
    with open(const_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            s_name = row["state_name"]
            res = row["reservation_category"]
            if s_name not in state_seats:
                state_seats[s_name] = {"total": 0, "general": 0, "sc": 0, "st": 0}
            state_seats[s_name]["total"] += 1
            if res == "SC":
                state_seats[s_name]["sc"] += 1
            elif res == "ST":
                state_seats[s_name]["st"] += 1
            else:
                state_seats[s_name]["general"] += 1

    qa_dict = {}
    with open(qa_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            qa_dict[normalize_state_key(row["state_name"])] = row

    out_file = PROCESSED_DIR / "master_dim_states_constituencies.csv"
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "state_id", "state_name", "category", "total_lok_sabha_seats",
            "general_seats", "sc_reserved_seats", "st_reserved_seats",
            "statutory_sc_allocation_pct", "statutory_st_allocation_pct",
            "cumulative_released_cr", "cumulative_expenditure_cr", "unspent_balance_cr",
            "utilization_pct", "works_completed_count"
        ])
        
        with open(states_file, "r", encoding="utf-8") as sf:
            reader = csv.DictReader(sf)
            for row in reader:
                s_name = row["state_name"]
                sid = row["state_id"]
                cat = row["category"]
                seats = state_seats.get(s_name, {"total": 0, "general": 0, "sc": 0, "st": 0})
                qa = qa_dict.get(normalize_state_key(s_name), {})
                
                writer.writerow([
                    sid,
                    s_name,
                    cat,
                    seats["total"],
                    seats["general"],
                    seats["sc"],
                    seats["st"],
                    15.0,  # Statutory minimum SC %
                    7.5,   # Statutory minimum ST %
                    qa.get("released_cr", ""),
                    qa.get("expenditure_cr", ""),
                    qa.get("unspent_balance_cr", ""),
                    qa.get("utilization_rate_pct", ""),
                    qa.get("works_completed", "")
                ])
    print(f"  Generated {out_file.name} (Consolidated Master Dimension Table)")

def main():
    print("=" * 70)
    print("MPLADS Data Processing: Standardizing Raw Feeds into Relational Tables")
    print(f"Target Directory: {PROCESSED_DIR}")
    print("=" * 70)
    
    process_states()
    process_constituencies()
    process_national_tiles()
    process_calamity_relief()
    process_union_budget()
    process_parliament_qa()
    process_master_dimension()
    
    print("\n" + "=" * 70)
    print("Processing Complete! All relational datasets ready for analytics.")
    print("=" * 70)

if __name__ == "__main__":
    main()
