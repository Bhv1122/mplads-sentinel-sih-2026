"""
backend/app/services/risk/risk_runner.py
=============================================================================
Orchestrator for Independent Risk Detectors in Phase 6.
=============================================================================

Executes all five modular risk detectors for a given project:
1. Cost Anomaly Detector (statistical peer comparison)
2. Delay Detector (calendar slippage analysis)
3. Fund Utilization Detector (budget variance and absorption anomalies)
4. Progress Mismatch Detector (financial vs physical delivery gap)
5. Duplicate Detector (semantic text duplication analysis)

Architecture Guarantee:
- Each detector runs in complete isolation with defensive error interception.
- A failure in one detector NEVER crashes the runner or other detectors.
- Standardized output dictionary without premature risk score aggregation (Phase 7).
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy import select
from sqlalchemy.orm import Session

try:
    from app.models.project import Project
    from app.services.risk.base import BaseRiskDetector, RiskDetectorResult
    from app.services.risk.cost_anomaly import CostAnomalyDetector
    from app.services.risk.delay_detector import DelayDetector
    from app.services.risk.fund_utilization import FundUtilizationDetector
    from app.services.risk.progress_mismatch import ProgressMismatchDetector
    from app.services.risk.duplicate_detection import DuplicateDetector
except ImportError:
    from backend.app.models.project import Project
    from backend.app.services.risk.base import BaseRiskDetector, RiskDetectorResult
    from backend.app.services.risk.cost_anomaly import CostAnomalyDetector
    from backend.app.services.risk.delay_detector import DelayDetector
    from backend.app.services.risk.fund_utilization import FundUtilizationDetector
    from backend.app.services.risk.progress_mismatch import ProgressMismatchDetector
    from backend.app.services.risk.duplicate_detection import DuplicateDetector

logger = logging.getLogger(__name__)


class RiskRunner:
    """
    Coordinates execution of all independent Phase 6 risk detectors for a project.
    """

    def __init__(
        self,
        cost_anomaly_detector: Optional[BaseRiskDetector] = None,
        delay_detector: Optional[BaseRiskDetector] = None,
        fund_utilization_detector: Optional[BaseRiskDetector] = None,
        progress_mismatch_detector: Optional[BaseRiskDetector] = None,
        duplicate_detector: Optional[BaseRiskDetector] = None
    ):
        self.detectors: Dict[str, BaseRiskDetector] = {
            "cost_anomaly": cost_anomaly_detector or CostAnomalyDetector(),
            "delay": delay_detector or DelayDetector(),
            "fund_utilization": fund_utilization_detector or FundUtilizationDetector(),
            "progress_mismatch": progress_mismatch_detector or ProgressMismatchDetector(),
            "duplicate_detection": duplicate_detector or DuplicateDetector(),
        }

    def run(
        self,
        project_id: str,
        db: Session,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes all registered detectors for the specified project.

        Args:
            project_id: Project identifier to evaluate.
            db: Active SQLAlchemy database session.
            context: Optional runtime parameters (e.g. as_of_date).

        Returns:
            Dictionary with project_id and individual detector outputs.
        """
        detector_outputs: Dict[str, Dict[str, Any]] = {}

        for detector_key, detector in self.detectors.items():
            try:
                result: RiskDetectorResult = detector.detect(
                    project_id=project_id,
                    db=db,
                    context=context
                )
                detector_outputs[detector_key] = result.to_dict()
            except Exception as e:
                logger.error(
                    "Unhandled exception in detector '%s' for project '%s': %s",
                    detector_key, project_id, str(e), exc_info=True
                )
                detector_outputs[detector_key] = {
                    "score": 0,
                    "reason": f"Detector execution failed: {str(e)}",
                    "severity": "low",
                    "details": {"error": str(e), "detector": detector_key}
                }

        return {
            "project_id": project_id,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "detectors": detector_outputs
        }

    def run_batch(
        self,
        db: Session,
        project_ids: Optional[List[str]] = None,
        limit: int = 50,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes risk detection for multiple projects in batch mode.
        """
        if project_ids is None:
            stmt = select(Project.project_id).order_by(Project.recommendation_date.desc()).limit(limit)
            project_ids = [str(r[0]) for r in db.execute(stmt).all()]

        results = []
        for pid in project_ids:
            res = self.run(project_id=pid, db=db, context=context)
            results.append(res)

        return results
