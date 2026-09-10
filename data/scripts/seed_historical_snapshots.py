"""
data/scripts/seed_historical_snapshots.py
=============================================================================
Populates rich, multi-snapshot historical risk trajectories and point-in-time
project snapshots for key MPLADS projects.

Enables authentic longitudinal risk trend visualization and multi-detector
evolution testing.
=============================================================================
"""

import os
import sys
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal

# Ensure backend package is in python path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.database import SessionLocal, engine
from app.models.project import (
    Project, ProjectSnapshot, RiskHistory, Financial, Progress, RiskScore
)



def seed_project_history():
    db = SessionLocal()
    print("Beginning seeding of historical snapshots and risk history...")

    # Clear existing snapshots and risk history to start clean
    db.query(RiskHistory).delete()
    db.query(ProjectSnapshot).delete()
    db.commit()
    print("Cleared existing historical snapshots and risk history records.")

    # -------------------------------------------------------------------------
    # Project 1: MPLADS-2024-0002 (Additional Classrooms in Govt High School)
    # Trajectory: Low Risk (18) -> Low (24) -> Moderate (38) -> High (54) -> Moderate (46)
    # Demonstrates: Schedule slippage, then cost escalation, then partial recovery.
    # -------------------------------------------------------------------------
    p2 = db.query(Project).filter(Project.project_id == "MPLADS-2024-0002").first()
    if p2:
        snapshots_data_p2 = [
            {
                "datetime": datetime(2024, 8, 1, 10, 0, tzinfo=timezone.utc),
                "date": date(2024, 8, 1),
                "status": "Sanctioned",
                "sanctioned": Decimal("2500000.00"),
                "released": Decimal("1000000.00"),
                "spent": Decimal("0.00"),
                "physical_pct": Decimal("0.00"),
                "financial_pct": Decimal("0.00"),
                "days_delayed": 0,
                "milestone": "Sanction Order",
                "overall_risk": Decimal("18.00"),
                "risk_level": "Low",
                "summary": "Administrative sanction granted under DPR approval. Baseline audit snapshot registered.",
                "detectors": {
                    "cost_anomaly": {"score": 5.0, "severity": "low", "reason": "Baseline sanction matches scheduled DPR estimates."},
                    "duplicate_detection": {"score": 0.0, "severity": "low", "reason": "No spatial or textual duplication detected."},
                    "delay_detection": {"score": 0.0, "severity": "low", "reason": "Project on track from sanction date."},
                    "fund_utilization": {"score": 10.0, "severity": "low", "reason": "Initial installment released to agency account."},
                    "progress_mismatch": {"score": 0.0, "severity": "low", "reason": "No execution drawdown yet."},
                    "agency_pattern": {"score": 14.0, "severity": "low", "reason": "Agency historical completion rate is satisfactory."}
                },
                "sub_scores": {"delay": 0.0, "cost": 5.0, "non_completion": 0.0, "leakage": 10.0}
            },
            {
                "datetime": datetime(2024, 10, 15, 11, 30, tzinfo=timezone.utc),
                "date": date(2024, 10, 15),
                "status": "In Progress",
                "sanctioned": Decimal("2500000.00"),
                "released": Decimal("1000000.00"),
                "spent": Decimal("625000.00"),
                "physical_pct": Decimal("22.00"),
                "financial_pct": Decimal("25.00"),
                "days_delayed": 8,
                "milestone": "Plinth Complete",
                "overall_risk": Decimal("25.50"),
                "risk_level": "Low",
                "summary": "Plinth level inspection completed. Minor 8-day rain delay noted by Junior Engineer.",
                "detectors": {
                    "cost_anomaly": {"score": 12.0, "severity": "low", "reason": "Material procurement cost within 5% of district SOR."},
                    "duplicate_detection": {"score": 0.0, "severity": "low", "reason": "No duplication identified."},
                    "delay_detection": {"score": 18.0, "severity": "low", "reason": "8 calendar days slippage due to monsoon waterlogging."},
                    "fund_utilization": {"score": 15.0, "severity": "low", "reason": "62.5% of first release utilized in 75 days."},
                    "progress_mismatch": {"score": 8.0, "severity": "low", "reason": "Physical (22%) closely matches financial draw (25%)."},
                    "agency_pattern": {"score": 14.0, "severity": "low", "reason": "Standard agency operational profile."}
                },
                "sub_scores": {"delay": 18.0, "cost": 12.0, "non_completion": 8.0, "leakage": 15.0}
            },
            {
                "datetime": datetime(2024, 12, 28, 14, 0, tzinfo=timezone.utc),
                "date": date(2024, 12, 28),
                "status": "In Progress",
                "sanctioned": Decimal("2500000.00"),
                "released": Decimal("2000000.00"),
                "spent": Decimal("1350000.00"),
                "physical_pct": Decimal("38.00"),
                "financial_pct": Decimal("54.00"),
                "days_delayed": 38,
                "milestone": "Superstructure Frame",
                "overall_risk": Decimal("41.20"),
                "risk_level": "Moderate",
                "summary": "Second tranche disbursed. Milestone lag emerged: financial draw (54%) exceeds physical ground completion (38%).",
                "detectors": {
                    "cost_anomaly": {"score": 32.0, "severity": "moderate", "reason": "Brickwork unit costs higher than peer median."},
                    "duplicate_detection": {"score": 0.0, "severity": "low", "reason": "Verified unique location coordinates."},
                    "delay_detection": {"score": 45.0, "severity": "moderate", "reason": "38 calendar days delayed past scheduled lintel stage."},
                    "fund_utilization": {"score": 28.0, "severity": "low", "reason": "Fund utilization pace steady."},
                    "progress_mismatch": {"score": 36.0, "severity": "moderate", "reason": "16% progress deficit between drawdown and physical verification."},
                    "agency_pattern": {"score": 18.0, "severity": "low", "reason": "Agency active across 3 other simultaneous works."}
                },
                "sub_scores": {"delay": 45.0, "cost": 32.0, "non_completion": 36.0, "leakage": 28.0}
            },
            {
                "datetime": datetime(2025, 3, 20, 16, 45, tzinfo=timezone.utc),
                "date": date(2025, 3, 20),
                "status": "In Progress",
                "sanctioned": Decimal("2500000.00"),
                "released": Decimal("2000000.00"),
                "spent": Decimal("1800000.00"),
                "physical_pct": Decimal("48.00"),
                "financial_pct": Decimal("72.00"),
                "days_delayed": 74,
                "milestone": "Roof Slab Delayed",
                "overall_risk": Decimal("55.80"),
                "risk_level": "High",
                "summary": "Audit scan flagged acute progress gap (+24% financial surplus over physical execution) and 74-day milestone delay.",
                "detectors": {
                    "cost_anomaly": {"score": 48.0, "severity": "moderate", "reason": "Steel reinforcement draw outpaced roof casting inspection."},
                    "duplicate_detection": {"score": 0.0, "severity": "low", "reason": "No duplication identified."},
                    "delay_detection": {"score": 72.0, "severity": "high", "reason": "74 days past scheduled roof casting target."},
                    "fund_utilization": {"score": 34.0, "severity": "moderate", "reason": "Treasury balance depleted to 10% of total allocation."},
                    "progress_mismatch": {"score": 62.0, "severity": "high", "reason": "24% delivery lag flagged under Section 7(b) rule."},
                    "agency_pattern": {"score": 25.0, "severity": "moderate", "reason": "Agency flagged for delay clustering in sub-district."}
                },
                "sub_scores": {"delay": 72.0, "cost": 48.0, "non_completion": 62.0, "leakage": 34.0}
            },
            {
                "datetime": datetime(2025, 6, 12, 9, 15, tzinfo=timezone.utc),
                "date": date(2025, 6, 12),
                "status": "In Progress",
                "sanctioned": Decimal("2500000.00"),
                "released": Decimal("2000000.00"),
                "spent": Decimal("1800000.00"),
                "physical_pct": Decimal("65.00"),
                "financial_pct": Decimal("72.00"),
                "days_delayed": 45,
                "milestone": "Finishing Underway",
                "overall_risk": Decimal("46.00"),
                "risk_level": "Moderate",
                "summary": "Contractor accelerated work after executive engineer notice. Physical progress climbed to 65%, reducing the mismatch gap.",
                "detectors": {
                    "cost_anomaly": {"score": 38.0, "severity": "moderate", "reason": "Material expenditure reconciled with certified measurements."},
                    "duplicate_detection": {"score": 0.0, "severity": "low", "reason": "Unique site verification confirmed."},
                    "delay_detection": {"score": 52.0, "severity": "moderate", "reason": "Net schedule delay reduced from 74d to 45d."},
                    "fund_utilization": {"score": 25.0, "severity": "low", "reason": "Unspent balance aligned with finishing estimates."},
                    "progress_mismatch": {"score": 22.0, "severity": "low", "reason": "Progress deficit compressed from 24% to 7%."},
                    "agency_pattern": {"score": 20.0, "severity": "low", "reason": "Agency restored active workforce on site."}
                },
                "sub_scores": {"delay": 52.0, "cost": 38.0, "non_completion": 22.0, "leakage": 25.0}
            }
        ]

        for item in snapshots_data_p2:
            snap = ProjectSnapshot(
                project_id="MPLADS-2024-0002",
                snapshot_datetime=item["datetime"],
                snapshot_date=item["date"],
                project_status=item["status"],
                recommended_amount=Decimal("2500000.00"),
                sanctioned_amount=item["sanctioned"],
                released_amount=item["released"],
                expenditure_amount=item["spent"],
                unspent_balance=item["released"] - item["spent"],
                utilization_rate_pct=round((item["spent"] / item["sanctioned"] * 100), 2) if item["sanctioned"] > 0 else Decimal("0.00"),
                cost_overrun_amount=Decimal("0.00"),
                physical_progress_pct=item["physical_pct"],
                financial_progress_pct=item["financial_pct"],
                days_delayed=item["days_delayed"],
                milestone_status=item["milestone"],
                cost_deviation=Decimal("0.00"),
                progress_gap=item["financial_pct"] - item["physical_pct"],
                overall_risk_score=item["overall_risk"],
                risk_level=item["risk_level"],
                change_summary=item["summary"],
                created_at=item["datetime"]
            )
            db.add(snap)
            db.flush()

            rh = RiskHistory(
                project_id="MPLADS-2024-0002",
                snapshot_id=snap.snapshot_id,
                overall_risk_score=item["overall_risk"],
                risk_level=item["risk_level"],
                delay_risk_score=Decimal(str(item["sub_scores"]["delay"])),
                cost_overrun_risk_score=Decimal(str(item["sub_scores"]["cost"])),
                non_completion_risk_score=Decimal(str(item["sub_scores"]["non_completion"])),
                leakage_risk_score=Decimal(str(item["sub_scores"]["leakage"])),
                detector_scores=item["detectors"],
                weights_used={
                    "cost_anomaly": 0.20,
                    "duplicate_detection": 0.20,
                    "delay_detection": 0.20,
                    "progress_mismatch": 0.20,
                    "agency_pattern": 0.20
                },
                calculated_at=item["datetime"],
                created_at=item["datetime"]
            )
            db.add(rh)
        print("Seeded 5 chronological snapshots for MPLADS-2024-0002.")

    # -------------------------------------------------------------------------
    # Project 2: MPLADS-2024-0005 (Construction of Cement Concrete Road & D)
    # Trajectory: Low Risk (16) -> Moderate (34) -> High (56) -> Critical (78)
    # Demonstrates: Project Stalled, rapid risk escalation across delay, agency, and progress.
    # -------------------------------------------------------------------------
    p5 = db.query(Project).filter(Project.project_id == "MPLADS-2024-0005").first()
    if p5:
        snapshots_data_p5 = [
            {
                "datetime": datetime(2024, 7, 20, 10, 0, tzinfo=timezone.utc),
                "date": date(2024, 7, 20),
                "status": "Sanctioned",
                "sanctioned": Decimal("2000000.00"),
                "released": Decimal("800000.00"),
                "spent": Decimal("0.00"),
                "physical_pct": Decimal("0.00"),
                "financial_pct": Decimal("0.00"),
                "days_delayed": 0,
                "milestone": "Sanction Baseline",
                "overall_risk": Decimal("16.00"),
                "risk_level": "Low",
                "summary": "Initial baseline sanction issued for 1.2km CC road and side drain.",
                "detectors": {
                    "cost_anomaly": {"score": 8.0, "severity": "low", "reason": "Standard road estimates."},
                    "duplicate_detection": {"score": 0.0, "severity": "low", "reason": "No spatial duplication."},
                    "delay_detection": {"score": 0.0, "severity": "low", "reason": "On schedule."},
                    "fund_utilization": {"score": 10.0, "severity": "low", "reason": "First release credited."},
                    "progress_mismatch": {"score": 0.0, "severity": "low", "reason": "Baseline state."},
                    "agency_pattern": {"score": 20.0, "severity": "low", "reason": "Agency verified."}
                },
                "sub_scores": {"delay": 0.0, "cost": 8.0, "non_completion": 0.0, "leakage": 10.0}
            },
            {
                "datetime": datetime(2024, 9, 30, 11, 0, tzinfo=timezone.utc),
                "date": date(2024, 9, 30),
                "status": "In Progress",
                "sanctioned": Decimal("2000000.00"),
                "released": Decimal("1200000.00"),
                "spent": Decimal("600000.00"),
                "physical_pct": Decimal("25.00"),
                "financial_pct": Decimal("30.00"),
                "days_delayed": 15,
                "milestone": "Sub-grade & Base Course",
                "overall_risk": Decimal("31.40"),
                "risk_level": "Moderate",
                "summary": "Earthwork and base course laid. Initial 15-day delay reported due to utility shifting.",
                "detectors": {
                    "cost_anomaly": {"score": 22.0, "severity": "low", "reason": "Gravel aggregate rates normal."},
                    "duplicate_detection": {"score": 0.0, "severity": "low", "reason": "No duplication."},
                    "delay_detection": {"score": 38.0, "severity": "moderate", "reason": "15 days behind target."},
                    "fund_utilization": {"score": 20.0, "severity": "low", "reason": "Fund utilization moderate."},
                    "progress_mismatch": {"score": 18.0, "severity": "low", "reason": "5% gap within normal limits."},
                    "agency_pattern": {"score": 25.0, "severity": "low", "reason": "Agency staffing slightly below plan."}
                },
                "sub_scores": {"delay": 38.0, "cost": 22.0, "non_completion": 18.0, "leakage": 20.0}
            },
            {
                "datetime": datetime(2024, 12, 10, 15, 0, tzinfo=timezone.utc),
                "date": date(2024, 12, 10),
                "status": "In Progress",
                "sanctioned": Decimal("2000000.00"),
                "released": Decimal("1200000.00"),
                "spent": Decimal("1100000.00"),
                "physical_pct": Decimal("32.00"),
                "financial_pct": Decimal("55.00"),
                "days_delayed": 62,
                "milestone": "Concreting Halted",
                "overall_risk": Decimal("52.80"),
                "risk_level": "High",
                "summary": "Concreting ceased. Financial drawdowns reached 55% while physical progress halted at 32%.",
                "detectors": {
                    "cost_anomaly": {"score": 45.0, "severity": "moderate", "reason": "Cement supply invoices disputed."},
                    "duplicate_detection": {"score": 0.0, "severity": "low", "reason": "No duplication."},
                    "delay_detection": {"score": 68.0, "severity": "high", "reason": "62 days schedule delay."},
                    "fund_utilization": {"score": 40.0, "severity": "moderate", "reason": "High expenditure with stalled output."},
                    "progress_mismatch": {"score": 60.0, "severity": "high", "reason": "23% progress discrepancy index."},
                    "agency_pattern": {"score": 42.0, "severity": "moderate", "reason": "Agency abandoned another local work."}
                },
                "sub_scores": {"delay": 68.0, "cost": 45.0, "non_completion": 60.0, "leakage": 40.0}
            },
            {
                "datetime": datetime(2025, 3, 15, 12, 0, tzinfo=timezone.utc),
                "date": date(2025, 3, 15),
                "status": "Stalled",
                "sanctioned": Decimal("2000000.00"),
                "released": Decimal("1200000.00"),
                "spent": Decimal("1200000.00"),
                "physical_pct": Decimal("35.00"),
                "financial_pct": Decimal("60.00"),
                "days_delayed": 145,
                "milestone": "Formally Declared Stalled",
                "overall_risk": Decimal("74.20"),
                "risk_level": "Critical",
                "summary": "Project status formally transitioned to 'Stalled'. Contractor abandoned site; forfeiture proceedings initiated.",
                "detectors": {
                    "cost_anomaly": {"score": 65.0, "severity": "high", "reason": "Unrecovered advance expenditure."},
                    "duplicate_detection": {"score": 0.0, "severity": "low", "reason": "No duplication."},
                    "delay_detection": {"score": 92.0, "severity": "critical", "reason": "145 days delayed; past planned completion."},
                    "fund_utilization": {"score": 55.0, "severity": "high", "reason": "Funds exhausted with only 35% physical delivery."},
                    "progress_mismatch": {"score": 78.0, "severity": "critical", "reason": "Severe 25% delivery deficit."},
                    "agency_pattern": {"score": 68.0, "severity": "high", "reason": "Agency blacklisting recommended by district committee."}
                },
                "sub_scores": {"delay": 92.0, "cost": 65.0, "non_completion": 78.0, "leakage": 55.0}
            }
        ]

        for item in snapshots_data_p5:
            snap = ProjectSnapshot(
                project_id="MPLADS-2024-0005",
                snapshot_datetime=item["datetime"],
                snapshot_date=item["date"],
                project_status=item["status"],
                recommended_amount=Decimal("2000000.00"),
                sanctioned_amount=item["sanctioned"],
                released_amount=item["released"],
                expenditure_amount=item["spent"],
                unspent_balance=item["released"] - item["spent"],
                utilization_rate_pct=round((item["spent"] / item["sanctioned"] * 100), 2) if item["sanctioned"] > 0 else Decimal("0.00"),
                cost_overrun_amount=Decimal("0.00"),
                physical_progress_pct=item["physical_pct"],
                financial_progress_pct=item["financial_pct"],
                days_delayed=item["days_delayed"],
                milestone_status=item["milestone"],
                cost_deviation=Decimal("0.00"),
                progress_gap=item["financial_pct"] - item["physical_pct"],
                overall_risk_score=item["overall_risk"],
                risk_level=item["risk_level"],
                change_summary=item["summary"],
                created_at=item["datetime"]
            )
            db.add(snap)
            db.flush()

            rh = RiskHistory(
                project_id="MPLADS-2024-0005",
                snapshot_id=snap.snapshot_id,
                overall_risk_score=item["overall_risk"],
                risk_level=item["risk_level"],
                delay_risk_score=Decimal(str(item["sub_scores"]["delay"])),
                cost_overrun_risk_score=Decimal(str(item["sub_scores"]["cost"])),
                non_completion_risk_score=Decimal(str(item["sub_scores"]["non_completion"])),
                leakage_risk_score=Decimal(str(item["sub_scores"]["leakage"])),
                detector_scores=item["detectors"],
                weights_used={
                    "cost_anomaly": 0.20,
                    "duplicate_detection": 0.20,
                    "delay_detection": 0.20,
                    "progress_mismatch": 0.20,
                    "agency_pattern": 0.20
                },
                calculated_at=item["datetime"],
                created_at=item["datetime"]
            )
            db.add(rh)
        print("Seeded 4 chronological snapshots for MPLADS-2024-0005.")

    # -------------------------------------------------------------------------
    # Project 3: MPLADS-2024-0001 (Community RO Plant)
    # Trajectory: Low (15) -> Low (18) -> Low (21) -> Low (22.6)
    # Demonstrates: Clean, well-governed project with steady progress to completion.
    # -------------------------------------------------------------------------
    p1 = db.query(Project).filter(Project.project_id == "MPLADS-2024-0001").first()
    if p1:
        snapshots_data_p1 = [
            {
                "datetime": datetime(2024, 7, 10, 9, 30, tzinfo=timezone.utc),
                "date": date(2024, 7, 10),
                "status": "Sanctioned",
                "sanctioned": Decimal("1500000.00"),
                "released": Decimal("750000.00"),
                "spent": Decimal("0.00"),
                "physical_pct": Decimal("0.00"),
                "financial_pct": Decimal("0.00"),
                "days_delayed": 0,
                "milestone": "Administrative Sanction",
                "overall_risk": Decimal("15.00"),
                "risk_level": "Low",
                "summary": "Sanction order issued for 1000 LPH RO purification plant.",
                "detectors": {
                    "cost_anomaly": {"score": 5.0, "severity": "low", "reason": "Standard equipment cost schedule."},
                    "duplicate_detection": {"score": 0.0, "severity": "low", "reason": "Unique site coordinates."},
                    "delay_detection": {"score": 0.0, "severity": "low", "reason": "Initial state."},
                    "fund_utilization": {"score": 8.0, "severity": "low", "reason": "Initial release credited."},
                    "progress_mismatch": {"score": 0.0, "severity": "low", "reason": "On track."},
                    "agency_pattern": {"score": 12.0, "severity": "low", "reason": "Experienced water board agency."}
                },
                "sub_scores": {"delay": 0.0, "cost": 5.0, "non_completion": 0.0, "leakage": 8.0}
            },
            {
                "datetime": datetime(2024, 9, 5, 11, 0, tzinfo=timezone.utc),
                "date": date(2024, 9, 5),
                "status": "In Progress",
                "sanctioned": Decimal("1500000.00"),
                "released": Decimal("750000.00"),
                "spent": Decimal("550000.00"),
                "physical_pct": Decimal("45.00"),
                "financial_pct": Decimal("36.67"),
                "days_delayed": 0,
                "milestone": "Shed Structure Built",
                "overall_risk": Decimal("18.20"),
                "risk_level": "Low",
                "summary": "Civil shed construction completed on schedule; machinery dispatched.",
                "detectors": {
                    "cost_anomaly": {"score": 8.0, "severity": "low", "reason": "Shed costs within budget."},
                    "duplicate_detection": {"score": 0.0, "severity": "low", "reason": "Verified."},
                    "delay_detection": {"score": 0.0, "severity": "low", "reason": "Ahead of schedule."},
                    "fund_utilization": {"score": 12.0, "severity": "low", "reason": "Healthy drawdown rate."},
                    "progress_mismatch": {"score": 4.0, "severity": "low", "reason": "Physical delivery leading disbursements."},
                    "agency_pattern": {"score": 12.0, "severity": "low", "reason": "Standard agency profile."}
                },
                "sub_scores": {"delay": 0.0, "cost": 8.0, "non_completion": 4.0, "leakage": 12.0}
            },
            {
                "datetime": datetime(2024, 11, 20, 14, 0, tzinfo=timezone.utc),
                "date": date(2024, 11, 20),
                "status": "In Progress",
                "sanctioned": Decimal("1500000.00"),
                "released": Decimal("1500000.00"),
                "spent": Decimal("1300000.00"),
                "physical_pct": Decimal("85.00"),
                "financial_pct": Decimal("86.67"),
                "days_delayed": 4,
                "milestone": "Equipment Installation",
                "overall_risk": Decimal("20.50"),
                "risk_level": "Low",
                "summary": "RO membrane filters, UV stages, and solar backup system installed.",
                "detectors": {
                    "cost_anomaly": {"score": 10.0, "severity": "low", "reason": "Procurement fully documented."},
                    "duplicate_detection": {"score": 0.0, "severity": "low", "reason": "Verified."},
                    "delay_detection": {"score": 6.0, "severity": "low", "reason": "4-day power connection delay."},
                    "fund_utilization": {"score": 15.0, "severity": "low", "reason": "Second tranche utilized effectively."},
                    "progress_mismatch": {"score": 5.0, "severity": "low", "reason": "Equilibrium between physical and financial stages."},
                    "agency_pattern": {"score": 12.0, "severity": "low", "reason": "Satisfactory agency delivery."}
                },
                "sub_scores": {"delay": 6.0, "cost": 10.0, "non_completion": 5.0, "leakage": 15.0}
            },
            {
                "datetime": datetime(2025, 1, 15, 10, 30, tzinfo=timezone.utc),
                "date": date(2025, 1, 15),
                "status": "Completed",
                "sanctioned": Decimal("1500000.00"),
                "released": Decimal("1500000.00"),
                "spent": Decimal("1450000.00"),
                "physical_pct": Decimal("100.00"),
                "financial_pct": Decimal("96.67"),
                "days_delayed": 0,
                "milestone": "Final Handover",
                "overall_risk": Decimal("22.60"),
                "risk_level": "Low",
                "summary": "Water quality potability certified by district lab; commissioned for public use.",
                "detectors": {
                    "cost_anomaly": {"score": 12.0, "severity": "low", "reason": "Minor savings under sanctioned budget."},
                    "duplicate_detection": {"score": 0.0, "severity": "low", "reason": "Unique facility registered on portal."},
                    "delay_detection": {"score": 0.0, "severity": "low", "reason": "Delivered within overall approved window."},
                    "fund_utilization": {"score": 10.0, "severity": "low", "reason": "96.7% fund absorption."},
                    "progress_mismatch": {"score": 2.0, "severity": "low", "reason": "100% complete."},
                    "agency_pattern": {"score": 12.0, "severity": "low", "reason": "Successful completion logged."}
                },
                "sub_scores": {"delay": 0.0, "cost": 12.0, "non_completion": 2.0, "leakage": 10.0}
            }
        ]

        for item in snapshots_data_p1:
            snap = ProjectSnapshot(
                project_id="MPLADS-2024-0001",
                snapshot_datetime=item["datetime"],
                snapshot_date=item["date"],
                project_status=item["status"],
                recommended_amount=Decimal("1500000.00"),
                sanctioned_amount=item["sanctioned"],
                released_amount=item["released"],
                expenditure_amount=item["spent"],
                unspent_balance=item["released"] - item["spent"],
                utilization_rate_pct=round((item["spent"] / item["sanctioned"] * 100), 2) if item["sanctioned"] > 0 else Decimal("0.00"),
                cost_overrun_amount=Decimal("0.00"),
                physical_progress_pct=item["physical_pct"],
                financial_progress_pct=item["financial_pct"],
                days_delayed=item["days_delayed"],
                milestone_status=item["milestone"],
                cost_deviation=Decimal("0.00"),
                progress_gap=item["financial_pct"] - item["physical_pct"],
                overall_risk_score=item["overall_risk"],
                risk_level=item["risk_level"],
                change_summary=item["summary"],
                created_at=item["datetime"]
            )
            db.add(snap)
            db.flush()

            rh = RiskHistory(
                project_id="MPLADS-2024-0001",
                snapshot_id=snap.snapshot_id,
                overall_risk_score=item["overall_risk"],
                risk_level=item["risk_level"],
                delay_risk_score=Decimal(str(item["sub_scores"]["delay"])),
                cost_overrun_risk_score=Decimal(str(item["sub_scores"]["cost"])),
                non_completion_risk_score=Decimal(str(item["sub_scores"]["non_completion"])),
                leakage_risk_score=Decimal(str(item["sub_scores"]["leakage"])),
                detector_scores=item["detectors"],
                weights_used={
                    "cost_anomaly": 0.20,
                    "duplicate_detection": 0.20,
                    "delay_detection": 0.20,
                    "progress_mismatch": 0.20,
                    "agency_pattern": 0.20
                },
                calculated_at=item["datetime"],
                created_at=item["datetime"]
            )
            db.add(rh)
        print("Seeded 4 chronological snapshots for MPLADS-2024-0001.")

    db.commit()
    db.close()
    print("Historical tracking seed completed successfully!")


if __name__ == "__main__":
    seed_project_history()
