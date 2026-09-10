"""
query_search_examples.py
=============================================================================
Search & Analytical Query Benchmark Suite for MPLADS in PostgreSQL.
=============================================================================

Demonstrates and validates high-performance queries:
  1. Search by Project ID / Code
  2. Search by State and District (Hierarchical Geographic Filter)
  3. Search by Project Status & Sector
  4. Find Delayed / Stalled Projects
  5. Find Projects with High Expenditure / Fund Releases
  6. Find Projects with Missing Information / Governance Gaps
  7. Find High-Risk Projects with Contributing Risk Drivers
  8. Full-Text Search (tsvector & GIN Index Ranking)
  9. Fuzzy Substring Match (pg_trgm)
"""

import sys
from pathlib import Path
from typing import List, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor

# Path setup
CURRENT_DIR = Path(__file__).resolve().parent
if CURRENT_DIR.parent.name == "data":
    PROJECT_ROOT = CURRENT_DIR.parent.parent
    DATA_DIR = CURRENT_DIR.parent
elif (CURRENT_DIR.parent / "data").exists():
    PROJECT_ROOT = CURRENT_DIR.parent
    DATA_DIR = PROJECT_ROOT / "data"
else:
    PROJECT_ROOT = CURRENT_DIR.parent
    DATA_DIR = PROJECT_ROOT / "data"

