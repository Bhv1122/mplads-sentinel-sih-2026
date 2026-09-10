"""
backend/app/services/risk_engine.py
=============================================================================
Central Risk Aggregation Engine for MPLADS Projects (Engines 1–5).
=============================================================================

Integrates the five independent risk engines:
1. Engine 1: Cost Anomaly Detection (`cost_anomaly`)
2. Engine 2: Duplicate Detection (`duplicate_detection`)
3. Engine 3: Delay Detection (`delay_detection` / `delay`)
4. Engine 4: Financial/Physical Progress Mismatch (`progress_mismatch`)
5. Engine 5: Agency Pattern Detection (`agency_pattern`)

Calculates overall composite risk score:
overall_score =
    cost_score * cost_weight
  + duplicate_score * duplicate_weight
  + delay_score * delay_weight
  + progress_mismatch_score * progress_weight
  + agency_score * agency_weight

Risk Level Mapping (0–100):
  0 – 29  = LOW
 30 – 59  = MEDIUM
 60 – 79  = HIGH
 80 – 100 = CRITICAL

Safety & Fault-Tolerance Principles:
- Single Engine Failure Containment: If an engine fails, the pipeline does NOT crash.
  The failure is logged with a full traceback and recorded in `unavailable_engines`.
- Configurable Missing Engine Strategies:
  * "RENORMALIZE" (Default): Weights of remaining active engines are proportionally
    redistributed so effective weights always sum to 100%.
  * "NEUTRAL_FALLBACK": Unavailable engines are assigned a neutral score of 0 without
    re-weighting.
  * "EXCLUDE": Unavailable engines are omitted from the calculation.
- Data Integrity & Clamping: All input scores are strictly validated against None,
  non-numeric values, NaN, Inf, and clamped into [0, 100].
"""

import logging
import math
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional, List, Tuple, Union

from sqlalchemy import select, delete
from sqlalchemy.orm import Session

try:
    from app.config import settings
    from app.models.project import Project, RiskScore, RiskFactor
    from app.schemas.risk_engine import RiskLevel, EngineResult, ExplainedRiskResult, RiskFactorExplanation
    from app.services.risk.cost_anomaly_engine import CostAnomalyEngine
    from app.services.risk.duplicate_detection_engine import DuplicateDetectionEngine
    from app.services.risk.delay_detection_engine import DelayDetectionEngine
    from app.services.risk.progress_mismatch_engine import ProgressMismatchEngine
    from app.services.risk.agency_pattern_engine import AgencyPatternEngine
    from app.services.risk.explained_risk_engine import ExplainedRiskEngine
except ImportError:
    from backend.app.config import settings
    from backend.app.models.project import Project, RiskScore, RiskFactor
    from backend.app.schemas.risk_engine import RiskLevel, EngineResult, ExplainedRiskResult, RiskFactorExplanation
    from backend.app.services.risk.cost_anomaly_engine import CostAnomalyEngine
    from backend.app.services.risk.duplicate_detection_engine import DuplicateDetectionEngine
    from backend.app.services.risk.delay_detection_engine import DelayDetectionEngine
    from backend.app.services.risk.progress_mismatch_engine import ProgressMismatchEngine
    from backend.app.services.risk.agency_pattern_engine import AgencyPatternEngine
    from backend.app.services.risk.explained_risk_engine import ExplainedRiskEngine

logger = logging.getLogger(__name__)


# =============================================================================
# Category Mapping & PostgreSQL CHECK Constraint Conformance
# =============================================================================

SEVERITY_TO_IMPACT = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "critical": "Critical",
}

# PostgreSQL CHECK constraint for risk_factors.factor_category:
# ('Agency Past Performance', 'Delay in Tendering', 'Budget Gap', 'Slow Physical Pace',
#  'Monsoon Seasonality', 'Geographic Remoteness', 'Land Dispute', 'Contractor Inaction', 'Other')
DETECTOR_KEY_TO_FACTOR_CATEGORY = {
    "cost_anomaly": "Budget Gap",
    "delay": "Delay in Tendering",
    "delay_detection": "Delay in Tendering",
    "fund_utilization": "Budget Gap",
    "progress_mismatch": "Slow Physical Pace",
    "duplicate_detection": "Other",
    "agency_pattern": "Agency Past Performance",
    "explained_risk": "Other",
}
FACTOR_CATEGORY_DEFAULT = "Other"


