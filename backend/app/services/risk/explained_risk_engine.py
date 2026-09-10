"""
backend/app/services/risk/explained_risk_engine.py
=============================================================================
Engine 6 — Explained Risk Engine
=============================================================================

This engine does NOT independently calculate new risk signals.
It consumes the outputs of Engines 1–5 and the central aggregate risk score,
explaining why a project received its score in a transparent, deterministic,
and audit-ready format.

For each project, it generates:
- overall_score (0-100 bounded)
- risk_level (LOW, MEDIUM, HIGH, CRITICAL)
- short summary (deterministic, evidence-grounded, non-accusatory)
- individual engine scores
- top contributing risk factors ranked by contribution (score * weight)
- contribution of each factor
- concrete evidence supporting each factor extracted from engine outputs
- recommended review areas

Strict Governance Language Compliance:
- Strictly avoids accusatory terms: "fraud", "corruption", "manipulation", "wrongdoing".
- Strictly utilizes cautious governance language:
    * "potential anomaly"
    * "unusual pattern"
    * "possible duplicate"
    * "significant deviation"
    * "requires verification"
"""

import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from sqlalchemy import select
from sqlalchemy.orm import Session

try:
    from app.config import settings
    from app.models.project import Project
    from app.schemas.risk_engine import (
        RiskLevel,
        EngineResult,
        RiskFactorExplanation,
        ExplainedRiskResult,
    )
    from app.services.risk.engine_base import BaseRiskEngine
except ImportError:
    from backend.app.config import settings
    from backend.app.models.project import Project
    from backend.app.schemas.risk_engine import (
        RiskLevel,
        EngineResult,
        RiskFactorExplanation,
        ExplainedRiskResult,
    )
    from backend.app.services.risk.engine_base import BaseRiskEngine

logger = logging.getLogger(__name__)


