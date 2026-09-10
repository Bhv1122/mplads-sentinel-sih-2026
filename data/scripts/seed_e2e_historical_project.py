"""
data/scripts/seed_e2e_historical_project.py
=============================================================================
Seeds a dedicated representative project (MPLADS-2024-E2E-01) with full
historical trajectory across 6 chronological snapshots into PostgreSQL.
=============================================================================
"""

import os
import sys
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal

# Ensure backend is in python path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.database import SessionLocal, engine
from app.models.project import (
    Project, Financial, Progress, RiskScore, RiskFactor,
    ProjectSnapshot, RiskHistory
)



def seed_representative_e2e_project():
    db = SessionLocal()
    pid = "MPLADS-2024-E2E-01"
    print(f"Seeding representative project '{pid}'...")

    # Clean up existing records
    existing = db.get(Project, pid)
    if existing:
        db.delete(existing)
        db.commit()

    # 1. Project Master Record
    proj = Project(
        project_id=pid,
        project_code="MPLADS-E2E-REPR-01",
        project_title="Integrated Skill & Innovation Center",
        project_description="High-capacity modern vocational skilling and digital innovation hub.",
        sector="Skill Development",
        sub_sector="Vocational Training",
        state_id=31,  # Uttar Pradesh
        constituency_id=484,  # Sambhal
        district_name="Sambhal District",
        block_name="Asmoli",
        implementing_agency="District Rural Development Agency (DRDA)",
        mp_name="Hon MP of Sambhal (Lok Sabha)",
        house_of_parliament="Lok Sabha",
        current_status="In Progress",
        financial_year="2024-25",
        recommendation_date=date(2024, 1, 15),
        sanction_date=date(2024, 2, 1),
        work_order_date=date(2024, 3, 1),
        expected_completion_date=date(2025, 3, 1)
    )
    db.add(proj)
    db.flush()

    # 2. Financial Record (reflects latest #6)
    fin = Financial(
        project_id=pid,
        currency="INR",
        recommended_amount=Decimal("3000000.00"),
        sanctioned_amount=Decimal("3000000.00"),
        released_amount=Decimal("3000000.00"),
        expenditure_amount=Decimal("3500000.00"),  # Overrun
        utilization_rate_pct=Decimal("100.00"),
        cost_overrun_amount=Decimal("500000.00"),
        cost_overrun_pct=Decimal("16.67")
    )
    db.add(fin)


    # 3. Progress Record (reflects latest #6)
    prog = Progress(
        project_id=pid,
        reported_date=date(2026, 9, 10),
        physical_progress_pct=Decimal("55.00"),
        financial_progress_pct=Decimal("100.00"),
        current_stage="Structure",
        days_delayed=400,
        milestone_status="Critical"
    )
    db.add(prog)

    # 4. Current RiskScore (reflects latest #6)
    r_score = RiskScore(
        project_id=pid,
        overall_risk_score=Decimal("78.50"),
        risk_level="Critical",
        delay_risk_score=Decimal("85.00"),
        cost_overrun_risk_score=Decimal("70.00"),
        non_completion_risk_score=Decimal("65.00"),
        leakage_risk_score=Decimal("20.00"),
        confidence_score=Decimal("0.85"),
        assessment_date=date(2026, 9, 10)
    )
    db.add(r_score)
    db.flush()



    # 5. Snapshots & Risk History sequence (6 snapshots)
    milestones = [
        {
            "snap_date": date(2024, 8, 1),
            "status": "Sanctioned",
            "sanctioned": Decimal("3000000.00"),
            "released": Decimal("1500000.00"),
            "expenditure": Decimal("150000.00"),
            "physical": Decimal("5.00"),
            "financial": Decimal("5.00"),
            "days_delayed": 0,
            "milestone_status": "On Track",
            "overall_score": Decimal("18.00"),
            "risk_level": "Low",
            "summary": "Initial baseline project snapshot recorded upon first ingestion.",
            "detectors": {
                "cost_anomaly": {"score": 5.0, "risk_level": "LOW", "reason": "Expenditure well within benchmark."},
                "delay_detection": {"score": 0.0, "risk_level": "LOW", "reason": "Work commenced on schedule."},
                "progress_mismatch": {"score": 0.0, "risk_level": "LOW", "reason": "Execution balanced."},
                "fund_utilization": {"score": 10.0, "risk_level": "LOW", "reason": "Initial mobilization advance disbursed."},
                "duplicate_detection": {"score": 0.0, "risk_level": "LOW", "reason": "No duplicate found."},
                "agency_pattern": {"score": 14.0, "risk_level": "LOW", "reason": "DRDA historical compliance satisfactory."}
            }
        },
        {
            "snap_date": date(2024, 10, 15),
            "status": "In Progress",
            "sanctioned": Decimal("3000000.00"),
            "released": Decimal("1500000.00"),
            "expenditure": Decimal("1000000.00"),
            "physical": Decimal("15.00"),
            "financial": Decimal("33.33"),
            "days_delayed": 0,
            "milestone_status": "On Track",
            "overall_score": Decimal("27.50"),
            "risk_level": "Low",
            "summary": "Expenditure increased from ₹1.5L to ₹10L (+₹8.5L). Physical progress advanced to 15%.",
            "detectors": {
                "cost_anomaly": {"score": 15.0, "risk_level": "LOW", "reason": "Expenditure consistent with procurement."},
                "delay_detection": {"score": 0.0, "risk_level": "LOW", "reason": "Foundation work on track."},
                "progress_mismatch": {"score": 18.0, "risk_level": "LOW", "reason": "Financial advance ahead of physical measurement."},
                "fund_utilization": {"score": 25.0, "risk_level": "LOW", "reason": "66.7% of released funds disbursed."},
                "duplicate_detection": {"score": 0.0, "risk_level": "LOW", "reason": "No duplicate found."},
                "agency_pattern": {"score": 14.0, "risk_level": "LOW", "reason": "Agency tracking normal."}
            }
        },
        {
            "snap_date": date(2024, 12, 28),
            "status": "In Progress",
            "sanctioned": Decimal("3000000.00"),
            "released": Decimal("2000000.00"),
            "expenditure": Decimal("1400000.00"),
            "physical": Decimal("40.00"),
            "financial": Decimal("46.67"),
            "days_delayed": 0,
            "milestone_status": "On Track",
            "overall_score": Decimal("39.00"),
            "risk_level": "Moderate",
            "summary": "Physical progress jumped to 40% following plinth verification. Second tranche received.",
            "detectors": {
                "cost_anomaly": {"score": 25.0, "risk_level": "LOW", "reason": "Material costs slightly elevated."},
                "delay_detection": {"score": 20.0, "risk_level": "LOW", "reason": "Minor weather slowdown."},
                "progress_mismatch": {"score": 12.0, "risk_level": "LOW", "reason": "Physical and financial pace converged."},
                "fund_utilization": {"score": 28.0, "risk_level": "LOW", "reason": "Good burn rate."},
                "duplicate_detection": {"score": 0.0, "risk_level": "LOW", "reason": "No duplicate found."},
                "agency_pattern": {"score": 18.0, "risk_level": "LOW", "reason": "DRDA cluster capacity moderate."}
            }
        },
        {
            "snap_date": date(2025, 3, 20),
            "status": "In Progress",
            "sanctioned": Decimal("3000000.00"),
            "released": Decimal("2800000.00"),
            "expenditure": Decimal("2200000.00"),
            "physical": Decimal("45.00"),
            "financial": Decimal("73.33"),
            "days_delayed": 20,
            "milestone_status": "On Track",
            "overall_score": Decimal("48.50"),
            "risk_level": "Moderate",
            "summary": "Financial progress reached 73.3% while physical progress lagged at 45.0% (gap +28.3%). Target date passed.",
            "detectors": {
                "cost_anomaly": {"score": 35.0, "risk_level": "MEDIUM", "reason": "High expenditure pace."},
                "delay_detection": {"score": 38.0, "risk_level": "MEDIUM", "reason": "Target completion date (2025-03-01) elapsed by 20 days."},
                "progress_mismatch": {"score": 48.0, "risk_level": "MEDIUM", "reason": "Significant progress gap (+28.3%)."},
                "fund_utilization": {"score": 30.0, "risk_level": "LOW", "reason": "Normal utilization."},
                "duplicate_detection": {"score": 0.0, "risk_level": "LOW", "reason": "No duplicate found."},
                "agency_pattern": {"score": 22.0, "risk_level": "LOW", "reason": "Agency handling multiple concurrent schemes."}
            }
        },
        {
            "snap_date": date(2025, 6, 10),
            "status": "In Progress",
            "sanctioned": Decimal("3000000.00"),
            "released": Decimal("3000000.00"),
            "expenditure": Decimal("2700000.00"),
            "physical": Decimal("50.00"),
            "financial": Decimal("90.00"),
            "days_delayed": 101,
            "milestone_status": "Delayed",
            "overall_score": Decimal("62.00"),
            "risk_level": "High",
            "summary": "Milestone status escalated to Delayed. Schedule overdue by 101 days. Physical progress sluggish at 50%.",
            "detectors": {
                "cost_anomaly": {"score": 42.0, "risk_level": "MEDIUM", "reason": "Approaching full sanction limit without completion."},
                "delay_detection": {"score": 65.0, "risk_level": "HIGH", "reason": "Contractor past deadline by >100 days."},
                "progress_mismatch": {"score": 62.0, "risk_level": "HIGH", "reason": "Acute mismatch: 90% funds drawn vs 50% physical completion."},
                "fund_utilization": {"score": 35.0, "risk_level": "MEDIUM", "reason": "High fund depletion."},
                "duplicate_detection": {"score": 0.0, "risk_level": "LOW", "reason": "No duplicate found."},
                "agency_pattern": {"score": 28.0, "risk_level": "LOW", "reason": "Agency delay index elevated."}
            }
        },
        {
            "snap_date": date(2026, 9, 10),
            "status": "In Progress",
            "sanctioned": Decimal("3000000.00"),
            "released": Decimal("3000000.00"),
            "expenditure": Decimal("3500000.00"),
            "physical": Decimal("55.00"),
            "financial": Decimal("100.00"),
            "days_delayed": 400,
            "milestone_status": "Critical",
            "overall_score": Decimal("78.50"),
            "risk_level": "Critical",
            "summary": "Critical escalation: 400 days overdue, ₹5,00,000 cost overrun beyond sanctioned budget, acute progress divergence.",
            "detectors": {
                "cost_anomaly": {"score": 68.0, "risk_level": "HIGH", "reason": "Expenditure exceeded sanctioned budget by 16.7%."},
                "delay_detection": {"score": 88.0, "risk_level": "CRITICAL", "reason": "400 days schedule slippage beyond contractual deadline."},
                "progress_mismatch": {"score": 75.0, "risk_level": "CRITICAL", "reason": "Complete financial exhaustion (100%) against only 55% structure."},
                "fund_utilization": {"score": 40.0, "risk_level": "MEDIUM", "reason": "Full funds exhausted."},
                "duplicate_detection": {"score": 0.0, "risk_level": "LOW", "reason": "No duplicate found."},
                "agency_pattern": {"score": 34.0, "risk_level": "MEDIUM", "reason": "Contractor inaction notice issued."}
            }
        }
    ]

    for idx, m in enumerate(milestones, start=1):
        dt = datetime.combine(m["snap_date"], datetime.min.time(), tzinfo=timezone.utc)
        snap = ProjectSnapshot(
            project_id=pid,
            snapshot_datetime=dt,
            snapshot_date=m["snap_date"],
            project_status=m["status"],
            recommended_amount=Decimal("3000000.00"),
            sanctioned_amount=m["sanctioned"],
            released_amount=m["released"],
            expenditure_amount=m["expenditure"],
            unspent_balance=max(Decimal("0.00"), m["released"] - m["expenditure"]),
            utilization_rate_pct=min(Decimal("100.00"), round((m["expenditure"] / m["released"]) * Decimal("100.0"), 2)),
            cost_overrun_amount=max(Decimal("0.00"), m["expenditure"] - m["sanctioned"]),
            physical_progress_pct=m["physical"],
            financial_progress_pct=m["financial"],
            expected_completion_date=date(2025, 3, 1),
            days_delayed=m["days_delayed"],
            milestone_status=m["milestone_status"],
            overall_risk_score=m["overall_score"],
            risk_level=m["risk_level"],
            change_summary=m["summary"]
        )
        db.add(snap)
        db.flush()

        rh = RiskHistory(
            project_id=pid,
            snapshot_id=snap.snapshot_id,
            overall_risk_score=m["overall_score"],
            risk_level=m["risk_level"],
            delay_risk_score=Decimal(str(m["detectors"]["delay_detection"]["score"])),
            cost_overrun_risk_score=Decimal(str(m["detectors"]["cost_anomaly"]["score"])),
            non_completion_risk_score=Decimal(str(m["detectors"]["progress_mismatch"]["score"])),
            leakage_risk_score=Decimal(str(m["detectors"]["fund_utilization"]["score"])),
            detector_scores=m["detectors"],
            calculated_at=dt
        )
        db.add(rh)

    db.commit()
    print(f"Successfully seeded {len(milestones)} historical snapshots for '{pid}'!")
    db.close()


if __name__ == "__main__":
    seed_representative_e2e_project()
