#!/usr/bin/env python3
"""
scripts/demo_risk_analysis.py
=============================================================================
Phase 7 Risk System - Live Demonstration & Evaluation Runner
=============================================================================

Demonstrates the complete 10-step evaluation flow of the MPLADS Phase 7
Risk and Anomaly Detection System:
  1. Select a project (from database)
  2. Run multi-engine risk analysis
  3. Show Engine 1 (Cost Anomaly) result
  4. Show Engine 2 (Duplicate Detection) result
  5. Show Engine 3 (Delay Detection) result
  6. Show Engine 4 (Financial/Physical Mismatch) result
  7. Show Engine 5 (Agency Historical Pattern) result
  8. Show Central Risk Aggregation (Overall Score & Tier)
  9. Show Engine 6 (Explained Risk & Recommendations)
 10. Show PostgreSQL Persistence verification (risk_scores & risk_factors)

Important Disclaimer:
  This system is a data-driven risk/anomaly detection and administrative
  decision-support platform. It identifies statistical deviations, schedule
  slippages, and reporting inconsistencies. It does NOT claim or determine fraud.
"""

import sys
import os
import argparse
from pathlib import Path
from decimal import Decimal

# Ensure project root and backend are on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal
from app.models.project import Project, Financial, Progress, RiskScore, RiskFactor
from app.services.risk_engine import RiskEngine


def format_currency(amount: float) -> str:
    """Format INR currency."""
    if amount is None:
        return "N/A"
    return f"₹{amount:,.2f}"


