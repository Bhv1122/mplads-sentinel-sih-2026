"""
run_all.py
Master orchestrator for the MPLADS Data Ingestion & Processing Pipeline.
Executes scripts in sequence:
  1. 01_download_esakshi_master.py
  2. 02_download_union_budget.py
  3. 03_download_parliament_qa.py
  4. 04_process_and_standardize.py
"""

import sys
import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent

def run_script(script_name: str):
    script_path = SCRIPTS_DIR / script_name
    print(f"\n>>> Executing {script_name}...")
    res = subprocess.run([sys.executable, str(script_path)])
    if res.returncode != 0:
        print(f"!!! Error executing {script_name} (exit code {res.returncode})")
        sys.exit(res.returncode)

def main():
    print("#" * 75)
    print("# SIH 2026: MPLADS Data Acquisition & Processing Pipeline")
    print("#" * 75)
    
    run_script("01_download_esakshi_master.py")
    run_script("02_download_union_budget.py")
    run_script("03_download_parliament_qa.py")
    run_script("04_process_and_standardize.py")
    run_script("05_profile_datasets.py")
    run_script("clean_mplads_data.py")
    run_script("07_validate_cleaned_data.py")
    run_script("08_audit_phase2.py")
    run_script("09_setup_database.py")
    run_script("load_to_postgres.py")
    run_script("11_verify_database.py")
    run_script("validate_database.py")
    
    print("\n" + "#" * 75)
    print("# All pipeline steps executed successfully!")
    print("#" * 75)

if __name__ == "__main__":
    main()
