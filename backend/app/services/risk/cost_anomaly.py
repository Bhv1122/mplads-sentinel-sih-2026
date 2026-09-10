"""
backend/app/services/risk/cost_anomaly.py
=============================================================================
Cost Anomaly Risk Detector for MPLADS Projects.
=============================================================================

Compares a project's cost against peer projects using non-parametric robust
statistics (Median, Q1, Q3, IQR, and Percentile Rank). Does NOT use machine learning.

Determines peer groups using:
1. Primary: Sector + State (closest developmental & geographic peers)
2. Fallback: Sector nationwide (if State-level peer group < MIN_PEERS)

Safeguards:
- Handles missing or zero cost fields cleanly.
- If peer group size < MIN_PEERS, returns a neutral/low-confidence score (0).
- Distinguishes high raw budget from statistical anomalies within peer class.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

try:
    from app.models.project import Project, Financial
    from app.services.risk.base import BaseRiskDetector, RiskDetectorResult, score_to_severity
except ImportError:
    from backend.app.models.project import Project, Financial
    from backend.app.services.risk.base import BaseRiskDetector, RiskDetectorResult, score_to_severity

logger = logging.getLogger(__name__)

MIN_PEERS_REQUIRED = 3


class CostAnomalyDetector(BaseRiskDetector):
    """
    Detects abnormal project cost inflations relative to statistically similar peers.
    """
    name: str = "cost_anomaly"
    version: str = "1.0.0"

    def detect(
        self,
        project_id: str,
        db: Session,
        context: Optional[Dict[str, Any]] = None
    ) -> RiskDetectorResult:
        """
        Calculates cost anomaly score for a given project.
        """
        try:
            # 1. Fetch target project and financial record
            project_stmt = (
                select(Project, Financial)
                .outerjoin(Financial, Project.project_id == Financial.project_id)
                .where(Project.project_id == project_id)
            )
            row = db.execute(project_stmt).first()
            if not row:
                return RiskDetectorResult(
                    score=0,
                    reason=f"Project '{project_id}' not found in database.",
                    severity="low",
                    details={"error": "not_found", "project_id": project_id}
                )

            target_project, target_financial = row

            # Determine cost to evaluate (prefer sanctioned, then recommended, then expenditure)
            project_cost = 0.0
            if target_financial:
                if target_financial.sanctioned_amount and float(target_financial.sanctioned_amount) > 0:
                    project_cost = float(target_financial.sanctioned_amount)
                elif target_financial.recommended_amount and float(target_financial.recommended_amount) > 0:
                    project_cost = float(target_financial.recommended_amount)
                elif target_financial.expenditure_amount and float(target_financial.expenditure_amount) > 0:
                    project_cost = float(target_financial.expenditure_amount)

            if project_cost <= 0.0:
                return RiskDetectorResult(
                    score=0,
                    reason="Project cost is zero or not recorded; anomaly score not applicable.",
                    severity="low",
                    details={
                        "project_cost": 0.0,
                        "project_id": project_id,
                        "peer_count": 0
                    }
                )

            # 2. Gather peer costs
            sector = target_project.sector
            state_id = target_project.state_id

            peer_costs, peer_scope = self._get_peer_costs(
                db=db,
                sector=sector,
                state_id=state_id,
                current_project_id=project_id
            )

            # Include target project's cost in distribution to compute percentiles reliably
            all_costs = peer_costs + [project_cost]

            if len(all_costs) < MIN_PEERS_REQUIRED:
                return RiskDetectorResult(
                    score=0,
                    reason=(
                        f"Insufficient peer data for sector '{sector}' "
                        f"(found {len(peer_costs)} peers; minimum {MIN_PEERS_REQUIRED} required). "
                        "Neutral score assigned."
                    ),
                    severity="low",
                    details={
                        "project_cost": round(project_cost, 2),
                        "peer_count": len(peer_costs),
                        "insufficient_peers": True,
                        "peer_scope": peer_scope
                    }
                )

            # 3. Calculate robust statistical metrics
            arr = np.array(all_costs, dtype=float)
            peer_arr = np.array(peer_costs, dtype=float) if peer_costs else arr

            peer_median = float(np.median(peer_arr))
            q1 = float(np.percentile(peer_arr, 25))
            q3 = float(np.percentile(peer_arr, 75))
            iqr = max(1.0, q3 - q1)

            # Percentile rank of target project within the peer group
            percentile = float(np.mean(peer_arr <= project_cost) * 100.0)

            # Ratio to peer median
            ratio = project_cost / peer_median if peer_median > 0 else 1.0

            # 4. Statistical Anomaly Scoring
            # - Ratio <= 1.15: normal (0-20 score)
            # - Ratio 1.15 - 1.5: mild elevation (20-45 score)
            # - Ratio 1.5 - 2.0: notable anomaly (45-75 score)
            # - Ratio > 2.0 or > Q3 + 1.5*IQR: severe anomaly (75-100 score)
            score = self._calculate_anomaly_score(
                project_cost=project_cost,
                peer_median=peer_median,
                ratio=ratio,
                q3=q3,
                iqr=iqr,
                percentile=percentile
            )

            severity = score_to_severity(score)

            # Formulate human-readable reason
            if ratio >= 2.0:
                reason = (
                    f"Project cost is {ratio:.1f}× the peer median "
                    f"({int(percentile)}th percentile for sector '{sector}')"
                )
            elif ratio >= 1.4:
                reason = (
                    f"Project cost is {ratio:.1f}× peer median "
                    f"(exceeds 75th percentile + IQR for sector '{sector}')"
                )
            elif ratio < 0.35:
                reason = (
                    f"Project cost is unusually low ({ratio:.2f}× peer median; "
                    f"{int(percentile)}th percentile)"
                )
            else:
                reason = (
                    f"Project cost is in line with peer group norms "
                    f"({ratio:.2f}× peer median in sector '{sector}')"
                )

            return RiskDetectorResult(
                score=score,
                reason=reason,
                severity=severity,
                details={
                    "project_cost": round(project_cost, 2),
                    "peer_median": round(peer_median, 2),
                    "ratio": round(ratio, 2),
                    "percentile": round(percentile, 1),
                    "q1": round(q1, 2),
                    "q3": round(q3, 2),
                    "iqr": round(iqr, 2),
                    "peer_count": len(peer_costs),
                    "peer_scope": peer_scope,
                    "sector": sector
                }
            )

        except Exception as e:
            logger.error("CostAnomalyDetector error for project %s: %s", project_id, str(e), exc_info=True)
            return RiskDetectorResult(
                score=0,
                reason=f"Unable to calculate cost anomaly due to internal error: {str(e)}",
                severity="low",
                details={"error": str(e), "project_id": project_id}
            )

    def _get_peer_costs(
        self,
        db: Session,
        sector: str,
        state_id: Optional[int],
        current_project_id: str
    ) -> Tuple[List[float], str]:
        """
        Queries peer costs using hierarchical matching.
        """
        # Level 1: Same sector and state
        if state_id is not None and sector:
            state_stmt = (
                select(Financial.sanctioned_amount, Financial.recommended_amount)
                .join(Project, Project.project_id == Financial.project_id)
                .where(
                    and_(
                        Project.sector == sector,
                        Project.state_id == state_id,
                        Project.project_id != current_project_id
                    )
                )
            )
            rows = db.execute(state_stmt).all()
            costs = [
                float(r[0] if r[0] is not None and float(r[0]) > 0 else (r[1] or 0))
                for r in rows
                if (r[0] is not None and float(r[0]) > 0) or (r[1] is not None and float(r[1]) > 0)
            ]
            if len(costs) >= MIN_PEERS_REQUIRED:
                return costs, "state_sector"

        # Level 2: Nationwide same sector
        if sector:
            nation_stmt = (
                select(Financial.sanctioned_amount, Financial.recommended_amount)
                .join(Project, Project.project_id == Financial.project_id)
                .where(
                    and_(
                        Project.sector == sector,
                        Project.project_id != current_project_id
                    )
                )
            )
            rows = db.execute(nation_stmt).all()
            costs = [
                float(r[0] if r[0] is not None and float(r[0]) > 0 else (r[1] or 0))
                for r in rows
                if (r[0] is not None and float(r[0]) > 0) or (r[1] is not None and float(r[1]) > 0)
            ]
            if len(costs) >= MIN_PEERS_REQUIRED:
                return costs, "nationwide_sector"

        # Level 3: All projects nationwide fallback
        all_stmt = (
            select(Financial.sanctioned_amount, Financial.recommended_amount)
            .join(Project, Project.project_id == Financial.project_id)
            .where(Project.project_id != current_project_id)
        )
        rows = db.execute(all_stmt).all()
        costs = [
            float(r[0] if r[0] is not None and float(r[0]) > 0 else (r[1] or 0))
            for r in rows
            if (r[0] is not None and float(r[0]) > 0) or (r[1] is not None and float(r[1]) > 0)
        ]
        return costs, "nationwide_general"

    def _calculate_anomaly_score(
        self,
        project_cost: float,
        peer_median: float,
        ratio: float,
        q3: float,
        iqr: float,
        percentile: float
    ) -> int:
        """
        Combines median ratio, Tukey IQR fence, and percentile rank into 0-100 score.
        """
        if ratio <= 1.05 and project_cost <= q3:
            # Below or around median: safe
            return max(0, int(round((ratio - 0.5) * 20))) if ratio > 0.5 else 0

        # Tukey upper fence: Q3 + 1.5 * IQR
        upper_fence = q3 + (1.5 * iqr)
        extreme_fence = q3 + (3.0 * iqr)

        if project_cost >= extreme_fence or ratio >= 3.0:
            score = 85 + min(15, int((ratio - 3.0) * 10) + int((percentile - 95) * 3))
        elif project_cost >= upper_fence or ratio >= 2.0:
            # Notable outlier
            score = 70 + min(15, int((ratio - 2.0) * 15))
        elif ratio >= 1.4:
            # Mild elevation
            score = 40 + min(25, int((ratio - 1.4) * 50))
        elif ratio > 1.05:
            score = 15 + min(25, int((ratio - 1.05) * 70))
        else:
            score = 0

        return max(0, min(100, score))