sys.path.insert(0, str(DATA_DIR / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from db_config import get_db_config, get_db_connection


QUERIES = [
    {
        "title": "1. Search by Project ID",
        "description": "Direct point lookup using Primary Key index on projects(project_id).",
        "sql": """
            SELECT 
                p.project_id,
                p.project_code,
                p.project_title,
                p.sector,
                s.state_name,
                c.constituency_name,
                p.district_name,
                p.mp_name,
                p.current_status,
                f.sanctioned_amount,
                f.expenditure_amount,
                rs.overall_risk_score,
                rs.risk_level
            FROM projects p
            JOIN states s ON p.state_id = s.state_id
            JOIN constituencies c ON p.constituency_id = c.constituency_id
            JOIN financials f ON p.project_id = f.project_id
            JOIN risk_scores rs ON p.project_id = rs.project_id
            WHERE p.project_id = 'MPLADS-2024-0001';
        """
    },
    {
        "title": "2. Search by State and District",
        "description": "Geographic administrative query leveraging idx_projects_state_district composite index.",
        "sql": """
            SELECT 
                p.project_id,
                p.project_title,
                s.state_name,
                p.district_name,
                p.block_name,
                p.sector,
                p.current_status,
                f.sanctioned_amount,
                f.expenditure_amount,
                pr.physical_progress_pct
            FROM projects p
            JOIN states s ON p.state_id = s.state_id
            JOIN financials f ON p.project_id = f.project_id
            JOIN progress pr ON p.project_id = pr.project_id
            WHERE s.state_name = 'Uttar Pradesh'
            ORDER BY f.sanctioned_amount DESC;
        """
    },
    {
        "title": "3. Search by Project Status and Sector",
        "description": "Categorical query filtering active works leveraging idx_projects_status_sector composite index.",
        "sql": """
            SELECT 
                p.project_id,
                p.project_code,
                p.project_title,
                p.sector,
                p.current_status,
                p.implementing_agency,
                f.sanctioned_amount,
                f.expenditure_amount,
                f.utilization_rate_pct,
                pr.physical_progress_pct,
                pr.current_stage
            FROM projects p
            JOIN financials f ON p.project_id = f.project_id
            JOIN progress pr ON p.project_id = pr.project_id
            WHERE p.current_status = 'In Progress' AND p.sector = 'Education'
            ORDER BY f.expenditure_amount DESC;
        """
    },
    {
        "title": "4. Find Delayed and Stalled Projects",
        "description": "Operational monitoring query querying v_delayed_projects view with milestone delay analysis.",
        "sql": """
            SELECT 
                project_id,
                project_title,
                state_name,
                constituency_name,
                sector,
                current_status,
                days_delayed,
                milestone_status,
                physical_progress_pct,
                sanctioned_amount,
                delay_risk_score,
                risk_level
            FROM v_delayed_projects
            ORDER BY days_delayed DESC;
        """
    },
    {
        "title": "5. Find Projects with High Expenditure",
        "description": "Fiscal audit query identifying highest capital outlays utilizing idx_financials_expenditure.",
        "sql": """
            SELECT 
                p.project_id,
                p.project_title,
                s.state_name,
                p.sector,
                p.current_status,
                f.sanctioned_amount,
                f.released_amount,
                f.expenditure_amount,
                f.unspent_balance,
                f.utilization_rate_pct,
                f.cost_overrun_amount
            FROM projects p
            JOIN states s ON p.state_id = s.state_id
            JOIN financials f ON p.project_id = f.project_id
            WHERE f.expenditure_amount >= 2000000.00
            ORDER BY f.expenditure_amount DESC;
        """
    },
    {
        "title": "6. Find Projects with Missing Information",
        "description": "Compliance query querying v_projects_missing_information to isolate governance audit gaps.",
        "sql": """
            SELECT 
                project_id,
                project_title,
                state_name,
                constituency_name,
                current_status,
                missing_fields_count,
                array_to_string(missing_fields, '; ') AS missing_fields_detail
            FROM v_projects_missing_information
            WHERE missing_fields_count > 0
            ORDER BY missing_fields_count DESC
            LIMIT 5;
        """
    },
    {
        "title": "7. Find High-Risk Projects and Causal Factors",
        "description": "Predictive risk query querying v_high_risk_projects with aggregated JSON risk drivers.",
        "sql": """
            SELECT 
                project_id,
                project_title,
                state_name,
                sector,
                current_status,
                overall_risk_score,
                delay_risk_score,
                cost_overrun_risk_score,
                risk_level,
                days_delayed,
                primary_risk_factors
            FROM v_high_risk_projects
            ORDER BY overall_risk_score DESC
            LIMIT 5;
        """
    },
    {
        "title": "8. Full-Text Search (FTS on Project Descriptions & Metadata)",
        "description": "Natural language keyword search utilizing search_vector GIN index with relevance ranking.",
        "sql": """
            SELECT 
                p.project_id,
                p.project_title,
                p.sector,
                p.district_name,
                p.mp_name,
                f.sanctioned_amount,
                ROUND(ts_rank(p.search_vector, websearch_to_tsquery('english', 'water OR solar'))::numeric, 4) AS search_relevance
            FROM projects p
            JOIN financials f ON p.project_id = f.project_id
            WHERE p.search_vector @@ websearch_to_tsquery('english', 'water OR solar')
            ORDER BY search_relevance DESC
            LIMIT 5;
        """
    },
    {
        "title": "9. Fuzzy Substring Matching (Trigram pg_trgm)",
        "description": "Fuzzy matching on MP or agency names leveraging GIN trigram indexes.",
        "sql": """
            SELECT 
                p.project_id,
                p.project_title,
                p.mp_name,
                p.implementing_agency,
                p.district_name,
                similarity(p.implementing_agency, 'Rural Development DRDA') AS match_score
            FROM projects p
            WHERE p.implementing_agency % 'Rural Development DRDA'
               OR p.implementing_agency ILIKE '%DRDA%'
            ORDER BY match_score DESC
            LIMIT 5;
        """
    }
]


def run_benchmarks():
    cfg = get_db_config()
    print("=" * 80)
    print("MPLADS: Benchmark & Search Optimization Suite Execution")
    print(f"Database: '{cfg['dbname']}' on {cfg['host']}:{cfg['port']}")
    print("=" * 80)

    conn = get_db_connection(override_dbname=cfg["dbname"], autocommit=True)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for item in QUERIES:
                print("\n" + "#" * 80)
                print(f"QUERY: {item['title']}")
                print(f"Notes: {item['description']}")
                print("-" * 80)

                # Execute EXPLAIN to verify index usage
                explain_sql = f"EXPLAIN (COSTS OFF) {item['sql'].strip()}"
                cur.execute(explain_sql)
                plan_lines = [r["QUERY PLAN"] for r in cur.fetchall()]
                plan_summary = plan_lines[0] if plan_lines else "N/A"
                print(f"Plan Execution Plan: {plan_summary}")

                # Execute query
                cur.execute(item["sql"])
                rows = cur.fetchall()
                print(f"Rows Returned: {len(rows)}")

                if rows:
                    cols = list(rows[0].keys())
                    # Print first 3 rows
                    for idx, row in enumerate(rows[:3]):
                        print(f"  Row {idx+1}:")
                        for k, v in row.items():
                            if isinstance(v, list) and len(v) > 1:
                                print(f"    - {k}: [{len(v)} items]")
                            else:
                                print(f"    - {k}: {v}")
                else:
                    print("  (No rows matched query criteria)")

    finally:
        conn.close()

    print("\n" + "=" * 80)
    print("ALL 9 SEARCH & ANALYTICAL BENCHMARK QUERIES EXECUTED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    run_benchmarks()