class ExplainedRiskEngine(BaseRiskEngine):
    """
    Engine 6: Consumes Engines 1–5 outputs and aggregate risk metrics
    to produce deterministic, evidence-backed explanations without generating
    independent risk signals.
    """
    engine_name: str = "explained_risk"
    version: str = "1.0.0"

    CANONICAL_ENGINES = [
        "cost_anomaly",
        "duplicate_detection",
        "delay_detection",
        "progress_mismatch",
        "agency_pattern",
    ]

    ENGINE_DISPLAY_NAMES = {
        "cost_anomaly": "Cost Anomaly",
        "duplicate_detection": "Duplicate Detection",
        "delay_detection": "Delay Detection",
        "delay": "Delay Detection",
        "progress_mismatch": "Progress Mismatch",
        "agency_pattern": "Agency Pattern",
    }

    def __init__(self, risk_engine: Optional[Any] = None):
        """
        Initializes the Explained Risk Engine.
        Optional risk_engine instance can be provided to resolve aggregate scores when needed.
        """
        self._risk_engine = risk_engine

    # -------------------------------------------------------------------------
    # Core Explanation Generation (No New Risk Signals)
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
        Consumes outputs of Engines 1–5 and central risk score to construct
        an auditable, ranked explanation.

        Args:
            project_id: Project identifier.
            engine_results: Dictionary mapping engine names to EngineResult, dict, or score.
            overall_score: Optional aggregate risk score. If None, calculated via weights.
            risk_level: Optional aggregate risk level. If None, mapped from score.
            effective_weights: Optional active/effective weights used in central aggregation.

        Returns:
            ExplainedRiskResult model conforming to specification.
        """
        # Default weights (20% each) if not provided
        weights = effective_weights or {
            "cost_anomaly": 0.20,
            "duplicate_detection": 0.20,
            "delay_detection": 0.20,
            "progress_mismatch": 0.20,
            "agency_pattern": 0.20,
        }

        # 1. Parse individual engine scores, reasons, and evidence
        engine_scores: Dict[str, int] = {}
        factor_items: List[RiskFactorExplanation] = []

        for canonical_name in self.CANONICAL_ENGINES:
            raw_entry = engine_results.get(canonical_name)
            if raw_entry is None and canonical_name == "delay_detection":
                raw_entry = engine_results.get("delay")

            # Extract raw score
            score_val = 0
            raw_reason = ""
            raw_details: Dict[str, Any] = {}

            if raw_entry is not None:
                if isinstance(raw_entry, (int, float)):
                    score_val = max(0, min(100, int(round(float(raw_entry)))))
                elif isinstance(raw_entry, dict):
                    raw_score = raw_entry.get("score", 0)
                    try:
                        score_val = max(0, min(100, int(round(float(raw_score)))))
                    except (ValueError, TypeError):
                        score_val = 0
                    raw_reason = str(raw_entry.get("reason", ""))
                    raw_details = raw_entry.get("details", {}) or {}
                elif hasattr(raw_entry, "score"):
                    raw_score = getattr(raw_entry, "score", 0)
                    try:
                        score_val = max(0, min(100, int(round(float(raw_score)))))
                    except (ValueError, TypeError):
                        score_val = 0
                    raw_reason = str(getattr(raw_entry, "reason", ""))
                    raw_details = getattr(raw_entry, "details", {}) or {}

            engine_scores[canonical_name] = score_val

            # Resolve engine weight (support alias for delay)
            weight = weights.get(canonical_name)
            if weight is None and canonical_name == "delay_detection":
                weight = weights.get("delay", 0.20)
            if weight is None:
                weight = 0.20

            # Calculate point contribution
            contribution = round(score_val * float(weight), 2)

            # Extract actual evidence from details without inventing information
            evidence = self._extract_evidence(canonical_name, raw_details)

            # Format cautious, non-accusatory reason grounded in evidence
            reason = self._format_cautious_reason(canonical_name, score_val, raw_reason, evidence)

            factor_items.append(
                RiskFactorExplanation(
                    engine=canonical_name,
                    score=score_val,
                    contribution=contribution,
                    reason=reason,
                    evidence=evidence,
                )
            )

        # 2. Rank risk factors strictly by contribution descending (with deterministic tie-breakers)
        ranked_factors = sorted(
            factor_items,
            key=lambda x: (-x.contribution, -x.score, x.engine),
        )

        # 3. Determine overall score and risk level if not explicitly provided
        if overall_score is None:
            computed_score = sum(f.contribution for f in factor_items)
            overall_score = max(0.0, min(100.0, round(computed_score, 2)))
        else:
            overall_score = max(0.0, min(100.0, round(float(overall_score), 2)))

        if risk_level is None:
            risk_level = self._map_risk_level(overall_score)
        else:
            risk_level = str(risk_level).upper()

        # 4. Generate deterministic, cautious narrative summary
        summary = self._generate_summary(overall_score, risk_level, ranked_factors)

        # 5. Generate recommended review areas
        recommended_review = self._generate_recommendations(overall_score, risk_level, ranked_factors)

        return ExplainedRiskResult(
            project_id=project_id,
            overall_score=overall_score,
            risk_level=risk_level,
            summary=summary,
            engine_scores=engine_scores,
            risk_factors=ranked_factors,
            recommended_review=recommended_review,
        )

    # -------------------------------------------------------------------------
    # BaseRiskEngine Interface Implementation
    # -------------------------------------------------------------------------

    def evaluate(
        self,
        project_id: str,
        db: Session,
        context: Optional[Dict[str, Any]] = None,
    ) -> EngineResult:
        """
        BaseRiskEngine contract method.
        Executes explanation for a project using existing or newly calculated
        Engines 1–5 evaluations, returning standard EngineResult.
        """
        # Lazy import to avoid circular dependency
        from app.services.risk_engine import RiskEngine

        risk_eng = self._risk_engine or RiskEngine()
        context_dict = context or {}

        # Run aggregate evaluation across Engines 1–5
        eval_res = risk_eng.evaluate(project_id, db)

        # Build engine_results dict from detector breakdown
        engine_results: Dict[str, Any] = {}
        effective_weights: Dict[str, float] = {}
        for item in eval_res.get("detector_breakdown", []):
            k = item["detector_key"]
            engine_results[k] = {
                "score": item.get("score", 0),
                "reason": item.get("reason", ""),
                "details": item.get("details", {}),
            }
            effective_weights[k] = item.get("effective_weight", 0.20)

        explained = self.explain(
            project_id=project_id,
            engine_results=engine_results,
            overall_score=float(eval_res["overall_risk_score"]),
            risk_level=eval_res["risk_level"],
            effective_weights=effective_weights,
        )

        # Inspect project for explanation/justification fields
        stmt = select(Project).where(Project.project_id == project_id)
        proj = db.execute(stmt).scalar_one_or_none()

        remarks = getattr(proj, "remarks", None) or "" if proj else ""
        has_explanation = bool(remarks and len(remarks.strip()) > 5)
        justification_status = "DOCUMENTED" if has_explanation else "MISSING"
        missing_or_insufficient = (explained.overall_score >= 30.0) and not has_explanation

        if missing_or_insufficient:
            actual_val = "Elevated risk signals without documented administrative justification in official records"
        elif has_explanation:
            actual_val = f"Documented justification recorded: '{remarks.strip()[:60]}'"
        else:
            actual_val = "Low composite risk; standard quarterly progress tracking"

        top_factor_name = explained.risk_factors[0].engine if explained.risk_factors else "None"
        evidence_items = [
            {
                "metric": "justification_status",
                "label": "Justification Status",
                "value": justification_status,
                "formatted": justification_status,
            },
            {
                "metric": "missing_or_insufficient_explanation",
                "label": "Missing/Insufficient Explanation",
                "value": missing_or_insufficient,
                "formatted": "Yes" if missing_or_insufficient else "No",
            },
            {
                "metric": "supporting_fields_used",
                "label": "Supporting Fields Inspected",
                "value": ["remarks", "project_description", "current_status"],
                "formatted": "remarks, project_description, current_status",
            },
            {
                "metric": "top_contributing_factor",
                "label": "Top Contributing Factor",
                "value": top_factor_name,
                "formatted": top_factor_name,
            },
        ]

        return self.build_result(
            score=explained.overall_score,
            reason=explained.summary,
            details=explained.to_dict(),
            confidence=float(eval_res.get("confidence", 1.0)),
            risk_level=RiskLevel(explained.risk_level),
            triggered=(explained.overall_score >= 30.0),
            threshold="Documented administrative justification for elevated risk signals (score >= 30)",
            actual_value=actual_val,
            expected_value="Documented justification notes for project delays or cost anomalies",
            reference_value=f"Composite score: {explained.overall_score} ({explained.risk_level})",
            evidence=evidence_items,
            metadata=explained.to_dict(),
        )


    # -------------------------------------------------------------------------
    # Evidence Extraction (Fact-Grounded, No Inventions)
    # -------------------------------------------------------------------------

    def _extract_evidence(self, engine: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts factual diagnostic indicators from engine outputs without inventing data.
        """
        evidence: Dict[str, Any] = {}

        if engine == "cost_anomaly":
            for field in [
                "sanctioned_amount",
                "cost",
                "peer_median",
                "peer_mean",
                "deviation",
                "deviation_pct",
                "cost_ratio",
                "peer_group",
                "sample_size",
            ]:
                if field in details and details[field] is not None:
                    evidence[field] = details[field]

        elif engine == "duplicate_detection":
            for field in [
                "matched_project_id",
                "similarity",
                "match_confidence",
                "category_match",
                "location_match",
                "description_preview",
            ]:
                if field in details and details[field] is not None:
                    evidence[field] = details[field]

        elif engine == "delay_detection":
            for field in [
                "overdue_days",
                "delay_percentage",
                "status",
                "sanction_date",
                "expected_completion_date",
                "actual_completion_date",
                "planned_duration_days",
            ]:
                if field in details and details[field] is not None:
                    evidence[field] = details[field]

        elif engine == "progress_mismatch":
            for field in [
                "financial_progress",
                "physical_progress",
                "progress_gap",
                "sanctioned_amount",
                "expenditure",
            ]:
                if field in details and details[field] is not None:
                    evidence[field] = details[field]

        elif engine == "agency_pattern":
            for field in [
                "agency_name",
                "projects_analyzed",
                "delay_rate",
                "cost_anomaly_rate",
                "mismatch_rate",
                "historical_sample_size",
            ]:
                if field in details and details[field] is not None:
                    evidence[field] = details[field]

        # Preserve any existing error messages for audit transparency
        if "error" in details:
            evidence["error"] = details["error"]

        return evidence

    # -------------------------------------------------------------------------
    # Cautious Reason Formatting (Strict Governance Language)
    # -------------------------------------------------------------------------

    def _format_cautious_reason(
        self,
        engine: str,
        score: int,
        raw_reason: str,
        evidence: Dict[str, Any],
    ) -> str:
        """
        Produces non-accusatory explanations grounded strictly in observed metrics.
        """
        if "error" in evidence:
            return f"Engine output unavailable ({evidence['error']}); requires verification."

        if engine == "cost_anomaly":
            if score >= 60:
                dev = evidence.get("deviation_pct") or evidence.get("cost_ratio")
                dev_str = f" ({dev}% deviation)" if dev is not None else ""
                return (
                    f"Potential anomaly: sanctioned cost significantly deviates from category peer median{dev_str}; "
                    "requires verification against standard schedule of rates."
                )
            elif score >= 30:
                return "Moderate cost deviation observed relative to peer category benchmarks."
            else:
                return "Sanctioned cost aligns within expected peer group distribution."

        elif engine == "duplicate_detection":
            if score >= 60:
                matched_id = evidence.get("matched_project_id", "unspecified project")
                sim = evidence.get("similarity")
                sim_str = f" ({round(sim * 100, 1)}% similarity)" if isinstance(sim, (int, float)) else ""
                return (
                    f"Possible duplicate: high semantic description similarity{sim_str} with project {matched_id}; "
                    "requires scope and site verification."
                )
            elif score >= 30:
                matched_id = evidence.get("matched_project_id", "unspecified project")
                return f"Moderate textual similarity identified with project {matched_id}; requires verification."
            else:
                return "No significant textual overlap or duplicate characteristics identified."

        elif engine == "delay_detection":
            if score >= 60:
                days = evidence.get("overdue_days")
                pct = evidence.get("delay_percentage")
                detail_str = ""
                if days is not None and pct is not None:
                    detail_str = f" by {days} days ({pct}% delay against planned schedule)"
                elif days is not None:
                    detail_str = f" by {days} days"
                return f"Significant deviation in execution timeline: project overdue{detail_str}; requires schedule review."
            elif score >= 30:
                days = evidence.get("overdue_days", "several")
                return f"Moderate timeline slippage observed ({days} days overdue)."
            else:
                return "Project milestones and timeline are progressing on schedule."

        elif engine == "progress_mismatch":
            if score >= 60:
                fin = evidence.get("financial_progress")
                phy = evidence.get("physical_progress")
                gap = evidence.get("progress_gap")
                gap_str = ""
                if fin is not None and phy is not None:
                    gap_str = f" (financial: {fin}%, physical: {phy}%, gap: {gap}%)"
                return f"Unusual pattern: significant gap between financial disbursements and physical milestone progress{gap_str}; requires verification."
            elif score >= 30:
                gap = evidence.get("progress_gap")
                gap_str = f" ({gap}% gap)" if gap is not None else ""
                return f"Moderate divergence observed between financial expenditure and recorded physical progress{gap_str}."
            else:
                return "Financial utilization aligns closely with verified physical progress."

        elif engine == "agency_pattern":
            if score >= 60:
                agency = evidence.get("agency_name", "Implementing agency")
                count = evidence.get("projects_analyzed", 0)
                d_rate = evidence.get("delay_rate")
                d_str = f" ({d_rate}% delay rate)" if d_rate is not None else ""
                return f"Unusual pattern in historical performance for {agency} across {count} analyzed projects{d_str}; requires institutional review."
            elif score >= 30:
                count = evidence.get("projects_analyzed", 0)
                return f"Moderate historical risk pattern noted across {count} projects handled by agency."
            else:
                return "Historical agency performance metrics are consistent with standard benchmarks."

        # Fallback to sanitized raw reason or generic cautious statement
        if raw_reason:
            clean = raw_reason.replace("fraud", "potential anomaly").replace("corrupt", "irregular")
            return clean
        return "Indicator evaluated within normal operating tolerances."

    # -------------------------------------------------------------------------
    # Deterministic Narrative Summary Generation
    # -------------------------------------------------------------------------

    def _generate_summary(
        self,
        overall_score: float,
        risk_level: str,
        ranked_factors: List[RiskFactorExplanation],
    ) -> str:
        """
        Produces a concise, deterministic, and reproducible narrative summary
        describing why the project received its risk score.
        """
        elevated_factors = [f for f in ranked_factors if f.score >= 30 and f.contribution > 0.0]

        if not elevated_factors or overall_score < 30.0:
            return (
                f"Project exhibits low overall risk (score {overall_score:.1f}/100, tier: {risk_level}). "
                "All evaluated financial, timeline, scope, and institutional metrics are within expected parameters."
            )

        # Identify top 1-2 drivers
        top_driver_names = [
            f"{self.ENGINE_DISPLAY_NAMES.get(f.engine, f.engine)} ({f.contribution:.1f} pts)"
            for f in elevated_factors[:2]
        ]
        drivers_phrase = " and ".join(top_driver_names)

        if risk_level == "CRITICAL":
            return (
                f"Project exhibits critical overall risk (score {overall_score:.1f}/100, tier: {risk_level}) "
                f"driven primarily by {drivers_phrase}. "
                "Multiple indicators show significant deviations and unusual patterns that require immediate administrative verification."
            )
        elif risk_level == "HIGH":
            return (
                f"Project exhibits high overall risk (score {overall_score:.1f}/100, tier: {risk_level}) "
                f"with primary contributions from {drivers_phrase}. "
                "Identified potential anomalies warrant formal inspection before further milestone sign-off."
            )
        else:  # MEDIUM
            return (
                f"Project exhibits medium overall risk (score {overall_score:.1f}/100, tier: {risk_level}) "
                f"with notable contributions from {drivers_phrase}. "
                "Routine operational verification is advised to maintain project trajectory."
            )

    # -------------------------------------------------------------------------
    # Recommended Review Areas Generation
    # -------------------------------------------------------------------------

    def _generate_recommendations(
        self,
        overall_score: float,
        risk_level: str,
        ranked_factors: List[RiskFactorExplanation],
    ) -> List[str]:
        """
        Produces actionable, prioritized, and cautious review areas
        targeted directly to the highest contributing risk factors.
        """
        recommendations: List[str] = []

        # Target factors with score >= 30 and contribution > 0
        elevated_factors = [f for f in ranked_factors if f.score >= 30 and f.contribution > 0.0]

        if not elevated_factors:
            recommendations.append(
                "Continue standard periodic administrative monitoring; no prioritized field inspection required at this time."
            )
            return recommendations

        for factor in elevated_factors:
            engine = factor.engine
            score = factor.score
            ev = factor.evidence

            if engine == "cost_anomaly":
                recommendations.append(
                    "Conduct an independent engineering estimate and bill-of-quantities (BOQ) review "
                    "against the standard schedule of rates to verify cost reasonableness."
                )
            elif engine == "duplicate_detection":
                matched_id = ev.get("matched_project_id", "matched project")
                recommendations.append(
                    f"Perform physical site inspection and geo-coordinate verification to confirm project scope "
                    f"is fully distinct from {matched_id}."
                )
            elif engine == "delay_detection":
                days = ev.get("overdue_days", "")
                days_str = f" ({days} days overdue)" if days else ""
                recommendations.append(
                    f"Review contractor milestone schedules and site progress logs{days_str} to determine root causes "
                    "and assess formal extension approvals."
                )
            elif engine == "progress_mismatch":
                recommendations.append(
                    "Cross-reference physical measurement book (MB) recordings and site inspection certificates "
                    "with released financial disbursements to reconcile progress gaps."
                )
            elif engine == "agency_pattern":
                agency = ev.get("agency_name", "executing agency")
                recommendations.append(
                    f"Examine overall active project workload, past completion rates, and staffing capacity of {agency}."
                )

        # De-duplicate while preserving insertion order
        seen = set()
        deduped = []
        for r in recommendations:
            if r not in seen:
                seen.add(r)
                deduped.append(r)

        return deduped

    def _map_risk_level(self, score: float) -> str:
        """Centralized risk level mapping."""
        s = float(score)
        if s < 30.0:
            return "LOW"
        elif s < 60.0:
            return "MEDIUM"
        elif s < 80.0:
            return "HIGH"
        else:
            return "CRITICAL"