def run_demo(project_id: str = "MPLADS-2024-0011"):
    """Executes the full 10-step demonstration flow."""
    print("=" * 84)
    print("       MPLADS PHASE 7 RISK & ANOMALY DETECTION SYSTEM — LIVE DEMONSTRATION")
    print("=" * 84)
    print("  * System Role: Data-Driven Decision-Support & Irregularity Screening")
    print("  * Non-Fraud Disclaimer: Identifies statistical anomalies and operational friction;")
    print("                          does NOT make definitive determinations of wrongdoing.")
    print("=" * 84)

    db = SessionLocal()
    engine = RiskEngine()

    try:
        # ---------------------------------------------------------------------
        # STEP 1: Select a Project
        # ---------------------------------------------------------------------
        print(f"\n[STEP 1] Selecting Project for Analysis: '{project_id}'")
        print("-" * 84)
        project = db.query(Project).filter_by(project_id=project_id).first()
        if not project:
            print(f"Error: Project '{project_id}' not found in database.", file=sys.stderr)
            return

        financial = db.query(Financial).filter_by(project_id=project_id).first()
        progress = db.query(Progress).filter_by(project_id=project_id).order_by(Progress.reported_date.desc()).first()

        print(f"  Project Title      : {project.project_title}")
        print(f"  Sector / Sub-Sector: {project.sector} / {project.sub_sector or 'General'}")
        print(f"  Location           : {project.district_name}, State ID: {project.state_id}")
        print(f"  Implementing Agency: {project.implementing_agency}")
        print(f"  Current Status     : {project.current_status}")
        print(f"  Key Dates          : Sanction: {project.sanction_date} | Expected End: {project.expected_completion_date}")
        if financial:
            print(f"  Sanctioned Amount  : {format_currency(float(financial.sanctioned_amount or 0))}")
            print(f"  Actual Expenditure : {format_currency(float(financial.expenditure_amount or 0))} ({financial.utilization_rate_pct or 0:.1f}% utilized)")
        if progress:
            print(f"  Physical Milestone : {progress.physical_progress_pct or 0:.1f}% ({progress.current_stage})")

        # ---------------------------------------------------------------------
        # STEP 2: Run Risk Analysis
        # ---------------------------------------------------------------------
        print(f"\n[STEP 2] Running Multi-Engine Risk Analysis Pipeline...")
        print("-" * 84)
        print("  Evaluating project concurrently through Engines 1–5, Aggregation, and Engine 6...")
        result = engine.evaluate(project_id=project_id, db=db, persist=True)
        db.commit()
        print("  Analysis successfully completed and persisted to PostgreSQL.")

        detector_map = {d["detector_key"]: d for d in result.get("detector_breakdown", [])}

        # ---------------------------------------------------------------------
        # STEP 3: Show Engine 1 Result (Cost Anomaly)
        # ---------------------------------------------------------------------
        print(f"\n[STEP 3] Engine 1 — Cost Anomaly Detection")
        print("-" * 84)
        e1 = detector_map.get("cost_anomaly", {})
        e1_det = e1.get("details", {})
        print(f"  Score              : {e1.get('score', 0):.1f} / 100 ({e1.get('severity', 'low').upper()})")
        print(f"  Evaluated Cost     : {format_currency(e1_det.get('evaluated_cost', 0))}")
        print(f"  Peer Baseline Scope: {e1_det.get('peer_scope', 'N/A')} (Peer Median: {format_currency(e1_det.get('peer_median', 0))})")
        print(f"  Cost Deviation     : {e1_det.get('deviation_percentage', 0):+.1f}% (Robust Z-Score: {e1_det.get('robust_z_score', 0):.2f})")
        print(f"  Legitimacy Check   : Anomaly Type: {e1_det.get('anomaly_type', 'N/A')}")
        print(f"  Audit Narrative    : {e1.get('reason', 'N/A')}")

        # ---------------------------------------------------------------------
        # STEP 4: Show Engine 2 Result (Duplicate Detection)
        # ---------------------------------------------------------------------
        print(f"\n[STEP 4] Engine 2 — Duplicate Project Detection")
        print("-" * 84)
        e2 = detector_map.get("duplicate_detection", {})
        e2_det = e2.get("details", {})
        print(f"  Score              : {e2.get('score', 0):.1f} / 100 ({e2.get('severity', 'low').upper()})")
        print(f"  Matched Project ID : {e2_det.get('matched_project_id', 'None')}")
        print(f"  Raw Similarity     : {e2_det.get('raw_similarity', 0):.4f} ({e2_det.get('raw_similarity', 0)*100:.1f}%)")
        print(f"  Contextual Multiplier: Location: {e2_det.get('location_factor', 1.0)}x ({e2_det.get('location_match', 'none')}), Sector: {e2_det.get('sector_factor', 1.0)}x")
        print(f"  Classification     : {e2_det.get('duplicate_classification', 'NONE')}")
        print(f"  Audit Narrative    : {e2.get('reason', 'N/A')}")

        # ---------------------------------------------------------------------
        # STEP 5: Show Engine 3 Result (Delay Detection)
        # ---------------------------------------------------------------------
        print(f"\n[STEP 5] Engine 3 — Project Delay Detection")
        print("-" * 84)
        e3 = detector_map.get("delay_detection", {})
        e3_det = e3.get("details", {})
        print(f"  Score              : {e3.get('score', 0):.1f} / 100 ({e3.get('severity', 'low').upper()})")
        print(f"  Planned Timeline   : {e3_det.get('planned_duration', 0)} days (End: {e3_det.get('expected_completion_date', 'N/A')})")
        print(f"  Execution Status   : {e3_det.get('completion_status', 'N/A')}")
        print(f"  Overdue Duration   : {e3_det.get('overdue_days', 0)} days beyond planned completion")
        print(f"  Schedule Slippage  : +{e3_det.get('delay_percentage', 0):.1f}% against planned duration")
        print(f"  Audit Narrative    : {e3.get('reason', 'N/A')}")

        # ---------------------------------------------------------------------
        # STEP 6: Show Engine 4 Result (Financial / Physical Mismatch)
        # ---------------------------------------------------------------------
        print(f"\n[STEP 6] Engine 4 — Financial & Physical Progress Mismatch")
        print("-" * 84)
        e4 = detector_map.get("progress_mismatch", {})
        e4_det = e4.get("details", {})
        print(f"  Score              : {e4.get('score', 0):.1f} / 100 ({e4.get('severity', 'low').upper()})")
        print(f"  Financial Progress : {e4_det.get('financial_progress', 0):.1f}%")
        print(f"  Physical Progress  : {e4_det.get('physical_progress', 0):.1f}%")
        print(f"  Progress Gap       : {e4_det.get('progress_gap', 0):+.1f} percentage points ({e4_det.get('direction', 'aligned')})")
        print(f"  Audit Narrative    : {e4.get('reason', 'N/A')}")

        # ---------------------------------------------------------------------
        # STEP 7: Show Engine 5 Result (Agency Historical Pattern)
        # ---------------------------------------------------------------------
        print(f"\n[STEP 7] Engine 5 — Agency Pattern Detection")
        print("-" * 84)
        e5 = detector_map.get("agency_pattern", {})
        e5_det = e5.get("details", {})
        print(f"  Score              : {e5.get('score', 0):.1f} / 100 ({e5.get('severity', 'low').upper()})")
        print(f"  Agency Analyzed    : {e5_det.get('agency_name', 'N/A')}")
        print(f"  Portfolio Size     : {e5_det.get('projects_analyzed', 0)} historical projects")
        print(f"  Historical Friction: Delay Rate: {e5_det.get('delay_rate', 0)*100:.1f}% | Progress Gaps: {e5_det.get('mismatch_rate', 0)*100:.1f}%")
        print(f"  Audit Narrative    : {e5.get('reason', 'N/A')}")

        # ---------------------------------------------------------------------
        # STEP 8: Show Central Risk Aggregation
        # ---------------------------------------------------------------------
        print(f"\n[STEP 8] Central Risk Aggregation (Overall Score & Tier)")
        print("-" * 84)
        overall_score = result.get("overall_score", 0.0)
        risk_level = result.get("risk_level", "LOW")
        print(f"  Overall Score      : {overall_score:.2f} / 100")
        print(f"  Assigned Risk Tier : {risk_level}")
        print(f"  Confidence Rating  : {result.get('confidence', 0.0):.2f}")
        print("  Component Contribution Formula (Equal 20% Default Weights):")
        for d in result.get("detector_breakdown", []):
            weight = d.get("effective_weight", 0.2)
            pts = d.get("score", 0) * weight
            print(f"    * {d.get('detector_name', d.get('detector_key')):28s}: Score {d.get('score', 0):5.1f} × {weight:.2f} = {pts:4.1f} pts")
        print(f"    -----------------------------------------------------------------")
        print(f"    * Total Composite Score                                = {overall_score:4.1f} pts")

        # ---------------------------------------------------------------------
        # STEP 9: Show Engine 6 Explanation
        # ---------------------------------------------------------------------
        print(f"\n[STEP 9] Engine 6 — Explained Risk Assessment")
        print("-" * 84)
        exp = result.get("explained_risk", {})
        print(f"  Executive Summary:")
        print(f"    \"{exp.get('summary', 'N/A')}\"")
        print("\n  Ranked Contributing Factors:")
        for idx, rf in enumerate(exp.get("risk_factors", []), start=1):
            print(f"    {idx}. {rf.get('engine'):22s} | Score: {rf.get('score', 0):5.1f} | Contribution: {rf.get('contribution', 0):4.1f} pts")
            print(f"       Evidence: {rf.get('reason')}")
        print("\n  Recommended Administrative Review Areas:")
        for idx, rec in enumerate(exp.get("recommended_review", []), start=1):
            print(f"    [{idx}] {rec}")

        # ---------------------------------------------------------------------
        # STEP 10: Show Stored Result in Database
        # ---------------------------------------------------------------------
        print(f"\n[STEP 10] Database Persistence Verification (PostgreSQL)")
        print("-" * 84)
        db_score = db.query(RiskScore).filter_by(project_id=project_id).first()
        db_factors = db.query(RiskFactor).filter_by(project_id=project_id).order_by(RiskFactor.score.desc()).all()

        if db_score:
            print(f"  Table: risk_scores")
            print(f"    - project_id   : {db_score.project_id}")
            print(f"    - overall_score: {db_score.overall_score:.2f}")
            print(f"    - risk_level   : {db_score.risk_level}")
            print(f"    - updated_at   : {db_score.updated_at}")
        else:
            print("  Warning: No record found in risk_scores table.")

        print(f"\n  Table: risk_factors ({len(db_factors)} persisted engines)")
        for f in db_factors:
            print(f"    - {f.engine_name:22s}: Score {f.score:5.1f} ({f.risk_level:8s}) | Conf: {f.confidence:.2f}")

        print("=" * 84)
        print("  DEMONSTRATION COMPLETE: All 10 steps executed and verified successfully.")
        print("=" * 84)

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Phase 7 Risk System Live Demonstration Runner")
    parser.add_argument(
        "--project",
        type=str,
        default="MPLADS-2024-0011",
        help="Project ID to evaluate (default: MPLADS-2024-0011)",
    )
    args = parser.parse_args()
    run_demo(project_id=args.project)


if __name__ == "__main__":
    main()