def _score_to_impact(score: float) -> str:
    """Maps a 0-100 score to a factor impact level matching the FactorImpactEnum."""
    if score >= 80:
        return "Critical"
    elif score >= 60:
        return "High"
    elif score >= 30:
        return "Medium"
    return "Low"


# =============================================================================
# Central Risk Aggregation Engine
# =============================================================================

class NormalizedWeights(dict):
    """
    Dictionary supporting transparent alias lookup for 'delay' and 'delay_detection'
    without duplicating keys in keys(), values(), or items(), ensuring sum(values()) is exact.
    """
    def __getitem__(self, key: str) -> float:
        if key == "delay" and not super().__contains__("delay") and super().__contains__("delay_detection"):
            return super().__getitem__("delay_detection")
        if key == "delay_detection" and not super().__contains__("delay_detection") and super().__contains__("delay"):
            return super().__getitem__("delay")
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: object) -> bool:
        if super().__contains__(key):
            return True
        if key == "delay" and super().__contains__("delay_detection"):
            return True
        if key == "delay_detection" and super().__contains__("delay"):
            return True
        return False


class RiskEngine:
    """
    Central Risk Aggregation Engine orchestrating Engines 1–5.
    """

    CANONICAL_KEYS = {
        "cost_anomaly": "cost_anomaly",
        "cost": "cost_anomaly",
        "duplicate_detection": "duplicate_detection",
        "duplicate": "duplicate_detection",
        "delay_detection": "delay_detection",
        "delay": "delay_detection",
        "progress_mismatch": "progress_mismatch",
        "progress": "progress_mismatch",
        "agency_pattern": "agency_pattern",
        "agency": "agency_pattern",
    }

    DETECTOR_DISPLAY_NAMES = {
        "cost_anomaly": "Cost Anomaly Detection",
        "duplicate_detection": "Duplicate Project Detection",
        "delay_detection": "Project Delay Detection",
        "delay": "Project Delay Detection",
        "progress_mismatch": "Progress Mismatch Detection",
        "agency_pattern": "Agency Pattern Analysis",
        "fund_utilization": "Fund Utilization Analysis",
        "explained_risk": "Explained Risk Assessment",
    }


    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        thresholds: Optional[List[Tuple[float, str]]] = None,
        engine_version: Optional[str] = None,
        missing_strategy: Optional[str] = None,
        cost_anomaly_engine: Optional[CostAnomalyEngine] = None,
        duplicate_detection_engine: Optional[DuplicateDetectionEngine] = None,
        delay_detection_engine: Optional[DelayDetectionEngine] = None,
        progress_mismatch_engine: Optional[ProgressMismatchEngine] = None,
        agency_pattern_engine: Optional[AgencyPatternEngine] = None,
        runner: Optional[Any] = None,
    ):
        """
        Initializes the Risk Aggregation Engine with configurable weights and thresholds.
        """
        # Default weights from centralized config (20% each across Engines 1–5)
        default_weights = {
            "cost_anomaly": float(getattr(settings, "ENGINE_WEIGHT_COST_ANOMALY", 0.20)),
            "duplicate_detection": float(getattr(settings, "ENGINE_WEIGHT_DUPLICATE_DETECTION", 0.20)),
            "delay_detection": float(getattr(settings, "ENGINE_WEIGHT_DELAY_DETECTION", 0.20)),
            "progress_mismatch": float(getattr(settings, "ENGINE_WEIGHT_PROGRESS_MISMATCH", 0.20)),
            "agency_pattern": float(getattr(settings, "ENGINE_WEIGHT_AGENCY_PATTERN", 0.20)),
        }

        raw_weights = weights if weights is not None else default_weights
        self.weights: Dict[str, float] = self._normalize_weight_dict(raw_weights)
        self.thresholds: List[Tuple[float, str]] = (
            thresholds if thresholds is not None else settings.risk_thresholds
        )
        self.engine_version: str = engine_version or settings.RISK_ENGINE_VERSION
        self.missing_strategy: str = (
            missing_strategy
            or getattr(settings, "MISSING_ENGINE_STRATEGY", "RENORMALIZE")
        ).upper()

        # Engine instances
        self.cost_anomaly_engine = cost_anomaly_engine or CostAnomalyEngine()
        self.duplicate_detection_engine = duplicate_detection_engine or DuplicateDetectionEngine()
        self.delay_detection_engine = delay_detection_engine or DelayDetectionEngine()
        self.progress_mismatch_engine = progress_mismatch_engine or ProgressMismatchEngine()
        self.agency_pattern_engine = agency_pattern_engine or AgencyPatternEngine()
        self.explained_risk_engine = ExplainedRiskEngine(risk_engine=self)

        # Legacy runner support for mock compatibility
        self._runner = runner

    @classmethod
    def _normalize_weight_dict(cls, weights: Dict[str, float]) -> Dict[str, float]:
        """
        Normalizes weight dictionary keys to canonical names while supporting aliases.
        """
        normalized: Dict[str, float] = {}
        for k, v in weights.items():
            canonical = cls.CANONICAL_KEYS.get(k, k)
            normalized[canonical] = float(v)
            # If alias exists, mirror it so both 'delay' and 'delay_detection' resolve
            if canonical == "delay_detection":
                normalized["delay"] = float(v)

        return normalized

    # -------------------------------------------------------------------------
    # Core Aggregation & Normalization
    # -------------------------------------------------------------------------

    def calculate_overall_score(
        self,
        scores: Dict[str, Any],
        weights: Optional[Dict[str, float]] = None,
        missing_strategy: Optional[str] = None,
    ) -> Tuple[float, str, Dict[str, float], List[str]]:
        """
        Calculates the aggregate 0–100 overall risk score across Engines 1–5:
        overall_score = sum(score_i * weight_i)

        Returns:
            Tuple of (overall_score, risk_level, effective_weights, unavailable_engines)
        """
        active_weights = self._normalize_weight_dict(weights) if weights else self.weights
        strategy = (missing_strategy or self.missing_strategy).upper()

        # Canonical engine list for Engines 1–5
        canonical_engines = [
            "cost_anomaly",
            "duplicate_detection",
            "delay_detection",
            "progress_mismatch",
            "agency_pattern",
        ]

        valid_scores: Dict[str, float] = {}
        unavailable_engines: List[str] = []

        for engine_key in canonical_engines:
            # Check for score under canonical key or alias (e.g. 'delay')
            raw_result = scores.get(engine_key)
            if raw_result is None and engine_key == "delay_detection":
                raw_result = scores.get("delay")

            if raw_result is None:
                unavailable_engines.append(engine_key)
                continue

            # Extract numeric score and inspect failure markers
            score_val = None
            is_error = False

            if isinstance(raw_result, (int, float)):
                score_val = raw_result
            elif isinstance(raw_result, dict):
                score_val = raw_result.get("score")
                details = raw_result.get("details", {})
                is_error = (
                    "error" in details
                    or raw_result.get("status") in {"error", "not_found"}
                    or raw_result.get("failed") is True
                )
            elif hasattr(raw_result, "score"):
                score_val = getattr(raw_result, "score", None)
                details = getattr(raw_result, "details", {})
                is_error = (
                    "error" in details
                    or getattr(raw_result, "status", None) in {"error", "not_found"}
                )
            else:
                is_error = True

            if is_error or score_val is None:
                unavailable_engines.append(engine_key)
                continue

            # Validate and clamp numeric score
            try:
                num = float(score_val)
                if math.isnan(num) or math.isinf(num):
                    logger.warning(
                        "Invalid non-finite score '%s' for engine '%s'; marking as unavailable.",
                        score_val, engine_key
                    )
                    unavailable_engines.append(engine_key)
                    continue
                # Bounded within [0, 100]
                clamped_score = max(0.0, min(100.0, num))
                valid_scores[engine_key] = clamped_score
            except (ValueError, TypeError):
                logger.warning(
                    "Non-numeric score '%s' for engine '%s'; marking as unavailable.",
                    score_val, engine_key
                )
                unavailable_engines.append(engine_key)
                continue

        # If all engines are unavailable
        if not valid_scores:
            logger.warning("All risk engines are unavailable; returning baseline score 0.")
            effective_weights = {k: 0.0 for k in canonical_engines}
            return 0.0, "LOW", NormalizedWeights(effective_weights), unavailable_engines

        # Calculate effective weights based on strategy
        effective_weights = {}
        weighted_sum = 0.0

        if strategy == "RENORMALIZE":
            total_avail_weight = sum(active_weights.get(k, 0.20) for k in valid_scores)
            if total_avail_weight <= 0:
                total_avail_weight = 1.0

            for k in canonical_engines:
                if k in valid_scores:
                    base_w = active_weights.get(k, 0.20)
                    ew = base_w / total_avail_weight
                    effective_weights[k] = round(ew, 4)
                    weighted_sum += valid_scores[k] * ew
                else:
                    effective_weights[k] = 0.0
        elif strategy in {"NEUTRAL_FALLBACK", "ZERO_FALLBACK"}:
            for k in canonical_engines:
                base_w = active_weights.get(k, 0.20)
                effective_weights[k] = round(base_w, 4)
                if k in valid_scores:
                    weighted_sum += valid_scores[k] * base_w
                else:
                    weighted_sum += 0.0 * base_w
        else:  # EXCLUDE
            for k in canonical_engines:
                base_w = active_weights.get(k, 0.20)
                if k in valid_scores:
                    effective_weights[k] = round(base_w, 4)
                    weighted_sum += valid_scores[k] * base_w
                else:
                    effective_weights[k] = 0.0

        overall_score = max(0.0, min(100.0, round(weighted_sum, 2)))
        risk_level = self._map_risk_level(overall_score)

        return overall_score, risk_level, NormalizedWeights(effective_weights), unavailable_engines

    def _compute_weighted_score(
        self,
        detector_results: Dict[str, Any],
    ) -> Tuple[float, Dict[str, float]]:
        """
        Backwards-compatible wrapper computing weighted score from detector outputs dictionary.
        Returns: (overall_score, effective_weights)
        """
        score, _, eff_weights, _ = self.calculate_overall_score(detector_results)
        return score, eff_weights

    def _map_risk_level(self, score: float) -> str:
        """
        Maps a 0-100 score to categorical risk level using self.thresholds if configured:
          0 – 29  = LOW
         30 – 59  = MEDIUM
         60 – 79  = HIGH
         80 – 100 = CRITICAL
        """
        s = float(score)
        if hasattr(self, "thresholds") and self.thresholds:
            # Check if thresholds are upper-bound exclusive (settings format) or lower-bound inclusive
            sorted_by_num = sorted(self.thresholds, key=lambda t: t[0])
            first_num, first_label = sorted_by_num[0]
            if first_num > 0 and str(first_label).upper() == "LOW":
                for bound, level in sorted_by_num:
                    if s < bound:
                        return str(level).upper()
                return str(sorted_by_num[-1][1]).upper()

            # Lower-bound format (e.g. [(0.0, 'LOW'), (40.0, 'MEDIUM'), (70.0, 'HIGH'), (90.0, 'CRITICAL')])
            sorted_descending = sorted(self.thresholds, key=lambda t: t[0], reverse=True)
            for bound, level in sorted_descending:
                if s >= bound:
                    return str(level).upper()
            return str(sorted_descending[-1][1]).upper()

        if s < 30.0:
            return "LOW"
        elif s < 60.0:
            return "MEDIUM"
        elif s < 80.0:
            return "HIGH"
        else:
            return "CRITICAL"

    def _compute_confidence(
        self,
        detector_results: Dict[str, Any],
    ) -> float:
        """
        Computes composite confidence based on successful engine executions
        and individual engine confidence metrics.
        """
        canonical_engines = [
            "cost_anomaly",
            "duplicate_detection",
            "delay_detection",
            "progress_mismatch",
            "agency_pattern",
        ]
        total = len(canonical_engines)
        successful = 0

        for key in canonical_engines:
            res = detector_results.get(key)
            if res is None and key == "delay_detection":
                res = detector_results.get("delay")

            if res is not None:
                if isinstance(res, dict):
                    details = res.get("details", {})
                    if "error" not in details and not res.get("failed"):
                        successful += 1
                elif hasattr(res, "details"):
                    details = getattr(res, "details", {})
                    if "error" not in details:
                        successful += 1
                elif isinstance(res, (int, float)):
                    successful += 1

        return round(successful / float(total), 3) if total > 0 else 0.0

    # -------------------------------------------------------------------------
    # Public Evaluation Interface
    # -------------------------------------------------------------------------

    def evaluate(
        self,
        project_id: str,
        db: Session,
        persist: bool = True,
        context: Optional[Dict[str, Any]] = None,
        commit: bool = True,
    ) -> Dict[str, Any]:
        """
        Runs all 5 risk engines for a project, aggregates scores, and optionally persists.

        Returns a structured risk engine result dictionary conforming to RiskEngineResult.
        """
        detector_results: Dict[str, Dict[str, Any]] = {}
        failed_engines: List[str] = []

        if self._runner is not None:
            # Legacy runner provided (e.g. mock in unit tests)
            runner_output = self._runner.run(project_id=project_id, db=db, context=context)
            detector_results = runner_output.get("detectors", {})
        else:
            # Run Engines 1–5 directly with single-engine failure containment
            engine_map = {
                "cost_anomaly": self.cost_anomaly_engine,
                "duplicate_detection": self.duplicate_detection_engine,
                "delay_detection": self.delay_detection_engine,
                "progress_mismatch": self.progress_mismatch_engine,
                "agency_pattern": self.agency_pattern_engine,
            }

            for key, engine in engine_map.items():
                try:
                    res = engine.evaluate(project_id=project_id, db=db, context=context)
                    if hasattr(res, "to_standardized_dict"):
                        std_dict = res.to_standardized_dict()
                        std_dict["engine"] = getattr(res, "engine", key)
                        std_dict["risk_level"] = getattr(res, "risk_level", "LOW")
                        std_dict["reason"] = getattr(res, "reason", "")
                        std_dict["details"] = getattr(res, "details", {})
                        std_dict["confidence"] = getattr(res, "confidence", 1.0)
                        detector_results[key] = std_dict
                    elif hasattr(res, "to_dict"):
                        detector_results[key] = res.to_dict()
                    else:
                        detector_results[key] = res
                except Exception as e:
                    logger.error(
                        "Risk engine '%s' failed for project '%s': %s",
                        key, project_id, str(e), exc_info=True
                    )
                    failed_engines.append(key)
                    detector_results[key] = {
                        "engine": key,
                        "detector_name": key,
                        "triggered": False,
                        "severity": "low",
                        "score": 0,
                        "risk_level": "LOW",
                        "reason": f"Engine '{key}' encountered execution error: {str(e)}",
                        "details": {"error": str(e), "failed": True},
                        "metadata": {"error": str(e), "failed": True},
                        "evidence": [],
                        "confidence": 0.0,
                    }

        # 2. Compute weighted overall score
        overall_score, risk_level, effective_weights, unavailable = self.calculate_overall_score(
            scores=detector_results
        )

        # 3. Compute confidence
        confidence = self._compute_confidence(detector_results)

        # 4. Build detector breakdown
        breakdown = []
        canonical_engines = [
            "cost_anomaly",
            "duplicate_detection",
            "delay_detection",
            "progress_mismatch",
            "agency_pattern",
        ]
        for key in canonical_engines:
            res = detector_results.get(key)
            if res is None and key == "delay_detection":
                res = detector_results.get("delay", {})
            if res is None:
                res = {}

            score_val = res.get("score", 0)
            eff_weight = effective_weights.get(key, 0.0)
            contrib_val = round(float(score_val) * eff_weight, 2)
            is_trig = res.get("triggered", score_val >= 30)
            sev_val = str(res.get("severity", res.get("risk_level", "low"))).lower()

            res["weight"] = eff_weight
            res["contribution"] = contrib_val

            breakdown.append({
                "detector_key": key,
                "detector_name": self.DETECTOR_DISPLAY_NAMES.get(key, key),
                "score": score_val,
                "weight": round(self.weights.get(key, 0.20), 4),
                "effective_weight": eff_weight,
                "contribution": contrib_val,
                "triggered": is_trig,
                "severity": sev_val,
                "reason": res.get("reason", "Engine did not execute."),
                "threshold": res.get("threshold"),
                "actual_value": res.get("actual_value"),
                "expected_value": res.get("expected_value"),
                "reference_value": res.get("reference_value"),
                "evidence": res.get("evidence", []),
                "details": res.get("details", {}),
                "metadata": res.get("metadata", res.get("details", {})),
                "confidence": res.get("confidence", 1.0),
            })

        # 5. Map sub-scores for schema & database compatibility
        delay_res = detector_results.get("delay_detection") or detector_results.get("delay") or {}
        cost_res = detector_results.get("cost_anomaly") or {}
        prog_res = detector_results.get("progress_mismatch") or {}
        agency_res = detector_results.get("agency_pattern") or {}

        sub_scores = {
            "delay_risk_score": float(delay_res.get("score", 0)),
            "cost_overrun_risk_score": float(cost_res.get("score", 0)),
            "non_completion_risk_score": float(prog_res.get("score", 0)),
            "leakage_risk_score": float(agency_res.get("score", 0)),
        }

        # 6. Run Engine 6 (Explained Risk Engine)
        explained = self.explain(
            project_id=project_id,
            engine_results={
                item["detector_key"]: item
                for item in breakdown
            },
            overall_score=overall_score,
            risk_level=risk_level,
            effective_weights={
                item["detector_key"]: item.get("effective_weight", 0.20)
                for item in breakdown
            },
        )
        explained_dict = explained.to_dict()

        engine_scores = {item["detector_key"]: float(item.get("score", 0)) for item in breakdown}
        engine_scores["explained_risk"] = overall_score

        reasons = {item["detector_key"]: item.get("reason", "") for item in breakdown}
        reasons["explained_risk"] = explained.summary

        evidence = {item["detector_key"]: item.get("details", {}) for item in breakdown}
        evidence["explained_risk"] = explained_dict

        now_iso = datetime.now(timezone.utc).isoformat()

        engine_result = {
            "project_id": project_id,
            "overall_score": overall_score,
            "overall_risk_score": overall_score,
            "risk_level": risk_level,
            "confidence": confidence,
            "assessment_date": date.today().isoformat(),
            "model_version": self.engine_version,
            "engine_version": self.engine_version,
            "config_version": getattr(settings, "RISK_ENGINE_CONFIG_VERSION", "v1.0"),
            "weights_used": dict(self.weights),
            "calculated_at": now_iso,
            "engine_scores": engine_scores,
            "reasons": reasons,
            "evidence": evidence,
            "summary": explained.summary,
            "recommended_review": explained.recommended_review,
            "explained_risk": explained_dict,
            "sub_scores": sub_scores,
            "detector_breakdown": breakdown,
            "unavailable_engines": unavailable,
            "evaluated_at": now_iso,
        }

        # 7. Persist if requested
        if persist:
            self._persist(project_id, engine_result, db, commit=commit)

        return engine_result

    def evaluate_batch(
        self,
        db: Session,
        project_ids: Optional[List[str]] = None,
        limit: int = 100,
        persist: bool = True,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Evaluates risk for multiple projects.
        """
        if project_ids is None:
            stmt = (
                select(Project.project_id)
                .order_by(Project.recommendation_date.desc())
                .limit(limit)
            )
            project_ids = [str(r[0]) for r in db.execute(stmt).all()]

        results = []
        for pid in project_ids:
            try:
                result = self.evaluate(
                    project_id=pid, db=db, persist=persist, context=context
                )
                results.append(result)
            except Exception as e:
                logger.error(
                    "Risk engine evaluation failed for project '%s': %s",
                    pid, str(e), exc_info=True
                )
                results.append({
                    "project_id": pid,
                    "overall_risk_score": 0.0,
                    "risk_level": "LOW",
                    "confidence": 0.0,
                    "assessment_date": date.today().isoformat(),
                    "error": str(e),
                    "model_version": self.engine_version,
                    "detector_breakdown": [],
                    "unavailable_engines": list(self.weights.keys()),
                })

        return results

    # -------------------------------------------------------------------------
    # Database Persistence
    # -------------------------------------------------------------------------

    def _persist(
        self,
        project_id: str,
        engine_result: Dict[str, Any],
        db: Session,
        commit: bool = True,
    ) -> None:
        """
        Upserts RiskScore and RiskFactor rows for the project.
        Supports in-place recalculation without creating duplicate records or deleting other projects' data.
        Preserves original created_at while refreshing updated_at.
        Persists all 6 risk engines (Engines 1–5 + Engine 6 Explained Risk).
        """
        try:
            # Verify target project exists in the database
            proj_exists = db.execute(
                select(Project.project_id).where(Project.project_id == project_id)
            ).scalar_one_or_none()
            if not proj_exists:
                logger.warning(
                    "Skipping database persistence: project '%s' does not exist in 'projects' table.",
                    project_id
                )
                return

            sub = engine_result.get("sub_scores", {})
            db_risk_level_map = {
                "LOW": "Low",
                "MEDIUM": "Moderate",
                "MODERATE": "Moderate",
                "HIGH": "High",
                "CRITICAL": "Critical",
            }
            raw_level = str(engine_result.get("risk_level", "Low")).upper()
            db_risk_level = db_risk_level_map.get(raw_level, "Low")

            now_utc = datetime.now(timezone.utc)
            overall_dec = Decimal(str(engine_result["overall_risk_score"])).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            delay_dec = Decimal(str(sub.get("delay_risk_score", 0))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            cost_dec = Decimal(str(sub.get("cost_overrun_risk_score", 0))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            prog_dec = Decimal(str(sub.get("non_completion_risk_score", 0))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            leakage_dec = Decimal(str(sub.get("leakage_risk_score", 0))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            conf_dec = Decimal(str(engine_result["confidence"])).quantize(
                Decimal("0.001"), rounding=ROUND_HALF_UP
            )

            # 1. Upsert RiskScore in-place (preserves created_at)
            existing_score = db.execute(
                select(RiskScore).where(RiskScore.project_id == project_id)
            ).scalar_one_or_none()

            if existing_score is not None:
                existing_score.overall_risk_score = overall_dec
                existing_score.delay_risk_score = delay_dec
                existing_score.cost_overrun_risk_score = cost_dec
                existing_score.non_completion_risk_score = prog_dec
                existing_score.leakage_risk_score = leakage_dec
                existing_score.risk_level = db_risk_level
                existing_score.confidence_score = conf_dec
                existing_score.assessment_date = date.today()
                existing_score.model_version = engine_result.get("model_version", "v1.0")
                existing_score.engine_version = self.engine_version
                existing_score.config_version = getattr(settings, "RISK_ENGINE_CONFIG_VERSION", "v1.0")
                existing_score.weights_used = dict(self.weights)
                existing_score.calculated_at = now_utc
                existing_score.updated_at = now_utc
                risk_score = existing_score
            else:
                risk_score = RiskScore(
                    project_id=project_id,
                    overall_risk_score=overall_dec,
                    delay_risk_score=delay_dec,
                    cost_overrun_risk_score=cost_dec,
                    non_completion_risk_score=prog_dec,
                    leakage_risk_score=leakage_dec,
                    risk_level=db_risk_level,
                    confidence_score=conf_dec,
                    assessment_date=date.today(),
                    model_version=engine_result.get("model_version", "v1.0"),
                    engine_version=self.engine_version,
                    config_version=getattr(settings, "RISK_ENGINE_CONFIG_VERSION", "v1.0"),
                    weights_used=dict(self.weights),
                    calculated_at=now_utc,
                    created_at=now_utc,
                    updated_at=now_utc,
                )
                db.add(risk_score)

            db.flush()

            # 2. Refresh RiskFactor rows for this risk_score atomically within the transaction
            db.execute(
                delete(RiskFactor).where(RiskFactor.risk_score_id == risk_score.risk_score_id)
            )

            # Persist Engines 1–5
            for item in engine_result.get("detector_breakdown", []):
                score_val = item.get("score", 0)
                sev = str(item.get("severity", item.get("risk_level", "LOW"))).upper()
                factor = RiskFactor(
                    risk_score_id=risk_score.risk_score_id,
                    project_id=project_id,
                    factor_category=DETECTOR_KEY_TO_FACTOR_CATEGORY.get(
                        item["detector_key"], FACTOR_CATEGORY_DEFAULT
                    ),
                    factor_name=item["detector_name"],
                    factor_weight=Decimal(
                        str(item.get("effective_weight") or item.get("weight", 0.20))
                    ).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP),
                    factor_impact=_score_to_impact(score_val),
                    mitigation_recommendation=item.get("reason", "No recommendation."),
                    is_mitigated=False,
                    created_at=now_utc,
                    engine_name=item["detector_key"],
                    score=Decimal(str(score_val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    risk_level=sev,
                    reason=item.get("reason", ""),
                    confidence=Decimal(
                        str(item.get("confidence", engine_result.get("confidence", 1.0)))
                    ).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP),
                    details=item.get("details", {}),
                )
                db.add(factor)

            # 3. Generate and persist Engine 6 (Explained Risk Engine)
            explained_dict = engine_result.get("explained_risk")
            if not explained_dict:
                explained = self.explain(
                    project_id=project_id,
                    engine_results={
                        item["detector_key"]: item
                        for item in engine_result.get("detector_breakdown", [])
                    },
                    overall_score=float(engine_result["overall_risk_score"]),
                    risk_level=engine_result["risk_level"],
                    effective_weights={
                        item["detector_key"]: item.get("effective_weight", 0.20)
                        for item in engine_result.get("detector_breakdown", [])
                    },
                )
                explained_dict = explained.to_dict()
                engine_result["explained_risk"] = explained_dict

            summary_text = engine_result.get("summary") or explained_dict.get("summary", "Explained risk evaluation completed.")

            explained_factor = RiskFactor(
                risk_score_id=risk_score.risk_score_id,
                project_id=project_id,
                factor_category="Other",
                factor_name="Explained Risk Assessment",
                factor_weight=Decimal("0.000"),
                factor_impact=_score_to_impact(engine_result["overall_risk_score"]),
                mitigation_recommendation=summary_text,
                is_mitigated=False,
                created_at=now_utc,
                engine_name="explained_risk",
                score=Decimal(str(engine_result["overall_risk_score"])).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
                risk_level=str(engine_result["risk_level"]).upper(),
                reason=summary_text,
                confidence=Decimal(str(engine_result["confidence"])).quantize(
                    Decimal("0.001"), rounding=ROUND_HALF_UP
                ),
                details=explained_dict,
            )
            db.add(explained_factor)

            if commit:
                db.commit()
            else:
                db.flush()
            logger.info(
                "Risk engine successfully persisted project '%s': score=%.2f, level=%s (all 6 engines recorded, committed=%s)",
                project_id, engine_result["overall_risk_score"], engine_result["risk_level"], commit
            )

        except Exception as e:
            if commit:
                db.rollback()
            logger.error(
                "Failed to persist risk engine results for project '%s': %s",
                project_id, str(e), exc_info=True
            )
            raise


    # -------------------------------------------------------------------------
    # Engine 6: Explanation Interface
    # -------------------------------------------------------------------------

    def explain(
        self,
        project_id: Union[str, int],
        engine_results: Dict[str, Any],
        overall_score: Optional[float] = None,
        risk_level: Optional[str] = None,
        effective_weights: Optional[Dict[str, float]] = None,
    ) -> ExplainedRiskResult:
        """
        Engine 6: Deconstructs the overall risk score and produces a deterministic,
        evidence-grounded explanation ranking contributing factors.
        """
        return self.explained_risk_engine.explain(
            project_id=project_id,
            engine_results=engine_results,
            overall_score=overall_score,
            risk_level=risk_level,
            effective_weights=effective_weights,
        )

    def explain_project(
        self,
        project_id: str,
        db: Session,
    ) -> ExplainedRiskResult:
        """
        Runs complete evaluation for a project and generates the auditable Engine 6 explanation.
        """
        result = self.explained_risk_engine.evaluate(project_id, db)
        return ExplainedRiskResult(**result.details)

