"""
backend/app/services/risk/cost_anomaly_engine.py
=============================================================================
Engine 1: Cost Anomaly Detection Engine for MPLADS Projects.
=============================================================================

Implements the common BaseRiskEngine interface contract:
{
    "engine": "cost_anomaly",
    "score": 0-100,
    "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
    "reason": "...",
    "details": {},
    "confidence": 0-1
}

Methodology & Statistical Rigor:
1. Multi-tier Peer Group Matching:
   - Primary: Sector + State (closest geographic and developmental peers)
   - Fallback: Sector Nationwide (if state peers < MIN_PEERS)
   - Fallback protection: If nationwide peers < MIN_PEERS, returns neutral score (0)
     with small_peer_group flag and low confidence.
2. Robust Non-Parametric Statistics:
   - Peer Median (M)
   - Interquartile Range (IQR = Q3 - Q1)
   - Percentile Rank (empirical CDF position)
   - Median Absolute Deviation (MAD = median(|x_i - M|))
   - Modified Robust Z-score: 0.6745 * (x - M) / max(MAD, 1.0)
   - Deviation percentage: (x - M) / M * 100
3. Legitimacy Dampener:
   - Does NOT automatically flag legitimately expensive projects as fraudulent.
   - If a project has high expenditure but was officially sanctioned for that amount
     (cost_overrun <= 0 and expenditure <= sanctioned), the anomaly score is dampened
     and capped within normal/moderate bounds.
4. Overrun Escalator:
   - If high cost stems from actual expenditure significantly exceeding sanctioned budget
     (cost overrun > 15%), the risk score is escalated.
5. Dual-Sided Anomaly Detection:
   - Flags unusually cheap / token expenditures (< 15% of peer median) as potential
     under-reporting or ghost project risks.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

try:
    from app.config import settings
    from app.models.project import Project, Financial, ProjectFeature
    from app.schemas.risk_engine import RiskLevel, EngineResult
    from app.services.risk.engine_base import BaseRiskEngine
except ImportError:
    from backend.app.config import settings
    from backend.app.models.project import Project, Financial, ProjectFeature
    from backend.app.schemas.risk_engine import RiskLevel, EngineResult
    from backend.app.services.risk.engine_base import BaseRiskEngine

logger = logging.getLogger(__name__)


class CostAnomalyEngine(BaseRiskEngine):
    """
    Independent risk engine for detecting abnormal project cost variations
    relative to statistically comparable peer works.
    """
    engine_name: str = "cost_anomaly"
    version: str = "1.0.0"

    def __init__(self, min_peers: Optional[int] = None):
        """
        Initializes the cost anomaly engine with configurable peer thresholds.
        """
        thresholds = self.get_engine_thresholds()
        self.min_peers: int = min_peers if min_peers is not None else thresholds.get("min_peers", 2)

    # -------------------------------------------------------------------------
    # Public Evaluation Interface
    # -------------------------------------------------------------------------

    def evaluate(
        self,
        project_id: str,
        db: Session,
        context: Optional[Dict[str, Any]] = None
    ) -> EngineResult:
        """
        Evaluates project cost against genuine peer works and returns standardized EngineResult.
        """
        try:
            # 1. Fetch target project and related records
            stmt = (
                select(Project, Financial, ProjectFeature)
                .outerjoin(Financial, Project.project_id == Financial.project_id)
                .outerjoin(ProjectFeature, Project.project_id == ProjectFeature.project_id)
                .where(Project.project_id == project_id)
            )
            row = db.execute(stmt).first()

            if not row or not row[0]:
                return self.build_result(
                    score=0,
                    reason=f"Project '{project_id}' not found in database.",
                    details={"error": "not_found", "project_id": project_id},
                    confidence=0.0
                )

            target_project, target_financial, target_features = row

            # 2. Extract cost signals safely (using financials, features, and project metadata)
            cost_info = self._extract_cost_signals(target_financial, target_features, target_project)
            project_cost = cost_info["evaluated_cost"]
            sanctioned = cost_info["sanctioned_amount"]
            released = cost_info["released_amount"]
            expenditure = cost_info["expenditure_amount"]
            cost_overrun_pct = cost_info["cost_overrun_pct"]

            # Handle missing or zero cost data
            if project_cost <= 0.0:
                return self.build_result(
                    score=0,
                    reason="Project cost (expenditure/sanctioned) is zero or missing; cost anomaly cannot be assessed.",
                    details={
                        "project_id": project_id,
                        "project_expenditure": 0.0,
                        "sanctioned_amount": sanctioned,
                        "released_amount": released,
                        "peer_median": None,
                        "deviation_percentage": None,
                        "percentile": None,
                        "peer_group_size": 0,
                        "missing_cost": True,
                        "anomaly_type": "MISSING_COST",
                        "sector": target_project.sector,
                    },
                    confidence=0.0
                )

            # 3. Hierarchical peer group matching
            sector = target_project.sector or "Unknown"
            state_id = target_project.state_id
            district_name = getattr(target_project, "district_name", None)

            peer_costs, peer_scope = self._get_peer_costs(
                db=db,
                sector=sector,
                state_id=state_id,
                current_project_id=project_id,
                district_name=district_name,
            )

            # Check for small peer group
            if len(peer_costs) < self.min_peers:
                peer_median = round(float(np.median(peer_costs)), 2) if peer_costs else None
                deviation_pct = (
                    round(float((project_cost - peer_median) / peer_median * 100), 2)
                    if (peer_costs and peer_median and peer_median > 0)
                    else None
                )
                percentile = (
                    round(float(np.mean(np.array(peer_costs) <= project_cost) * 100), 1)
                    if peer_costs
                    else None
                )
                return self.build_result(
                    score=0,
                    reason=(
                        f"Insufficient peer data for sector '{sector}' "
                        f"(found {len(peer_costs)} peers; minimum {self.min_peers} required). "
                        "Neutral score assigned."
                    ),
                    details={
                        "project_expenditure": round(expenditure, 2),
                        "sanctioned_amount": round(sanctioned, 2),
                        "released_amount": round(released, 2),
                        "peer_median": peer_median,
                        "deviation_percentage": deviation_pct,
                        "percentile": percentile,
                        "peer_group_size": len(peer_costs),
                        "peer_scope": peer_scope,
                        "small_peer_group": True,
                        "anomaly_type": "INSUFFICIENT_PEERS",
                        "sector": sector,
                    },
                    confidence=0.30
                )

            # 4. Compute robust statistical metrics
            metrics = self._calculate_robust_metrics(peer_costs, project_cost)

            # 5. Determine normalized risk score and explainability
            score, anomaly_type, reason = self._compute_score_and_reason(
                project_cost=project_cost,
                sanctioned=sanctioned,
                cost_overrun_pct=cost_overrun_pct,
                metrics=metrics,
                sector=sector,
                peer_scope=peer_scope,
                project_status=target_project.current_status,
                peer_group_size=len(peer_costs),
            )

            # 6. Calculate data confidence
            confidence = self._compute_confidence(
                target_financial=target_financial,
                target_features=target_features,
                peer_group_size=len(peer_costs),
                peer_scope=peer_scope,
            )

            details = {
                # 5 Mandatory evidence fields specified in prompt:
                "project_expenditure": round(expenditure, 2),
                "peer_median": round(metrics["peer_median"], 2),
                "deviation_percentage": round(metrics["deviation_pct"], 2),
                "percentile": round(metrics["percentile"], 1),
                "peer_group_size": len(peer_costs),

                # Contextual cost amounts & metric evaluated:
                "sanctioned_amount": round(sanctioned, 2),
                "released_amount": round(released, 2),
                "evaluated_cost": round(project_cost, 2),
                "cost_metric_used": cost_info.get("cost_metric_used", "expenditure"),

                # Robust statistical distribution evidence:
                "peer_scope": peer_scope,
                "peer_q1": round(metrics["q1"], 2),
                "peer_q3": round(metrics["q3"], 2),
                "peer_iqr": round(metrics["iqr"], 2),
                "robust_z_score": round(metrics["robust_z"], 2),
                "cost_overrun_pct": round(cost_overrun_pct, 2),

                # Duration & location evidence:
                "project_duration_days": cost_info.get("project_duration_days"),
                "cost_per_day": cost_info.get("cost_per_day"),
                "state_id": cost_info.get("state_id"),
                "district_name": cost_info.get("district_name"),

                # Engineered features evidence:
                "utilization_ratio": cost_info.get("utilization_ratio"),
                "cost_deviation": cost_info.get("cost_deviation"),
                "cost_relative_to_category": cost_info.get("cost_relative_to_category"),
                "cost_category_zscore": cost_info.get("cost_category_zscore"),

                # Categorization & classification:
                "anomaly_type": anomaly_type,
                "sector": sector,
                "sub_sector": cost_info.get("sub_sector"),
            }

            peer_med = metrics["peer_median"]
            dev_mult = round(project_cost / peer_med, 2) if peer_med > 0 else 1.0
            evidence_items = [
                {
                    "metric": "project_cost",
                    "label": "Project Cost",
                    "value": round(project_cost, 2),
                    "formatted": f"₹{project_cost:,.2f}",
                },
                {
                    "metric": "peer_median",
                    "label": "Peer Median Cost",
                    "value": round(peer_med, 2),
                    "formatted": f"₹{peer_med:,.2f}",
                },
                {
                    "metric": "deviation_multiplier",
                    "label": "Deviation Multiplier",
                    "value": dev_mult,
                    "formatted": f"{dev_mult:.2f}x",
                },
                {
                    "metric": "percentile",
                    "label": "Peer Percentile",
                    "value": round(metrics["percentile"], 1),
                    "formatted": f"{metrics['percentile']:.1f}th percentile",
                },
                {
                    "metric": "robust_z_score",
                    "label": "Robust Z-Score",
                    "value": round(metrics["robust_z"], 2),
                    "formatted": f"{metrics['robust_z']:.2f}",
                },
                {
                    "metric": "peer_iqr",
                    "label": "Peer IQR",
                    "value": round(metrics["iqr"], 2),
                    "formatted": f"₹{metrics['iqr']:,.2f}",
                },
                {
                    "metric": "cost_overrun_pct",
                    "label": "Budget Overrun",
                    "value": round(cost_overrun_pct, 1),
                    "formatted": f"{cost_overrun_pct:+.1f}%",
                },
            ]

            return self.build_result(
                score=score,
                reason=reason,
                details=details,
                confidence=confidence,
                triggered=(score >= 30),
                threshold="Robust Z >= 2.0 or expenditure > 1.35x peer median with > 15% budget overrun",
                actual_value=f"₹{project_cost:,.2f} ({metrics['deviation_pct']:+.1f}% vs peer median, {metrics['percentile']:.1f}th percentile)",
                expected_value=f"Peer Median: ₹{peer_med:,.2f} (Sanctioned: ₹{sanctioned:,.2f})",
                reference_value=f"Category benchmark IQR: ₹{metrics['iqr']:,.2f} (Q1: ₹{metrics['q1']:,.2f}, Q3: ₹{metrics['q3']:,.2f})",
                evidence=evidence_items,
                metadata=details,
            )

        except Exception as e:
            logger.error(
                "CostAnomalyEngine evaluation failed for project '%s': %s",
                project_id, str(e), exc_info=True
            )
            return self.build_result(
                score=0,
                reason=f"Cost anomaly evaluation encountered runtime error: {str(e)}",
                details={"error": str(e), "project_id": project_id},
                confidence=0.0
            )

    # -------------------------------------------------------------------------
    # Helper: Cost Signals Extraction
    # -------------------------------------------------------------------------

    def _extract_cost_signals(
        self,
        financial: Optional[Financial],
        features: Optional[ProjectFeature],
        target_project: Optional[Project] = None,
    ) -> Dict[str, Any]:
        """
        Safely extracts and standardizes cost values, location, duration, and
        engineered features from Project, Financial, and ProjectFeature.
        Does NOT assume all fields exist.
        """
        expenditure = 0.0
        sanctioned = 0.0
        released = 0.0
        cost_overrun_pct = 0.0

        if financial:
            if financial.expenditure_amount is not None:
                expenditure = max(0.0, float(financial.expenditure_amount))
            if financial.sanctioned_amount is not None:
                sanctioned = max(0.0, float(financial.sanctioned_amount))
            if financial.released_amount is not None:
                released = max(0.0, float(financial.released_amount))
            if financial.cost_overrun_pct is not None:
                cost_overrun_pct = float(financial.cost_overrun_pct)

        # Primary cost metric is actual expenditure; fall back to sanctioned or released
        if expenditure > 0.0:
            evaluated_cost = expenditure
            cost_metric_used = "expenditure"
        elif sanctioned > 0.0:
            evaluated_cost = sanctioned
            cost_metric_used = "sanctioned"
        elif released > 0.0:
            evaluated_cost = released
            cost_metric_used = "released"
        else:
            evaluated_cost = 0.0
            cost_metric_used = "none"

        # Duration extraction
        project_duration_days: Optional[int] = None
        if features and getattr(features, "project_duration_days", None) is not None and features.project_duration_days > 0:
            project_duration_days = int(features.project_duration_days)
        elif features and getattr(features, "project_duration", None) is not None and features.project_duration > 0:
            project_duration_days = int(features.project_duration)
        elif target_project:
            # Fallback calculation from project lifecycle dates
            start_date = (
                getattr(target_project, "work_order_date", None)
                or getattr(target_project, "sanction_date", None)
                or getattr(target_project, "recommendation_date", None)
            )
            end_date = (
                getattr(target_project, "actual_completion_date", None)
                or getattr(target_project, "expected_completion_date", None)
            )
            if start_date and end_date:
                try:
                    delta = (end_date - start_date).days
                    if delta > 0:
                        project_duration_days = delta
                except Exception:
                    pass

        cost_per_day: Optional[float] = None
        if project_duration_days and project_duration_days > 0 and evaluated_cost > 0:
            cost_per_day = round(evaluated_cost / project_duration_days, 2)

        # Location details
        state_id = getattr(target_project, "state_id", None) if target_project else None
        district_name = getattr(target_project, "district_name", None) if target_project else None
        sector = getattr(target_project, "sector", None) if target_project else None
        sub_sector = getattr(target_project, "sub_sector", None) if target_project else None

        # Engineered features
        cost_deviation = None
        utilization_ratio = None
        cost_relative_to_category = None
        cost_category_zscore = None

        if features:
            if getattr(features, "cost_deviation", None) is not None:
                cost_deviation = float(features.cost_deviation)
            if getattr(features, "utilization_ratio", None) is not None:
                utilization_ratio = float(features.utilization_ratio)
            if getattr(features, "cost_relative_to_category", None) is not None:
                cost_relative_to_category = float(features.cost_relative_to_category)
            if getattr(features, "cost_category_zscore", None) is not None:
                cost_category_zscore = float(features.cost_category_zscore)

        # Fallbacks for engineered features if missing in project_features
        if cost_deviation is None and (expenditure > 0 or sanctioned > 0):
            cost_deviation = round(expenditure - sanctioned, 2)
        if utilization_ratio is None and released > 0:
            utilization_ratio = round(expenditure / released, 4)

        return {
            "evaluated_cost": evaluated_cost,
            "cost_metric_used": cost_metric_used,
            "expenditure_amount": expenditure,
            "sanctioned_amount": sanctioned,
            "released_amount": released,
            "cost_overrun_pct": cost_overrun_pct,
            "project_duration_days": project_duration_days,
            "cost_per_day": cost_per_day,
            "state_id": state_id,
            "district_name": district_name,
            "sector": sector,
            "sub_sector": sub_sector,
            "cost_deviation": cost_deviation,
            "utilization_ratio": utilization_ratio,
            "cost_relative_to_category": cost_relative_to_category,
            "cost_category_zscore": cost_category_zscore,
        }

    # -------------------------------------------------------------------------
    # Helper: Hierarchical Peer Matching
    # -------------------------------------------------------------------------

    def _get_peer_costs(
        self,
        db: Session,
        sector: str,
        state_id: Optional[int],
        current_project_id: str,
        district_name: Optional[str] = None,
    ) -> Tuple[List[float], str]:
        """
        Gathers peer project costs following genuine comparable hierarchical levels:
        1. Level 1: Sector + District (most localized peers, if >= min_peers)
        2. Level 2: Sector + State (statewide peers, if >= min_peers)
        3. Level 3: Sector Nationwide (nationwide category peers, if >= min_peers)
        4. Fallback: insufficient_peers
        """
        # Level 1: Same sector + same district
        if district_name:
            stmt_dist = (
                select(Financial)
                .join(Project, Financial.project_id == Project.project_id)
                .where(
                    and_(
                        Project.sector == sector,
                        Project.district_name == district_name,
                        Project.project_id != current_project_id,
                    )
                )
            )
            dist_rows = db.execute(stmt_dist).scalars().all()
            dist_costs = [
                float(f.expenditure_amount or f.sanctioned_amount or 0.0)
                for f in dist_rows
                if (f.expenditure_amount or f.sanctioned_amount or 0.0) > 0
            ]
            if len(dist_costs) >= self.min_peers:
                return dist_costs, "sector_and_district"

        # Level 2: Same sector + same state
        if state_id is not None:
            stmt_local = (
                select(Financial)
                .join(Project, Financial.project_id == Project.project_id)
                .where(
                    and_(
                        Project.sector == sector,
                        Project.state_id == state_id,
                        Project.project_id != current_project_id,
                    )
                )
            )
            local_rows = db.execute(stmt_local).scalars().all()
            local_costs = [
                float(f.expenditure_amount or f.sanctioned_amount or 0.0)
                for f in local_rows
                if (f.expenditure_amount or f.sanctioned_amount or 0.0) > 0
            ]
            if len(local_costs) >= self.min_peers:
                return local_costs, "sector_and_state"

        # Level 3: Same sector nationwide
        stmt_national = (
            select(Financial)
            .join(Project, Financial.project_id == Project.project_id)
            .where(
                and_(
                    Project.sector == sector,
                    Project.project_id != current_project_id,
                )
            )
        )
        national_rows = db.execute(stmt_national).scalars().all()
        national_costs = [
            float(f.expenditure_amount or f.sanctioned_amount or 0.0)
            for f in national_rows
            if (f.expenditure_amount or f.sanctioned_amount or 0.0) > 0
        ]
        if len(national_costs) >= self.min_peers:
            return national_costs, "sector_nationwide"

        return national_costs, "insufficient_peers"

    # -------------------------------------------------------------------------
    # Helper: Robust Statistical Metrics
    # -------------------------------------------------------------------------

    def _calculate_robust_metrics(
        self,
        peer_costs: List[float],
        project_cost: float,
    ) -> Dict[str, float]:
        """
        Computes non-parametric robust statistics over peer distribution:
        - Median
        - Q1, Q3, and IQR
        - Percentile rank
        - Modified Robust Z-score via MAD with scale floor
        - Deviation percentage
        """
        peer_arr = np.array(peer_costs, dtype=float)
        peer_median = float(np.median(peer_arr))

        q1 = float(np.percentile(peer_arr, 25))
        q3 = float(np.percentile(peer_arr, 75))
        iqr = max(0.0, float(q3 - q1))

        # Deviation percentage from peer median
        deviation_pct = (
            ((project_cost - peer_median) / peer_median) * 100.0
            if peer_median > 0
            else 0.0
        )

        # Percentile rank within peers (0 to 100)
        percentile = float(np.mean(peer_arr <= project_cost) * 100.0)

        # Modified Robust Z-Score via Median Absolute Deviation (MAD)
        abs_deviations = np.abs(peer_arr - peer_median)
        mad = float(np.median(abs_deviations))

        # Scale floor: prevents division by zero and hyper-sensitive false positives
        # on degenerate peer distributions (e.g. peers with identical standard budgets).
        min_scale = max(peer_median * 0.05, 10000.0)
        if mad > 0:
            scale = max(mad / 0.6745, min_scale)
        elif iqr > 0:
            scale = max(iqr / 1.349, min_scale)
        else:
            scale = min_scale

        robust_z = float((project_cost - peer_median) / scale)

        return {
            "peer_median": peer_median,
            "q1": q1,
            "q3": q3,
            "iqr": iqr,
            "deviation_pct": deviation_pct,
            "percentile": percentile,
            "robust_z": robust_z,
            "mad": mad,
        }

    # -------------------------------------------------------------------------
    # Helper: Scoring & Legitimacy Protection Logic
    # -------------------------------------------------------------------------

    def _compute_score_and_reason(
        self,
        project_cost: float,
        sanctioned: float,
        cost_overrun_pct: float,
        metrics: Dict[str, float],
        sector: str,
        peer_scope: str,
        project_status: str,
        peer_group_size: int = 3,
    ) -> Tuple[float, str, str]:
        """
        Determines the normalized 0-100 risk score and human-readable explanation.

        Applies:
        - Legitimacy dampener for officially sanctioned high-budget works.
        - Escalator for unauthorized cost overruns.
        - Low-cost anomaly detection for abnormally low/token expenditure.
        - Small-sample score ceiling for small peer cohorts (< 3 peers).
        - Early-stage status dampener for projects in preliminary phases.
        """
        peer_median = metrics["peer_median"]
        q3 = metrics["q3"]
        iqr = metrics["iqr"]
        deviation_pct = metrics["deviation_pct"]
        percentile = metrics["percentile"]
        robust_z = metrics["robust_z"]

        ratio = project_cost / peer_median if peer_median > 0 else 1.0

        # Case 1: Unusually Cheap Project (Low-Cost Anomaly vs Early Stage)
        # If expenditure is < 15% of peer median (deviation < -85%)
        if ratio < 0.15:
            is_early_stage = (project_status or "").lower() in {
                "work order issued", "proposed", "sanctioned", "recommended", "approved", "pending"
            }
            if is_early_stage:
                score = 10.0
                anomaly_type = "EARLY_STAGE_EXPENDITURE"
                reason = (
                    f"Expenditure (₹{project_cost:,.0f}) is low ({ratio:.1%} of peer median ₹{peer_median:,.0f}), "
                    f"but consistent with early project phase '{project_status}'."
                )
                return score, anomaly_type, reason
            else:
                is_active_or_done = (project_status or "").lower() in {"completed", "ongoing", "in progress", "closed"}
                base_score = 45.0 if is_active_or_done else 30.0
                anomaly_type = "LOW_COST_ANOMALY"
                reason = (
                    f"Unusually low expenditure (₹{project_cost:,.0f} is only {ratio:.1%} of peer median "
                    f"₹{peer_median:,.0f}, deviation: {deviation_pct:.1f}%). "
                    f"Potential token booking, incomplete reporting, or ghost asset risk."
                )
                return base_score, anomaly_type, reason

        # --- Cost Overrun Escalator ---
        # If high cost is compounded or caused by unapproved expenditure exceeding sanction
        has_cost_overrun = cost_overrun_pct > 15.0 or (sanctioned > 0.0 and project_cost > sanctioned * 1.15)
        if has_cost_overrun:
            effective_overrun_pct = cost_overrun_pct if cost_overrun_pct > 0 else ((project_cost - sanctioned) / sanctioned * 100.0)
            if ratio > 1.35:
                # Compounded by peer outlier
                escalated_score = min(100.0, 60.0 + min(40.0, (effective_overrun_pct - 15.0) * 0.60 + max(0.0, ratio - 1.35) * 10.0))
                anomaly_type = "COST_OVERRUN_ANOMALY"
                reason = (
                    f"Severe cost overrun ({effective_overrun_pct:.1f}%) combined with peer anomaly. "
                    f"Expenditure (₹{project_cost:,.0f}) exceeds sanctioned limit (₹{sanctioned:,.0f}) "
                    f"and is {ratio:.1f}× peer median ({int(percentile)}th percentile)."
                )
            else:
                # Standalone cost overrun exceeding approved public sanction
                escalated_score = min(100.0, 50.0 + min(50.0, (effective_overrun_pct - 15.0) * 0.50))
                anomaly_type = "COST_OVERRUN_ANOMALY"
                reason = (
                    f"Cost overrun detected ({effective_overrun_pct:.1f}%): expenditure "
                    f"(₹{project_cost:,.0f}) exceeds approved sanctioned budget (₹{sanctioned:,.0f}) "
                    f"by ₹{project_cost - sanctioned:,.0f}."
                )
            return escalated_score, anomaly_type, reason

        # Case 2: Normal / Mild Range (Score 0–29)
        # Up to 35% above peer median or within Q3 + 0.5*IQR
        if ratio <= 1.35 and robust_z <= 1.5:
            score = max(0.0, min(25.0, max(0.0, deviation_pct) * 0.70))
            anomaly_type = "NORMAL"
            reason = (
                f"Project expenditure (₹{project_cost:,.0f}) is normal and well-aligned with "
                f"{peer_scope.replace('_', ' ')} peer median (₹{peer_median:,.0f}, "
                f"percentile: {int(percentile)}th)."
            )
            return score, anomaly_type, reason

        # Case 3: Elevated / High / Critical Cost Anomaly
        # Base raw statistical anomaly curve
        if ratio <= 1.8 and robust_z <= 2.5:
            # Mild to moderate elevation (Score 30–55)
            raw_score = 30.0 + (ratio - 1.35) / 0.45 * 25.0
        elif ratio <= 2.5 and robust_z <= 3.5:
            # Significant elevation (Score 55–75)
            raw_score = 55.0 + (ratio - 1.80) / 0.70 * 20.0
        else:
            # Severe statistical outlier (Score 75–100)
            raw_score = 75.0 + min(25.0, (ratio - 2.5) * 8.0)

        # Small-sample ceiling: avoid issuing CRITICAL risk (>=80) on small peer groups (< 3 peers)
        if peer_group_size < 3 and raw_score > 70.0:
            raw_score = min(70.0, raw_score * 0.85)

        # --- Legitimacy Protection ---
        # A project is legitimately expensive if:
        # 1. Official sanctioned amount is greater than 0 and supports this expenditure
        # 2. Project has zero or negative cost overrun (expenditure <= sanctioned * 1.02)
        is_legitimately_sanctioned = (
            sanctioned > 0.0
            and project_cost <= sanctioned * 1.02
            and cost_overrun_pct <= 0.0
        )

        if is_legitimately_sanctioned:
            if ratio <= 3.0:
                # Moderate peer elevation (<= 3x): dampened and capped at 50 (MEDIUM or LOW)
                dampened_score = min(50.0, raw_score * 0.65)
            else:
                # Extraordinary peer multiplier (> 3x): dampened to HIGH tier (capped at 75, avoiding CRITICAL)
                dampened_score = min(75.0, raw_score * 0.70)

            anomaly_type = "LEGITIMATE_HIGH_BUDGET"
            reason = (
                f"Project expenditure (₹{project_cost:,.0f}) is {ratio:.1f}× peer median, "
                f"but is strictly within the approved sanctioned budget (₹{sanctioned:,.0f}) "
                f"with zero cost overrun. Legitimate approved scale."
            )
            return dampened_score, anomaly_type, reason

        # Standard high-cost outlier
        anomaly_type = "HIGH_COST_OUTLIER"
        reason = (
            f"Project cost (₹{project_cost:,.0f}) is an anomaly ({ratio:.1f}× peer median "
            f"₹{peer_median:,.0f}, {int(percentile)}th percentile in sector '{sector}', "
            f"robust Z-score: {robust_z:.1f})."
        )
        return raw_score, anomaly_type, reason

    # -------------------------------------------------------------------------
    # Helper: Confidence Scoring
    # -------------------------------------------------------------------------

    def _compute_confidence(
        self,
        target_financial: Optional[Financial],
        target_features: Optional[ProjectFeature],
        peer_group_size: int,
        peer_scope: str,
    ) -> float:
        """
        Calculates diagnostic confidence based on data completeness and peer depth.
        """
        conf = 0.50

        # Peer group depth
        if peer_group_size >= 10:
            conf += 0.20
        elif peer_group_size >= 5:
            conf += 0.15
        elif peer_group_size >= 3:
            conf += 0.05
        elif peer_group_size == 2:
            conf -= 0.05
        else:
            conf -= 0.15

        # Geographic proximity
        if peer_scope == "sector_and_district":
            conf += 0.20
        elif peer_scope == "sector_and_state":
            conf += 0.15
        elif peer_scope == "sector_nationwide":
            conf += 0.08

        # Financial records completeness
        if target_financial:
            if target_financial.sanctioned_amount and target_financial.expenditure_amount:
                conf += 0.10
            elif target_financial.sanctioned_amount or target_financial.expenditure_amount:
                conf += 0.05

        # Feature availability
        if target_features and getattr(target_features, "project_duration_days", None) is not None and target_features.project_duration_days > 0:
            conf += 0.05

        return round(max(0.20, min(1.0, conf)), 3)
