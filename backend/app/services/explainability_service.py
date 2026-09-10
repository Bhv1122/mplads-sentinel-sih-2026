"""
backend/app/services/explainability_service.py
=============================================================================
Phase 8: Explainability Service for Project Risk Detection.
=============================================================================

Translates raw detector calculations and risk-engine aggregation results into
structured, auditable, and human-readable evidence.

Strict Governance Constraints:
1. No LLM Hallucinations: All explanations, evidence items, and recommendations
   are deterministically generated from actual detector numerical outputs,
   peer benchmarks, calendar timelines, and stored database metadata.
2. Objective Terminology: Never accuses fraud, corruption, or wrongdoing.
   Uses precise administrative audit language ("potential anomaly", "progress gap",
   "schedule overrun", "scope overlap").
3. Dual-Format Delivery: Returns both machine-readable diagnostic structures and
   UI-ready visual tokens (badges, display cards, warning chips, metric bars).

Architecture:
Detector Engines -> Detector Results -> Risk Engine -> Explainability Service -> Structured Explanation -> Frontend
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

try:
    from app.config import settings
    from app.models.project import Project, Financial, Progress, RiskScore, RiskFactor
    from app.schemas.explainability import (
        SeverityLevel,
        ActionPriority,
        ActionCategory,
        EvidenceItem,
        EvidenceStatement,
        DetectorContribution,
        RiskScoreDecompositionItem,
        RiskScoreDecomposition,
        ExplanationFactor,
        RecommendationAction,
        UIDisplayCard,
        StructuredExplanation,
        RiskContributionItem,
        WhyFlaggedExplanation,
        ProjectExplanationEvidence,
        ProjectExplanationFactor,
        ProjectExplanationResponse,
    )
    from app.services.risk_engine import RiskEngine
    from app.services.evidence_generator import EvidenceGenerator, evidence_generator, parse_numerical_value
except ImportError:
    from backend.app.config import settings
    from backend.app.models.project import Project, Financial, Progress, RiskScore, RiskFactor
    from backend.app.schemas.explainability import (
        SeverityLevel,
        ActionPriority,
        ActionCategory,
        EvidenceItem,
        EvidenceStatement,
        DetectorContribution,
        RiskScoreDecompositionItem,
        RiskScoreDecomposition,
        ExplanationFactor,
        RecommendationAction,
        UIDisplayCard,
        StructuredExplanation,
        RiskContributionItem,
        WhyFlaggedExplanation,
        ProjectExplanationEvidence,
        ProjectExplanationFactor,
        ProjectExplanationResponse,
    )
    from backend.app.services.risk_engine import RiskEngine
    from backend.app.services.evidence_generator import EvidenceGenerator, evidence_generator, parse_numerical_value

logger = logging.getLogger(__name__)


def _format_currency(amount: Optional[Union[float, int]]) -> str:
    """Format an amount into Indian Rupees format."""
    if amount is None:
        return "N/A"
    return f"₹{float(amount):,.2f}"


def _map_score_to_severity(score: float) -> SeverityLevel:
    """Standard mapping from score to SeverityLevel."""
    if score >= 80.0:
        return SeverityLevel.CRITICAL
    elif score >= 60.0:
        return SeverityLevel.HIGH
    elif score >= 30.0:
        return SeverityLevel.MEDIUM
    return SeverityLevel.LOW


# ---- Vocabulary normalization ------------------------------------------------
# The database stores risk levels as "Low"/"Moderate"/"High"/"Critical" (PostgreSQL
# enum), but the explainability API vocabulary is LOW/MEDIUM/HIGH/CRITICAL.
# This helper normalizes at all ingestion boundaries.
_RISK_LEVEL_NORMALIZE = {
    "MODERATE": "MEDIUM",
    "Moderate": "MEDIUM",
    "moderate": "medium",
}

_SEVERITY_NORMALIZE = {
    "moderate": "medium",
    "Moderate": "medium",
    "MODERATE": "MEDIUM",
}


def _normalize_risk_level(raw: str) -> str:
    """Normalizes risk level string: maps MODERATE→MEDIUM and uppercases."""
    upper = raw.strip().upper()
    return _RISK_LEVEL_NORMALIZE.get(upper, upper)


def _normalize_severity(raw: str) -> str:
    """Normalizes severity string: maps moderate→medium and lowercases."""
    lower = raw.strip().lower()
    return _SEVERITY_NORMALIZE.get(lower, lower)


class ExplainabilityService:
    """
    Core service for Phase 8 Explainability Layer.
    Synthesizes detector outputs and risk scores into human-readable evidence.
    """

    DETECTOR_METADATA = {
        "cost_anomaly": {
            "display_name": "Cost Anomaly Detection",
            "factor_name": "Cost Deviation & Budget Compliance",
            "icon": "currency",
            "default_weight": 0.20,
            "threshold_desc": "Expenditure > 1.35x peer median or cost overrun > 15.0%",
        },
        "duplicate_detection": {
            "display_name": "Duplicate Project Detection",
            "factor_name": "Textual & Scope Overlap",
            "icon": "copy",
            "default_weight": 0.20,
            "threshold_desc": "Semantic similarity >= 60.0% (Possible) / >= 75.0% (Strong)",
        },
        "delay_detection": {
            "display_name": "Project Delay Detection",
            "factor_name": "Execution Timeline & Schedule Slippage",
            "icon": "clock",
            "default_weight": 0.20,
            "threshold_desc": "Elapsed schedule exceeding planned completion date",
        },
        "progress_mismatch": {
            "display_name": "Progress Mismatch Detection",
            "factor_name": "Financial vs Physical Milestone Alignment",
            "icon": "bar-chart",
            "default_weight": 0.20,
            "threshold_desc": "Absolute discrepancy (|FP - PP|) > 10.0 percentage points",
        },
        "agency_pattern": {
            "display_name": "Agency Pattern Analysis",
            "factor_name": "Implementing Agency Historical Track Record",
            "icon": "users",
            "default_weight": 0.20,
            "threshold_desc": "Historical delay or mismatch rate > 25.0% (minimum 3 projects)",
        },
    }

    WHY_FLAGGED_FACTOR_NAMES = {
        "cost_anomaly": "Cost anomaly",
        "delay_detection": "Delay",
        "progress_mismatch": "Progress mismatch",
        "duplicate_detection": "Duplicate detection",
        "agency_pattern": "Agency pattern",
    }

    def __init__(
        self,
        risk_engine: Optional[RiskEngine] = None,
        evidence_generator_inst: Optional[EvidenceGenerator] = None,
    ):
        """Initializes the ExplainabilityService with RiskEngine and EvidenceGenerator."""
        self.risk_engine = risk_engine or RiskEngine()
        self.evidence_generator = evidence_generator_inst or evidence_generator or EvidenceGenerator()

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def explain_project(
        self,
        project_id: str,
        db: Session,
        risk_result: Optional[Dict[str, Any]] = None,
        recalculate: bool = False,
    ) -> StructuredExplanation:
        """
        Generates a comprehensive structured explanation for a project.

        Args:
            project_id: Target project ID.
            db: Database session.
            risk_result: Optional pre-calculated risk result dictionary.
            recalculate: Whether to force fresh re-evaluation.

        Returns:
            StructuredExplanation model.
        """
        # 1. Fetch project entity
        stmt = select(Project).where(Project.project_id == project_id)
        project = db.execute(stmt).scalar_one_or_none()

        project_title = project.project_title if project else None

        # 2. Resolve risk evaluation result
        if risk_result is None or recalculate:
            risk_result = self.risk_engine.evaluate(
                project_id=project_id,
                db=db,
                persist=recalculate,
            )

        # 3. Build structured explanation
        project_metadata = {
            "project_title": project_title,
            "sector": project.sector if project else None,
            "sub_sector": project.sub_sector if project else None,
            "district_name": project.district_name if project else None,
            "state_id": project.state_id if project else None,
            "implementing_agency": project.implementing_agency if project else None,
            "current_status": project.current_status if project else None,
        }

        return self.explain_risk_result(
            project_id=project_id,
            risk_result=risk_result,
            project_metadata=project_metadata,
        )

    def explain_risk_result(
        self,
        project_id: Optional[Union[str, Dict[str, Any]]] = None,
        risk_result: Optional[Dict[str, Any]] = None,
        project_metadata: Optional[Dict[str, Any]] = None,
    ) -> StructuredExplanation:
        """
        Pure in-memory explanation synthesis from evaluated risk results.
        Supports both explain_risk_result(project_id, risk_result) and explain_risk_result(risk_result=...).
        """
        if isinstance(project_id, dict) and risk_result is None:
            risk_result = project_id
            project_id = risk_result.get("project_id", "UNKNOWN")
        elif project_id is None and risk_result is not None:
            project_id = risk_result.get("project_id", "UNKNOWN")
        elif project_id is None and risk_result is None:
            risk_result = {}
            project_id = "UNKNOWN"
        else:
            project_id = str(project_id or (risk_result.get("project_id") if risk_result else "UNKNOWN"))

        overall_score = float(risk_result.get("overall_score", risk_result.get("overall_risk_score", 0.0)))
        risk_level = str(risk_result.get("risk_level", "LOW")).upper()
        confidence = float(risk_result.get("confidence", 1.0))
        summary = str(risk_result.get("summary", ""))

        weights = risk_result.get("weights_used", {})
        detector_breakdown = risk_result.get("detector_breakdown", [])

        # Index detector breakdown by key
        detector_map: Dict[str, Dict[str, Any]] = {}
        for d in detector_breakdown:
            k = d.get("detector_key", d.get("detector_name"))
            if k:
                detector_map[k] = d

        # Also support dictionary of engines/detectors if passed
        engines_dict = risk_result.get("engines") or risk_result.get("detectors") or {}
        if isinstance(engines_dict, dict):
            for k, val in engines_dict.items():
                if k not in detector_map and isinstance(val, dict):
                    detector_map[k] = val

        # Build factors & contributions
        factors: List[ExplanationFactor] = []
        contributions: List[DetectorContribution] = []
        triggered_count = 0

        canonical_keys = [
            "cost_anomaly",
            "duplicate_detection",
            "delay_detection",
            "progress_mismatch",
            "agency_pattern",
        ]

        for key in canonical_keys:
            det_data = detector_map.get(key)
            if not det_data:
                # Handle missing/unavailable detector
                score = 0.0
                weight = float(weights.get(key, self.DETECTOR_METADATA[key]["default_weight"]))
                contrib_pts = 0.0
                severity = SeverityLevel.LOW
                triggered = False
            else:
                score = float(det_data.get("score", 0.0))
                weight = float(det_data.get("effective_weight", det_data.get("weight", weights.get(key, 0.20))))
                contrib_pts = round(score * weight, 2)
                severity = _map_score_to_severity(score)
                # Triggered when score indicates non-negligible anomaly (score >= 30)
                triggered = score >= 30.0

            if triggered:
                triggered_count += 1

            pct_of_total = round((contrib_pts / overall_score * 100.0), 1) if overall_score > 0 else 0.0

            meta = self.DETECTOR_METADATA.get(key, {})
            disp_name = meta.get("display_name", key.replace("_", " ").title())

            contributions.append(DetectorContribution(
                detector_name=key,
                display_name=disp_name,
                score=round(score, 1),
                weight=round(weight, 2),
                contribution_points=contrib_pts,
                percentage_of_total=pct_of_total,
            ))

            # Build engine-specific explanation factor
            factor = self._build_engine_factor(
                key=key,
                det_data=det_data,
                score=score,
                weight=weight,
                contribution=contrib_pts,
                severity=severity,
                triggered=triggered,
                meta=meta,
            )
            factors.append(factor)

        # Sort factors descending by points contributed
        factors.sort(key=lambda f: f.contribution_to_risk_score, reverse=True)

        # Generate actionable recommendations
        recommendations = self._generate_recommendations(
            factors=factors,
            detector_map=detector_map,
            overall_score=overall_score,
            project_metadata=project_metadata,
        )

        # Generate UI presentation cards and badges
        ui_display = self._generate_ui_display(
            factors=factors,
            overall_score=overall_score,
            risk_level=risk_level,
            detector_map=detector_map,
        )

        # Synthesize fallback summary if not present
        if not summary:
            summary = self._synthesize_summary(
                overall_score=overall_score,
                risk_level=risk_level,
                factors=factors,
            )

        metadata = {
            "evaluated_at": risk_result.get("evaluated_at", datetime.now(timezone.utc).isoformat()),
            "model_version": "Phase 8 Explainability Engine v1.0",
            "aggregation_strategy": "weighted_composite",
            "non_fraud_disclaimer": (
                "Data-driven anomaly screening and administrative decision-support indicator. "
                "Does not constitute legal proof or determination of fraud."
            ),
        }

        # Collect concise factual evidence statements across factors
        concise_statements: List[str] = []
        for factor in factors:
            for stmt in getattr(factor, "evidence_statements", []):
                if stmt.statement and (factor.triggered_status or not concise_statements):
                    concise_statements.append(stmt.statement)

        if not concise_statements:
            for factor in factors:
                for stmt in getattr(factor, "evidence_statements", []):
                    if stmt.statement and stmt.statement not in concise_statements:
                        concise_statements.append(stmt.statement)

        # Generate concise 'Why Was This Flagged?' explanation containing only triggered factors
        why_flagged = self.generate_why_flagged(
            project_id=project_id,
            risk_result=risk_result,
            project_metadata=project_metadata,
            factors=factors,
        )

        score_decomposition = self._extract_decomposition_from_risk_result(risk_result)

        return StructuredExplanation(
            project_id=project_id,
            project_title=project_metadata.get("project_title") if project_metadata else None,
            overall_score=round(overall_score, 2),
            risk_level=risk_level,
            confidence=round(confidence, 2),
            summary=summary,
            triggered_detectors_count=triggered_count,
            total_detectors_count=len(canonical_keys),
            explanation_factors=factors,
            detector_contributions=contributions,
            recommendations=recommendations,
            concise_statements=concise_statements,
            why_flagged=why_flagged,
            ui_display=ui_display,
            metadata=metadata,
            score_decomposition=score_decomposition,
        )

    def get_why_flagged(
        self,
        project_id: str,
        db: Session,
        risk_result: Optional[Dict[str, Any]] = None,
        recalculate: bool = False,
    ) -> WhyFlaggedExplanation:
        """
        Retrieves project risk data and generates the concise 'Why Was This Flagged?'
        structured explanation based ONLY on triggered detectors.
        """
        stmt = select(Project).where(Project.project_id == project_id)
        project = db.execute(stmt).scalar_one_or_none()
        project_title = project.project_title if project else None

        if risk_result is None or recalculate:
            risk_result = self.risk_engine.evaluate(
                project_id=project_id,
                db=db,
                persist=recalculate,
            )

        metadata = {
            "project_title": project_title,
        }

        return self.generate_why_flagged(
            project_id=project_id,
            risk_result=risk_result,
            project_metadata=metadata,
        )

    def generate_why_flagged(
        self,
        project_id: Optional[Union[str, Dict[str, Any]]] = None,
        risk_result: Optional[Dict[str, Any]] = None,
        project_metadata: Optional[Dict[str, Any]] = None,
        factors: Optional[List[ExplanationFactor]] = None,
    ) -> WhyFlaggedExplanation:
        """
        Pure in-memory 'Why Was This Flagged?' explanation generator.
        Constructs a structured explanation containing ONLY triggered detectors.

        Conceptual Structure:
        WHY WAS THIS FLAGGED?

        Triggered factors:
        ✓ Cost anomaly
        ✓ Delay
        ✓ Progress mismatch

        Evidence:
        • Cost is 2.56× peer median
        • Delayed by 210 days
        • Financial progress exceeds physical progress by 47 percentage points

        Risk contribution:
        • Cost anomaly: 17.2 points
        • Delay: 16.0 points
        • Progress mismatch: 14.0 points

        Overall risk:
        HIGH
        """
        if isinstance(project_id, dict) and risk_result is None:
            risk_result = project_id
            project_id = risk_result.get("project_id", "UNKNOWN")
        elif project_id is None and risk_result is not None:
            project_id = risk_result.get("project_id", "UNKNOWN")
        elif project_id is None and risk_result is None:
            risk_result = {}
            project_id = "UNKNOWN"
        else:
            project_id = str(project_id or (risk_result.get("project_id") if risk_result else "UNKNOWN"))

        risk_result = risk_result or {}
        overall_score = float(risk_result.get("overall_score", risk_result.get("overall_risk_score", 0.0)))
        risk_level = _normalize_risk_level(str(risk_result.get("risk_level", _map_score_to_severity(overall_score).value)))
        project_title = (
            (project_metadata.get("project_title") if project_metadata else None)
            or risk_result.get("project_title")
        )

        weights = risk_result.get("weights_used", {})
        detector_breakdown = risk_result.get("detector_breakdown", [])

        detector_map: Dict[str, Dict[str, Any]] = {}
        for d in detector_breakdown:
            k = d.get("detector_key", d.get("detector_name"))
            if k:
                detector_map[k] = d

        engines_dict = risk_result.get("engines") or risk_result.get("detectors") or {}
        if isinstance(engines_dict, dict):
            for k, val in engines_dict.items():
                if k not in detector_map and isinstance(val, dict):
                    detector_map[k] = val

        canonical_keys = [
            "cost_anomaly",
            "delay_detection",
            "progress_mismatch",
            "duplicate_detection",
            "agency_pattern",
        ]

        factor_by_detector = {f.detector_name: f for f in factors} if factors else {}

        triggered_factors: List[str] = []
        evidence_items: List[str] = []
        risk_contributions: List[RiskContributionItem] = []
        raw_details: Dict[str, Any] = {}

        for key in canonical_keys:
            det_data = detector_map.get(key, {})
            factor = factor_by_detector.get(key)

            score = float(det_data.get("score", 0.0))
            if factor is not None:
                triggered = factor.triggered_status
            else:
                triggered = bool(det_data.get("triggered", score >= 30.0))

            # Strictly display only triggered factors with non-trivial score
            if not triggered or score < 20.0:
                continue

            factor_label = self.WHY_FLAGGED_FACTOR_NAMES.get(key, key.replace("_", " ").title())
            triggered_factors.append(factor_label)

            weight = float(det_data.get("effective_weight", det_data.get("weight", weights.get(key, 0.20))))
            points = round(score * weight, 1)
            formatted_points = f"{points:.1f} points"

            risk_contributions.append(
                RiskContributionItem(
                    factor=factor_label,
                    detector_name=key,
                    points=points,
                    formatted_points=formatted_points,
                )
            )

            # Retrieve evidence statements
            evidence_stmts = []
            if factor and getattr(factor, "evidence_statements", None):
                evidence_stmts = factor.evidence_statements
            else:
                evidence_stmts = self.evidence_generator.generate_statements_from_detector(key, det_data)

            det_details = det_data.get("details", {})
            raw_details[key] = det_details

            for stmt in evidence_stmts:
                txt = stmt.statement.strip().rstrip(".")
                if txt.startswith("Project is delayed by "):
                    txt = "Delayed by " + txt[len("Project is delayed by "):]
                if txt and txt not in evidence_items:
                    evidence_items.append(txt)

        is_flagged = len(triggered_factors) > 0
        message = None if is_flagged else "No significant risk factors were detected based on the configured detection thresholds."

        # Format conceptual layout
        lines = [
            "WHY WAS THIS FLAGGED?",
            "",
        ]

        if is_flagged:
            lines.append("Triggered factors:")
            for f in triggered_factors:
                lines.append(f"✓ {f}")
            lines.append("")

            lines.append("Evidence:")
            for ev in evidence_items:
                lines.append(f"• {ev}")
            lines.append("")

            lines.append("Risk contribution:")
            for rc in risk_contributions:
                lines.append(f"• {rc.factor}: {rc.formatted_points}")
            lines.append("")

            lines.append("Overall risk:")
            lines.append(risk_level)
        else:
            lines.append(message)
            lines.append("")
            lines.append("Overall risk:")
            lines.append(risk_level)

        formatted_text = "\n".join(lines)

        return WhyFlaggedExplanation(
            project_id=project_id,
            project_title=project_title,
            overall_risk=risk_level,
            overall_score=round(overall_score, 2),
            is_flagged=is_flagged,
            header="WHY WAS THIS FLAGGED?",
            message=message,
            triggered_factors=triggered_factors,
            evidence=evidence_items,
            risk_contributions=risk_contributions,
            formatted_text=formatted_text,
            raw_details=raw_details,
        )

    # -------------------------------------------------------------------------
    # Transparent Risk-Score Decomposition (Engines 1-6)
    # -------------------------------------------------------------------------

    DECOMPOSITION_DETECTORS: List[Tuple[str, str, float]] = [
        ("cost_anomaly", "Cost Anomaly", 0.20),
        ("delay_detection", "Delay", 0.20),
        ("progress_mismatch", "Progress Mismatch", 0.20),
        ("agency_pattern", "Agency Pattern", 0.20),
        ("duplicate_detection", "Duplicate", 0.20),
        ("explained_risk", "Explained", 0.0),
    ]

    def build_risk_score_decomposition(
        self,
        final_score: float,
        risk_level: str,
        detector_data: Dict[str, Dict[str, Any]],
        configured_weights: Optional[Dict[str, float]] = None,
        effective_weights: Optional[Dict[str, float]] = None,
        rounding_tolerance: float = 0.2,
    ) -> RiskScoreDecomposition:
        """
        Constructs a transparent mathematical risk-score decomposition from existing detector results.
        Reads actual configured weights and detector scores from the central Risk Engine.
        Does NOT create a second scoring algorithm.

        Exposes:
        - detector score
        - configured weight
        - weighted contribution
        - final score

        Ensures contributions mathematically reconcile with the final risk score within rounding tolerance.
        """
        conf_weights = configured_weights or {
            "cost_anomaly": 0.20,
            "delay_detection": 0.20,
            "progress_mismatch": 0.20,
            "agency_pattern": 0.20,
            "duplicate_detection": 0.20,
            "explained_risk": 0.0,
        }
        eff_weights = effective_weights or conf_weights

        components: List[RiskScoreDecompositionItem] = []
        final_score_val = round(float(final_score), 1)

        for det_key, det_name, default_w in self.DECOMPOSITION_DETECTORS:
            data = detector_data.get(det_key)
            if data is None and det_key == "delay_detection":
                data = detector_data.get("delay")
            if data is None:
                data = {}

            score_val = float(data.get("score", 0.0))
            conf_w = float(conf_weights.get(det_key, default_w))
            eff_w = float(eff_weights.get(det_key, data.get("effective_weight", data.get("weight", conf_w))))
            weighted_contrib = round(score_val * eff_w, 1)

            pct_of_total = (
                round((weighted_contrib / final_score_val) * 100.0, 1)
                if final_score_val > 0 else 0.0
            )

            components.append(RiskScoreDecompositionItem(
                detector_key=det_key,
                detector_name=det_name,
                detector_score=round(score_val, 1),
                configured_weight=round(conf_w, 2),
                effective_weight=round(eff_w, 4),
                weighted_contribution=weighted_contrib,
                percentage_of_total=pct_of_total,
            ))

        total_contributions = round(sum(c.weighted_contribution for c in components), 1)
        discrepancy = round(abs(total_contributions - final_score_val), 2)
        reconciled = discrepancy <= rounding_tolerance

        # Formatted decomposition text representation matching user format
        lines = [f"Overall Risk Score: {final_score_val:.1f}\n"]
        for c in components:
            prefix = "+" if c.weighted_contribution >= 0 else "-"
            lines.append(f"{c.detector_name:<18} {prefix}{abs(c.weighted_contribution):>4.1f}")
        lines.append("                   ------")
        lines.append(f"Total              {total_contributions:>5.1f}")
        formatted_breakdown = "\n".join(lines)

        return RiskScoreDecomposition(
            final_score=final_score_val,
            risk_level=str(risk_level).upper(),
            components=components,
            total_contributions=total_contributions,
            rounding_tolerance=rounding_tolerance,
            reconciled=reconciled,
            formatted_breakdown=formatted_breakdown,
        )

    def _extract_decomposition_from_risk_result(
        self,
        risk_result: Dict[str, Any],
        rounding_tolerance: float = 0.2,
    ) -> RiskScoreDecomposition:
        """Extracts decomposition from an existing Risk Engine result dictionary."""
        overall_score = float(risk_result.get("overall_score", risk_result.get("overall_risk_score", 0.0)))
        risk_level = str(risk_result.get("risk_level", "LOW")).upper()

        breakdown = risk_result.get("detector_breakdown", [])
        detector_data: Dict[str, Dict[str, Any]] = {}
        for d in breakdown:
            k = d.get("detector_key", d.get("detector_name"))
            if k:
                detector_data[k] = d

        engines = risk_result.get("engines") or risk_result.get("detectors") or {}
        if isinstance(engines, dict):
            for k, v in engines.items():
                if k not in detector_data and isinstance(v, dict):
                    detector_data[k] = v

        configured_weights = self.risk_engine.weights if hasattr(self.risk_engine, "weights") else None
        effective_weights = risk_result.get("weights_used")

        return self.build_risk_score_decomposition(
            final_score=overall_score,
            risk_level=risk_level,
            detector_data=detector_data,
            configured_weights=configured_weights,
            effective_weights=effective_weights,
            rounding_tolerance=rounding_tolerance,
        )

    def _extract_decomposition_from_db_record(
        self,
        cached_score: RiskScore,
        rounding_tolerance: float = 0.2,
    ) -> RiskScoreDecomposition:
        """Extracts decomposition from PostgreSQL RiskScore & RiskFactor rows."""
        overall_score = float(cached_score.overall_risk_score or 0.0)
        risk_level = str(cached_score.risk_level or "LOW").upper()

        detector_data: Dict[str, Dict[str, Any]] = {}
        configured_weights: Dict[str, float] = {}

        for f in cached_score.factors:
            if not f.engine_name:
                continue
            eng_name = f.engine_name
            score = float(f.score or 0.0)
            weight = float(f.factor_weight or 0.0)
            detector_data[eng_name] = {
                "score": score,
                "weight": weight,
                "effective_weight": weight,
            }
            configured_weights[eng_name] = weight

        if "delay" in detector_data and "delay_detection" not in detector_data:
            detector_data["delay_detection"] = detector_data["delay"]

        return self.build_risk_score_decomposition(
            final_score=overall_score,
            risk_level=risk_level,
            detector_data=detector_data,
            configured_weights=configured_weights,
            effective_weights=configured_weights,
            rounding_tolerance=rounding_tolerance,
        )

    def get_risk_score_decomposition(
        self,
        project_id: str,
        db: Session,
        recalculate: bool = False,
        risk_result: Optional[Dict[str, Any]] = None,
    ) -> RiskScoreDecomposition:
        """
        Public API: Reads existing Risk Engine calculation and returns the
        transparent risk-score decomposition into detector contributions.
        """
        if risk_result is not None:
            return self._extract_decomposition_from_risk_result(risk_result)

        if not recalculate:
            stmt = (
                select(RiskScore)
                .where(RiskScore.project_id == project_id)
                .options(selectinload(RiskScore.factors))
            )
            cached_score = db.execute(stmt).scalar_one_or_none()
            if cached_score is not None and cached_score.factors:
                return self._extract_decomposition_from_db_record(cached_score)

        evaluated_result = self.risk_engine.evaluate(
            project_id=project_id,
            db=db,
            persist=True,
        )
        return self._extract_decomposition_from_risk_result(evaluated_result)

    # -------------------------------------------------------------------------
    # Structured Project Explanation API (GET /projects/{id}/explanation)
    # -------------------------------------------------------------------------

    CANONICAL_DETECTOR_KEYS = [
        "cost_anomaly",
        "delay_detection",
        "progress_mismatch",
        "duplicate_detection",
        "agency_pattern",
    ]

    FACTOR_DISPLAY_NAMES = {
        "cost_anomaly": "Cost Anomaly",
        "delay_detection": "Delay Detection",
        "progress_mismatch": "Progress Mismatch",
        "duplicate_detection": "Duplicate Detection",
        "agency_pattern": "Agency Pattern",
    }

    SUMMARY_FACTOR_NAMES = {
        "cost_anomaly": "cost anomaly",
        "delay_detection": "delay",
        "progress_mismatch": "progress mismatch",
        "duplicate_detection": "duplicate similarity",
        "agency_pattern": "agency friction",
    }

    def get_project_explanation(
        self,
        project_id: str,
        db: Session,
        recalculate: bool = False,
        risk_result: Optional[Dict[str, Any]] = None,
        only_triggered: bool = False,
    ) -> ProjectExplanationResponse:
        """
        Retrieves or generates a complete structured explanation for a project.

        Follows strict efficiency and persistence rules:
        - If existing risk score and factors are found in PostgreSQL and recalculate=False,
          synthesizes the explanation directly from stored detector records without recomputation.
        - If recalculate=True or records do not exist, performs risk engine evaluation,
          persists results, and constructs the explanation.

        Args:
            project_id: Target project identifier.
            db: Active SQLAlchemy database session.
            recalculate: Whether to force re-evaluation by the risk engine.
            risk_result: Optional pre-calculated risk result dictionary (for in-memory use).
            only_triggered: If True, returns only factors that triggered risk flags.

        Returns:
            ProjectExplanationResponse containing project_id, risk_level, risk_score,
            summary, and granular factor evidence items.
        """
        if risk_result is not None:
            return self._build_from_risk_result(
                project_id=project_id,
                risk_result=risk_result,
                only_triggered=only_triggered,
            )

        if not recalculate:
            # Query existing database results
            stmt = (
                select(RiskScore)
                .where(RiskScore.project_id == project_id)
                .options(selectinload(RiskScore.factors))
            )
            cached_score = db.execute(stmt).scalar_one_or_none()
            if cached_score is not None and cached_score.factors:
                logger.info(
                    "Building explanation for project '%s' directly from stored database results.",
                    project_id
                )
                return self._build_from_db_record(
                    project_id=project_id,
                    cached_score=cached_score,
                    only_triggered=only_triggered,
                )

        # Recalculate or evaluate for first time
        logger.info(
            "Evaluating risk analysis for project '%s' (recalculate=%s)...",
            project_id,
            recalculate
        )
        evaluated_result = self.risk_engine.evaluate(
            project_id=project_id,
            db=db,
            persist=True,
        )
        return self._build_from_risk_result(
            project_id=project_id,
            risk_result=evaluated_result,
            only_triggered=only_triggered,
        )

    @property
    def DETECTOR_THRESHOLDS(self) -> Dict[str, str]:
        """Returns detector threshold descriptions sourced from centralized config."""
        agency_pct = int(getattr(settings, 'AGENCY_DELAY_RATE_THRESHOLD', 0.50) * 100)
        gap_low = int(getattr(settings, 'PROGRESS_MISMATCH_GAP_LOW', 10))
        cost_ratio = getattr(settings, 'COST_ANOMALY_RATIO_HIGH', 2.0)
        return {
            "cost_anomaly": f"Cost ≥ {cost_ratio}× peer median (or Robust Z ≥ 2.0)",
            "delay_detection": "Delay > 30 days beyond planned completion date",
            "progress_mismatch": f"Financial vs Physical divergence > {gap_low} percentage points",
            "duplicate_detection": "Semantic similarity ≥ 85% duplicate threshold (≥ 60% potential overlap)",
            "agency_pattern": f"Historical delay rate > {agency_pct}% or completion rate < 60%",
        }

    DETECTOR_RECOMMENDATIONS = {
        "cost_anomaly": "Initiate independent quantity survey audit and request rate variance justification from the implementing agency.",
        "delay_detection": "Review contractor milestone logs and site engineering journals to determine root causes of schedule slippage and verify formal extension approvals.",
        "progress_mismatch": "Cross-reference physical measurement book (MB) records with financial payment vouchers to reconcile disbursement lead over on-site milestone completion.",
        "duplicate_detection": "Cross-verify project geographic coordinates and scope items to rule out duplicate sanction or double-billing across schemes.",
        "agency_pattern": "Examine overall active workload, staffing capacity, and past completion track record of the implementing agency before assigning additional works.",
    }

    def _get_detector_reference(self, detector: str, details: Dict[str, Any]) -> Optional[str]:
        """Returns readable reference or benchmark comparison."""
        if detector == "cost_anomaly":
            m = details.get("peer_median") or details.get("reference_value")
            if m is not None:
                try:
                    m_f = float(m)
                    if m_f >= 10_000_000:
                        return f"Peer median: ₹{m_f / 10_000_000:.2f} Cr"
                    elif m_f >= 100_000:
                        return f"Peer median: ₹{m_f / 100_000:.2f} Lakh"
                    return f"Peer median: ₹{m_f:,.2f}"
                except (ValueError, TypeError):
                    return f"Peer median: {m}"
            return "Peer median: Expected category baseline"
        elif detector == "delay_detection":
            exp = details.get("expected_completion_date")
            dur = details.get("planned_duration")
            if exp and dur:
                return f"Planned duration: {dur} days (Expected: {exp})"
            elif exp:
                return f"Expected completion: {exp}"
            elif dur:
                return f"Planned duration: {dur} days"
            return "Milestone timeline schedule baseline"
        elif detector == "progress_mismatch":
            stage = details.get("current_stage", "Execution")
            gap_low = getattr(settings, 'PROGRESS_MISMATCH_GAP_LOW', 10.0)
            return f"Acceptable alignment tolerance: ±{gap_low:g}% (Current stage: '{stage}')"
        elif detector == "duplicate_detection":
            matched = details.get("matched_project_id")
            sim = details.get("raw_similarity") or details.get("similarity")
            if matched and sim:
                return f"Matched project: {matched} ({float(sim)*100:.1f}% raw similarity)"
            elif matched:
                return f"Matched project: {matched}"
            return "Duplicate threshold: ≥ 85% duplicate (≥ 60% potential overlap)"
        elif detector == "agency_pattern":
            agency_pct = getattr(settings, 'AGENCY_DELAY_RATE_THRESHOLD', 0.50) * 100
            return f"Institutional benchmark: < {agency_pct:g}% historical delay frequency"
        return None

    def _build_from_db_record(
        self,
        project_id: str,
        cached_score: RiskScore,
        only_triggered: bool = False,
    ) -> ProjectExplanationResponse:
        """Constructs ProjectExplanationResponse from PostgreSQL RiskScore & RiskFactor rows."""
        factor_map: Dict[str, RiskFactor] = {
            f.engine_name: f for f in cached_score.factors if f.engine_name
        }
        if "delay" in factor_map and "delay_detection" not in factor_map:
            factor_map["delay_detection"] = factor_map["delay"]

        overall_score = float(cached_score.overall_risk_score or 0.0)
        risk_level = _normalize_risk_level(str(cached_score.risk_level or "LOW"))

        explanation_factors: List[ProjectExplanationFactor] = []
        triggered_detectors: List[str] = []
        recommendations: List[str] = []

        for det in self.CANONICAL_DETECTOR_KEYS:
            rf = factor_map.get(det)
            if rf is not None:
                score = float(rf.score or 0.0)
                weight = float(rf.factor_weight or 0.20)
                details = dict(rf.details or {})
                triggered = bool(details.get("triggered", score >= 30.0))
                severity = _normalize_severity(str(rf.risk_level or _map_score_to_severity(score).value))
                contrib = round(score * weight, 1)
                ev_list = self._extract_factor_evidence(det, details, score)
                rec = rf.mitigation_recommendation or self.DETECTOR_RECOMMENDATIONS.get(det)
            else:
                score = 0.0
                weight = 0.20
                details = {}
                triggered = False
                severity = "low"
                contrib = 0.0
                ev_list = self._extract_factor_evidence(det, details, score)
                rec = self.DETECTOR_RECOMMENDATIONS.get(det)

            if triggered:
                triggered_detectors.append(det)
                if rec and rec not in recommendations:
                    recommendations.append(rec)

            ref_comp = self._get_detector_reference(det, details)
            thresh_raw = details.get("threshold") or self.DETECTOR_THRESHOLDS.get(det)
            thresh = str(thresh_raw) if thresh_raw is not None else None

            factor_model = ProjectExplanationFactor(
                name=self.FACTOR_DISPLAY_NAMES.get(det, det.replace("_", " ").title()),
                detector=det,
                triggered=triggered,
                severity=severity,
                contribution=contrib,
                detector_score=round(score, 1),
                weight=round(weight, 4),
                evidence=ev_list,
                threshold=thresh,
                reference_comparison=ref_comp,
                recommendation=rec,
                details=details,
            )
            explanation_factors.append(factor_model)

        explanation_factors.sort(key=lambda x: (not x.triggered, -x.contribution))

        if only_triggered:
            explanation_factors = [f for f in explanation_factors if f.triggered]

        summary = self._synthesize_explanation_summary(triggered_detectors)

        if not recommendations:
            recommendations.append("Continue routine quarterly milestone tracking and maintain regular monitoring reports.")

        score_decomposition = self._extract_decomposition_from_db_record(cached_score)

        return ProjectExplanationResponse(
            project_id=project_id,
            risk_level=risk_level,
            risk_score=round(overall_score, 1),
            summary=summary,
            factors=explanation_factors,
            recommendations=recommendations,
            score_decomposition=score_decomposition,
        )

    def _build_from_risk_result(
        self,
        project_id: str,
        risk_result: Dict[str, Any],
        only_triggered: bool = False,
    ) -> ProjectExplanationResponse:
        """Constructs ProjectExplanationResponse from risk_engine evaluation dictionary."""
        overall_score = float(risk_result.get("overall_score", risk_result.get("overall_risk_score", 0.0)))
        risk_level = str(risk_result.get("risk_level", "LOW")).upper()

        breakdown = risk_result.get("detector_breakdown", [])
        breakdown_map: Dict[str, Dict[str, Any]] = {}
        for d in breakdown:
            k = d.get("detector_key", d.get("detector_name"))
            if k:
                breakdown_map[k] = d

        engines = risk_result.get("engines") or risk_result.get("detectors") or {}
        if isinstance(engines, dict):
            for k, v in engines.items():
                if k not in breakdown_map and isinstance(v, dict):
                    breakdown_map[k] = v

        weights = risk_result.get("weights_used", {})

        explanation_factors: List[ProjectExplanationFactor] = []
        triggered_detectors: List[str] = []
        recommendations: List[str] = []

        for det in self.CANONICAL_DETECTOR_KEYS:
            det_data = breakdown_map.get(det)
            if det_data is None and det == "delay_detection":
                det_data = breakdown_map.get("delay")

            if det_data is not None:
                score = float(det_data.get("score", 0.0))
                weight = float(det_data.get("effective_weight", det_data.get("weight", weights.get(det, 0.20))))
                details = dict(det_data.get("details", {}))
                for field in ("actual_value", "expected_value", "reference_value", "threshold", "evidence", "unit"):
                    if field in det_data and field not in details:
                        details[field] = det_data[field]
                triggered = bool(det_data.get("triggered", details.get("triggered", score >= 30.0)))
                severity = _normalize_severity(str(det_data.get("severity", det_data.get("risk_level", _map_score_to_severity(score).value))))
                contrib = round(score * weight, 1)
                ev_list = self._extract_factor_evidence(det, details, score)
                rec = det_data.get("reason") or self.DETECTOR_RECOMMENDATIONS.get(det)
            else:
                score = 0.0
                weight = float(weights.get(det, 0.20))
                details = {}
                triggered = False
                severity = "low"
                contrib = 0.0
                ev_list = self._extract_factor_evidence(det, details, score)
                rec = self.DETECTOR_RECOMMENDATIONS.get(det)

            if triggered:
                triggered_detectors.append(det)
                if rec and rec not in recommendations:
                    recommendations.append(rec)

            ref_comp = self._get_detector_reference(det, details)
            thresh_raw = details.get("threshold") or self.DETECTOR_THRESHOLDS.get(det)
            thresh = str(thresh_raw) if thresh_raw is not None else None

            factor_model = ProjectExplanationFactor(
                name=self.FACTOR_DISPLAY_NAMES.get(det, det.replace("_", " ").title()),
                detector=det,
                triggered=triggered,
                severity=severity,
                contribution=contrib,
                detector_score=round(score, 1),
                weight=round(weight, 4),
                evidence=ev_list,
                threshold=thresh,
                reference_comparison=ref_comp,
                recommendation=rec,
                details=details,
            )
            explanation_factors.append(factor_model)

        explanation_factors.sort(key=lambda x: (not x.triggered, -x.contribution))

        if only_triggered:
            explanation_factors = [f for f in explanation_factors if f.triggered]

        summary = self._synthesize_explanation_summary(triggered_detectors)

        if not recommendations:
            recommendations.append("Continue routine quarterly milestone tracking and maintain regular monitoring reports.")

        score_decomposition = self._extract_decomposition_from_risk_result(risk_result)

        return ProjectExplanationResponse(
            project_id=project_id,
            risk_level=risk_level,
            risk_score=round(overall_score, 1),
            summary=summary,
            factors=explanation_factors,
            recommendations=recommendations,
            score_decomposition=score_decomposition,
        )

    def _synthesize_explanation_summary(self, triggered_detectors: List[str]) -> str:
        """
        Synthesizes an objective, non-accusatory summary string based strictly on triggered factors.
        Example: 'Project flagged due to cost anomaly, delay, and progress mismatch.'
        """
        names = [
            self.SUMMARY_FACTOR_NAMES.get(k, k.replace("_", " "))
            for k in triggered_detectors
            if k in self.SUMMARY_FACTOR_NAMES or k
        ]
        if not names:
            return "No significant risk factors were detected based on the configured detection thresholds."
        elif len(names) == 1:
            return f"Project flagged due to {names[0]}."
        elif len(names) == 2:
            return f"Project flagged due to {names[0]} and {names[1]}."
        else:
            return f"Project flagged due to {', '.join(names[:-1])}, and {names[-1]}."

    def _extract_factor_evidence(
        self,
        detector: str,
        details: Dict[str, Any],
        score: float,
    ) -> List[ProjectExplanationEvidence]:
        """Extracts structured ProjectExplanationEvidence items for a detector."""
        raw_ev = details.get("evidence")
        if isinstance(raw_ev, list) and len(raw_ev) > 0:
            extracted = []
            for item in raw_ev:
                if isinstance(item, dict) and "text" in item:
                    extracted.append(ProjectExplanationEvidence(
                        text=item["text"],
                        actual_value=item.get("actual_value"),
                        reference_value=item.get("reference_value"),
                        unit=item.get("unit"),
                    ))
            if extracted:
                return extracted

        if detector == "cost_anomaly":
            return self._extract_cost_anomaly_evidence(details, score)
        elif detector == "delay_detection":
            return self._extract_delay_evidence(details, score)
        elif detector == "progress_mismatch":
            return self._extract_progress_mismatch_evidence(details, score)
        elif detector == "duplicate_detection":
            return self._extract_duplicate_evidence(details, score)
        elif detector == "agency_pattern":
            return self._extract_agency_evidence(details, score)

        return [ProjectExplanationEvidence(
            text=f"{detector.replace('_', ' ').title()} evaluation completed within normal variance.",
            actual_value=None,
            reference_value=None,
            unit=None,
        )]

    def _extract_cost_anomaly_evidence(
        self,
        details: Dict[str, Any],
        score: float,
    ) -> List[ProjectExplanationEvidence]:
        """
        Extracts cost anomaly evidence statements and underlying numerical metrics.
        Input: evaluated_cost=25.6 crore (or 256,000,000 INR), peer_median=10.0 crore (or 100,000,000 INR)
        Output: text='Cost is 2.56× peer median.', actual_value=25.6, reference_value=10.0, unit='crore'
        """
        raw_cost = None
        for k in ("evaluated_cost", "project_expenditure", "sanctioned_amount"):
            v = details.get(k)
            if isinstance(v, (int, float)):
                raw_cost = float(v)
                break

        if raw_cost is None:
            act = details.get("actual_value")
            if isinstance(act, (int, float)):
                raw_cost = float(act)
            elif isinstance(act, str):
                num, u = parse_numerical_value(act)
                if num is not None:
                    raw_cost = num
                    if u and not details.get("unit"):
                        details["unit"] = u

        raw_median = None
        if isinstance(details.get("peer_median"), (int, float)):
            raw_median = float(details["peer_median"])
        else:
            ref = details.get("reference_value")
            if isinstance(ref, (int, float)):
                raw_median = float(ref)
            elif isinstance(ref, str):
                num, u = parse_numerical_value(ref)
                if num is not None:
                    raw_median = num

        unit = details.get("unit") or details.get("cost_unit")
        c_val = raw_cost
        m_val = raw_median

        if c_val is not None and m_val is not None and m_val > 0:
            if unit == "crore" or c_val >= 10_000_000 or m_val >= 10_000_000:
                eff_unit = "crore"
                scale = 10_000_000.0 if c_val >= 10_000_000 else 1.0
                act = round(c_val / scale, 2)
                ref = round(m_val / scale, 2)
            elif unit == "lakh" or c_val >= 100_000 or m_val >= 100_000:
                eff_unit = "lakh"
                scale = 100_000.0 if c_val >= 100_000 else 1.0
                act = round(c_val / scale, 2)
                ref = round(m_val / scale, 2)
            else:
                eff_unit = unit or "INR"
                act = round(c_val, 2)
                ref = round(m_val, 2)

            ratio = (c_val) / (m_val)
            if ratio >= 1.0:
                text = f"Cost is {ratio:.2f}× peer median."
            else:
                text = f"Cost is {round(ratio * 100, 1)}% of peer median."

            return [ProjectExplanationEvidence(
                text=text,
                actual_value=act,
                reference_value=ref,
                unit=eff_unit,
            )]
        elif c_val is not None:
            eff_unit = "crore" if c_val >= 10_000_000 else ("lakh" if c_val >= 100_000 else "INR")
            scale = 10_000_000.0 if eff_unit == "crore" else (100_000.0 if eff_unit == "lakh" else 1.0)
            return [ProjectExplanationEvidence(
                text=f"Project cost is {c_val / scale:.2f} {eff_unit}, peer median baseline unavailable.",
                actual_value=round(c_val / scale, 2),
                reference_value=None,
                unit=eff_unit,
            )]

        return [ProjectExplanationEvidence(
            text="Project cost is within expected category benchmarks.",
            actual_value=None,
            reference_value=None,
            unit=None,
        )]

    def _extract_delay_evidence(
        self,
        details: Dict[str, Any],
        score: float,
    ) -> List[ProjectExplanationEvidence]:
        """
        Extracts delay evidence statements and underlying duration metrics.
        Input: overdue_days=210
        Output: text='Project is delayed by 210 days.', actual_value=210, reference_value=0, unit='days'
        """
        overdue_days = None
        for k in ("overdue_days", "delay_days"):
            v = details.get(k)
            if v is not None:
                try:
                    overdue_days = int(float(v))
                    break
                except (ValueError, TypeError):
                    pass

        if overdue_days is None:
            act = details.get("actual_value")
            if isinstance(act, (int, float)):
                overdue_days = int(act)
            elif isinstance(act, str):
                num, _ = parse_numerical_value(act)
                if num is not None:
                    overdue_days = int(num)

        if overdue_days is not None:
            if overdue_days > 0:
                text = f"Project is delayed by {overdue_days} days."
            elif overdue_days == 0:
                text = "Project is on schedule."
            else:
                text = f"Project is ahead of schedule by {abs(overdue_days)} days."

            return [ProjectExplanationEvidence(
                text=text,
                actual_value=overdue_days,
                reference_value=0,
                unit="days",
            )]

        return [ProjectExplanationEvidence(
            text="Project execution timeline is within planned milestones.",
            actual_value=0,
            reference_value=0,
            unit="days",
        )]

    def _extract_progress_mismatch_evidence(
        self,
        details: Dict[str, Any],
        score: float,
    ) -> List[ProjectExplanationEvidence]:
        """
        Extracts financial vs physical progress mismatch evidence statements.
        Input: financial_progress=82%, physical_progress=35%
        Output: text='Financial progress exceeds physical progress by 47 percentage points.', actual_value=82.0, reference_value=35.0, unit='percentage points'
        """
        fp = details.get("financial_progress")
        if isinstance(fp, str):
            fp_num, _ = parse_numerical_value(fp)
            fp = fp_num
        pp = details.get("physical_progress")
        if isinstance(pp, str):
            pp_num, _ = parse_numerical_value(pp)
            pp = pp_num

        if fp is not None and pp is not None:
            fp_f = float(fp)
            pp_f = float(pp)
            if 0 < fp_f <= 1.0 and pp_f <= 1.0:
                fp_f = fp_f * 100.0
                pp_f = pp_f * 100.0

            diff = round(abs(fp_f - pp_f), 1)
            if fp_f > pp_f:
                text = f"Financial progress exceeds physical progress by {diff:g} percentage points."
            elif pp_f > fp_f:
                text = f"Physical progress exceeds financial progress by {diff:g} percentage points."
            else:
                text = "Financial progress matches physical progress."

            return [ProjectExplanationEvidence(
                text=text,
                actual_value=round(fp_f, 1),
                reference_value=round(pp_f, 1),
                unit="percentage points",
            )]

        return [ProjectExplanationEvidence(
            text="Financial expenditure and physical milestone progress are aligned.",
            actual_value=None,
            reference_value=None,
            unit="percentage points",
        )]

    def _extract_duplicate_evidence(
        self,
        details: Dict[str, Any],
        score: float,
    ) -> List[ProjectExplanationEvidence]:
        """
        Extracts duplicate text similarity evidence statements.
        Input: similarity=0.94, threshold=0.85, matched_project_id='XYZ'
        Output: text='Project description has 94% similarity with project XYZ, exceeding the 85% duplicate threshold.', actual_value=94.0, reference_value=85.0, unit='%'
        """
        sim = None
        for k in ("similarity", "adjusted_similarity", "raw_similarity"):
            v = details.get(k)
            if isinstance(v, (int, float)):
                sim = float(v)
                break

        if sim is None:
            act = details.get("actual_value")
            if isinstance(act, (int, float)):
                sim = float(act)
            elif isinstance(act, str):
                num, _ = parse_numerical_value(act)
                if num is not None:
                    sim = num

        thr = details.get("threshold", 0.85)
        if isinstance(thr, str):
            num, _ = parse_numerical_value(thr)
            thr = num if num is not None else 0.85

        matched_id = details.get("matched_project_id", "XYZ")

        if sim is not None:
            sim_f = float(sim)
            sim_pct = round(sim_f * 100.0 if sim_f <= 1.0 else sim_f, 1)
            thr_f = float(thr)
            thr_pct = round(thr_f * 100.0 if thr_f <= 1.0 else thr_f, 1)

            if sim_pct >= thr_pct:
                text = f"Project description has {sim_pct:g}% similarity with project {matched_id}, exceeding the {thr_pct:g}% duplicate threshold."
            else:
                text = f"Project description has {sim_pct:g}% similarity with project {matched_id}, within the {thr_pct:g}% duplicate threshold."

            return [ProjectExplanationEvidence(
                text=text,
                actual_value=sim_pct,
                reference_value=thr_pct,
                unit="%",
            )]

        return [ProjectExplanationEvidence(
            text="No duplicate project descriptions or overlapping work items identified.",
            actual_value=0.0,
            reference_value=85.0,
            unit="%",
        )]

    def _extract_agency_evidence(
        self,
        details: Dict[str, Any],
        score: float,
    ) -> List[ProjectExplanationEvidence]:
        """Extracts agency historical pattern evidence statements."""
        agency = details.get("agency_name", "implementing agency")
        delay_rate = details.get("delay_rate")
        if isinstance(delay_rate, str):
            num, _ = parse_numerical_value(delay_rate)
            delay_rate = num

        projects_analyzed = details.get("projects_analyzed", 0)
        if isinstance(projects_analyzed, str):
            num, _ = parse_numerical_value(projects_analyzed)
            projects_analyzed = int(num) if num is not None else 0

        insufficient = details.get("insufficient_history", False)

        if insufficient:
            return [ProjectExplanationEvidence(
                text=f"Agency '{agency}' has insufficient historical project records ({projects_analyzed} projects).",
                actual_value=projects_analyzed,
                reference_value=3,
                unit="projects",
            )]
        elif delay_rate is not None:
            dr_pct = round(float(delay_rate) * 100.0 if float(delay_rate) <= 1.0 else float(delay_rate), 1)
            agency_ref_pct = round(getattr(settings, 'AGENCY_DELAY_RATE_THRESHOLD', 0.50) * 100, 1)
            return [ProjectExplanationEvidence(
                text=f"Agency '{agency}' historical delay rate is {dr_pct:g}% across {projects_analyzed} projects.",
                actual_value=dr_pct,
                reference_value=agency_ref_pct,
                unit="%",
            )]

        agency_ref_pct = round(getattr(settings, 'AGENCY_DELAY_RATE_THRESHOLD', 0.50) * 100, 1)
        return [ProjectExplanationEvidence(
            text="Implementing agency historical track record is within normal parameters.",
            actual_value=0.0,
            reference_value=agency_ref_pct,
            unit="%",
        )]

    # -------------------------------------------------------------------------
    # Factor Builders
    # -------------------------------------------------------------------------

    def _build_engine_factor(
        self,
        key: str,
        det_data: Optional[Dict[str, Any]],
        score: float,
        weight: float,
        contribution: float,
        severity: SeverityLevel,
        triggered: bool,
        meta: Dict[str, Any],
    ) -> ExplanationFactor:
        """Dispatches factor generation to engine-specific builder."""
        details = det_data.get("details", {}) if det_data else {}
        reason = det_data.get("reason", "") if det_data else f"No analysis available for {key}."

        if key == "cost_anomaly":
            return self._build_cost_anomaly_factor(details, score, contribution, severity, triggered, meta, reason)
        elif key == "duplicate_detection":
            return self._build_duplicate_factor(details, score, contribution, severity, triggered, meta, reason)
        elif key == "delay_detection":
            return self._build_delay_factor(details, score, contribution, severity, triggered, meta, reason)
        elif key == "progress_mismatch":
            return self._build_mismatch_factor(details, score, contribution, severity, triggered, meta, reason)
        elif key == "agency_pattern":
            return self._build_agency_factor(details, score, contribution, severity, triggered, meta, reason)

        # Generic fallback
        return ExplanationFactor(
            factor_name=meta.get("factor_name", key.title()),
            detector_name=key,
            severity=severity,
            triggered_status=triggered,
            contribution_to_risk_score=contribution,
            threshold_used=meta.get("threshold_desc"),
            actual_value=str(score),
            expected_reference_value="Normal expected range",
            evidence=[],
            raw_evidence_dict=details,
            explanation_text=reason,
        )

    def _build_cost_anomaly_factor(
        self,
        details: Dict[str, Any],
        score: float,
        contribution: float,
        severity: SeverityLevel,
        triggered: bool,
        meta: Dict[str, Any],
        reason: str,
    ) -> ExplanationFactor:
        cost = details.get("evaluated_cost", details.get("project_expenditure", 0.0))
        median = details.get("peer_median", 0.0)
        dev_pct = details.get("deviation_percentage", 0.0)
        robust_z = details.get("robust_z_score", 0.0)
        overrun_pct = details.get("cost_overrun_pct", 0.0)
        sanctioned = details.get("sanctioned_amount", 0.0)
        scope = details.get("peer_scope", "peers").replace("_", " ")
        anomaly_type = details.get("anomaly_type", "NORMAL")

        actual_str = f"{_format_currency(cost)} ({dev_pct:+.1f}% vs {scope})"
        if overrun_pct > 0:
            actual_str += f", Overrun: +{overrun_pct:.1f}%"

        ref_str = f"Peer Median: {_format_currency(median)} (Sanctioned: {_format_currency(sanctioned)})"

        evidence_items = [
            EvidenceItem(
                metric_key="evaluated_cost",
                label="Evaluated Project Cost",
                actual_value=cost,
                formatted_value=_format_currency(cost),
                reference_value=median,
                formatted_reference=f"Peer Median: {_format_currency(median)}",
                unit="INR",
                context="Primary cost figure evaluated against category baseline.",
            ),
            EvidenceItem(
                metric_key="deviation_percentage",
                label="Cost Deviation",
                actual_value=dev_pct,
                formatted_value=f"{dev_pct:+.1f}%",
                reference_value=0.0,
                formatted_reference="0.0% (Aligned with median)",
                unit="%",
                context="Percentage difference from the statistical peer median.",
            ),
            EvidenceItem(
                metric_key="robust_z_score",
                label="Robust Z-Score (MAD)",
                actual_value=robust_z,
                formatted_value=f"{robust_z:.2f}",
                reference_value=1.5,
                formatted_reference="Normal limit: <= 1.50",
                unit="MAD-standardized",
                context="Outlier metric robust against extreme high/low skews.",
            ),
            EvidenceItem(
                metric_key="cost_overrun_pct",
                label="Cost Overrun vs Sanction",
                actual_value=overrun_pct,
                formatted_value=f"{overrun_pct:.1f}%",
                reference_value=0.0,
                formatted_reference="0.0% (Within approved sanction)",
                unit="%",
                context="Unapproved expenditures exceeding the legally sanctioned amount.",
            ),
        ]

        evidence_statements: List[EvidenceStatement] = []
        if cost and median:
            evidence_statements.append(self.evidence_generator.generate_cost_statement(cost, median))
        if sanctioned and (overrun_pct > 0 or cost > sanctioned):
            evidence_statements.append(
                self.evidence_generator.generate_cost_overrun_statement(cost, sanctioned, overrun_pct)
            )

        return ExplanationFactor(
            factor_name=meta["factor_name"],
            detector_name="cost_anomaly",
            severity=severity,
            triggered_status=triggered,
            contribution_to_risk_score=contribution,
            threshold_used=meta["threshold_desc"],
            actual_value=actual_str,
            expected_reference_value=ref_str,
            evidence=evidence_items,
            raw_evidence_dict=details,
            explanation_text=reason,
            evidence_statements=evidence_statements,
        )

    def _build_duplicate_factor(
        self,
        details: Dict[str, Any],
        score: float,
        contribution: float,
        severity: SeverityLevel,
        triggered: bool,
        meta: Dict[str, Any],
        reason: str,
    ) -> ExplanationFactor:
        matched_id = details.get("matched_project_id")
        sim = details.get("similarity", details.get("raw_similarity", 0.0))
        adj_sim = details.get("adjusted_similarity", sim)
        loc_match = details.get("location_match", "different")
        classification = details.get("duplicate_classification", "NONE")

        actual_str = f"{sim*100:.1f}% semantic similarity with project '{matched_id or 'None'}'"
        ref_str = "Duplicate threshold: >= 60.0% (Possible) / >= 75.0% (Strong)"

        evidence_items = [
            EvidenceItem(
                metric_key="matched_project_id",
                label="Nearest Match Project ID",
                actual_value=matched_id or "None",
                formatted_value=str(matched_id or "None"),
                reference_value=None,
                formatted_reference="No duplicate overlap",
                unit="ID",
                context="Closest matching historical project in scope or title.",
            ),
            EvidenceItem(
                metric_key="similarity",
                label="Semantic Text Similarity",
                actual_value=sim,
                formatted_value=f"{sim*100:.1f}%",
                reference_value=0.60,
                formatted_reference="Alert threshold: >= 60.0%",
                unit="cosine",
                context="Dense vector dot product between normalized descriptions.",
            ),
            EvidenceItem(
                metric_key="location_match",
                label="Geographical Proximity",
                actual_value=loc_match,
                formatted_value=str(loc_match).replace("_", " ").title(),
                reference_value=None,
                formatted_reference="Distant location dampens risk",
                unit="category",
                context="Same district elevates double-billing likelihood.",
            ),
            EvidenceItem(
                metric_key="duplicate_classification",
                label="Duplicate Classification",
                actual_value=classification,
                formatted_value=str(classification).replace("_", " "),
                reference_value="NONE",
                formatted_reference="NONE",
                unit="status",
                context="Operational risk category assigned to text overlap.",
            ),
        ]

        evidence_statements: List[EvidenceStatement] = []
        threshold = 0.85 if sim >= 0.85 else (0.75 if sim >= 0.75 else 0.60)
        evidence_statements.append(
            self.evidence_generator.generate_duplicate_statement(
                similarity_score=sim,
                threshold=threshold,
                matched_project_id=str(matched_id or "XYZ"),
            )
        )

        return ExplanationFactor(
            factor_name=meta["factor_name"],
            detector_name="duplicate_detection",
            severity=severity,
            triggered_status=triggered,
            contribution_to_risk_score=contribution,
            threshold_used=meta["threshold_desc"],
            actual_value=actual_str,
            expected_reference_value=ref_str,
            evidence=evidence_items,
            raw_evidence_dict=details,
            explanation_text=reason,
            evidence_statements=evidence_statements,
        )

    def _build_delay_factor(
        self,
        details: Dict[str, Any],
        score: float,
        contribution: float,
        severity: SeverityLevel,
        triggered: bool,
        meta: Dict[str, Any],
        reason: str,
    ) -> ExplanationFactor:
        overdue_days = int(details.get("overdue_days", 0))
        delay_pct = float(details.get("delay_percentage", 0.0))
        planned_dur = int(details.get("planned_duration", 0))
        exp_date = str(details.get("expected_completion_date", "N/A"))
        comp_status = str(details.get("completion_status", "ON_TRACK"))

        actual_str = f"{overdue_days} days overdue beyond planned completion (+{delay_pct:.1f}% delay)"
        ref_str = f"Planned duration: {planned_dur} days (Expected completion: {exp_date})"

        evidence_items = [
            EvidenceItem(
                metric_key="overdue_days",
                label="Days Overdue",
                actual_value=overdue_days,
                formatted_value=f"{overdue_days} days",
                reference_value=0,
                formatted_reference="0 days (On schedule)",
                unit="days",
                context="Calendar days elapsed beyond official planned completion date.",
            ),
            EvidenceItem(
                metric_key="delay_percentage",
                label="Schedule Slippage Ratio",
                actual_value=delay_pct,
                formatted_value=f"+{delay_pct:.1f}%",
                reference_value=0.0,
                formatted_reference="0.0% (Zero overrun)",
                unit="%",
                context="Percentage by which execution timeline exceeded planned schedule.",
            ),
            EvidenceItem(
                metric_key="planned_duration",
                label="Planned Project Duration",
                actual_value=planned_dur,
                formatted_value=f"{planned_dur} days",
                reference_value=planned_dur,
                formatted_reference=f"Target Date: {exp_date}",
                unit="days",
                context="Scheduled duration from sanction/work order to expected completion.",
            ),
            EvidenceItem(
                metric_key="completion_status",
                label="Timeline Delivery Status",
                actual_value=comp_status,
                formatted_value=comp_status.replace("_", " "),
                reference_value="ON_TRACK",
                formatted_reference="ON_TRACK",
                unit="status",
                context="Operational schedule classification.",
            ),
        ]

        evidence_statements: List[EvidenceStatement] = []
        evidence_statements.append(
            self.evidence_generator.generate_delay_statement(
                delay_days=overdue_days,
                planned_duration=planned_dur,
                expected_completion=exp_date if exp_date != "N/A" else None,
            )
        )

        return ExplanationFactor(
            factor_name=meta["factor_name"],
            detector_name="delay_detection",
            severity=severity,
            triggered_status=triggered,
            contribution_to_risk_score=contribution,
            threshold_used=meta["threshold_desc"],
            actual_value=actual_str,
            expected_reference_value=ref_str,
            evidence=evidence_items,
            raw_evidence_dict=details,
            explanation_text=reason,
            evidence_statements=evidence_statements,
        )

    def _build_mismatch_factor(
        self,
        details: Dict[str, Any],
        score: float,
        contribution: float,
        severity: SeverityLevel,
        triggered: bool,
        meta: Dict[str, Any],
        reason: str,
    ) -> ExplanationFactor:
        fp = float(details.get("financial_progress", 0.0))
        pp = float(details.get("physical_progress", 0.0))
        gap = float(details.get("progress_gap", 0.0))
        direction = str(details.get("direction", "aligned")).replace("_", " ").title()
        stage = str(details.get("current_stage", "Structure"))

        actual_str = f"Financial {fp:.1f}% vs Physical {pp:.1f}% ({gap:+.1f} percentage point gap, {direction})"
        ref_str = f"Acceptable alignment tolerance: ±10.0% (Current stage: '{stage}')"

        evidence_items = [
            EvidenceItem(
                metric_key="progress_gap",
                label="Progress Discrepancy Gap",
                actual_value=gap,
                formatted_value=f"{gap:+.1f} pts",
                reference_value=0.0,
                formatted_reference="±10.0% tolerance threshold",
                unit="percentage points",
                context="Discrepancy between recorded financial progress and verified physical milestone.",
            ),
            EvidenceItem(
                metric_key="financial_progress",
                label="Financial Progress",
                actual_value=fp,
                formatted_value=f"{fp:.1f}%",
                reference_value=pp,
                formatted_reference=f"Physical: {pp:.1f}%",
                unit="%",
                context="Cumulative financial utilization of released funds.",
            ),
            EvidenceItem(
                metric_key="physical_progress",
                label="Verified Physical Progress",
                actual_value=pp,
                formatted_value=f"{pp:.1f}%",
                reference_value=fp,
                formatted_reference=f"Financial: {fp:.1f}%",
                unit="%",
                context="On-site physical milestone completion verified by engineer.",
            ),
            EvidenceItem(
                metric_key="current_stage",
                label="Recorded Construction Stage",
                actual_value=stage,
                formatted_value=stage,
                reference_value=None,
                formatted_reference=None,
                unit="milestone",
                context="Current structural stage recorded in monitoring registry.",
            ),
        ]

        evidence_statements: List[EvidenceStatement] = []
        evidence_statements.append(
            self.evidence_generator.generate_progress_statement(
                financial_progress=fp,
                physical_progress=pp,
            )
        )

        return ExplanationFactor(
            factor_name=meta["factor_name"],
            detector_name="progress_mismatch",
            severity=severity,
            triggered_status=triggered,
            contribution_to_risk_score=contribution,
            threshold_used=meta["threshold_desc"],
            actual_value=actual_str,
            expected_reference_value=ref_str,
            evidence=evidence_items,
            raw_evidence_dict=details,
            explanation_text=reason,
            evidence_statements=evidence_statements,
        )

    def _build_agency_factor(
        self,
        details: Dict[str, Any],
        score: float,
        contribution: float,
        severity: SeverityLevel,
        triggered: bool,
        meta: Dict[str, Any],
        reason: str,
    ) -> ExplanationFactor:
        agency = str(details.get("agency_name", "N/A"))
        count = int(details.get("projects_analyzed", 0))
        delay_rate = float(details.get("delay_rate", 0.0))
        mismatch_rate = float(details.get("mismatch_rate", 0.0))
        cost_anom_rate = float(details.get("cost_anomaly_rate", 0.0))
        insufficient = bool(details.get("insufficient_history", False))

        if insufficient or count < 3:
            actual_str = f"{agency}: Only {count} historical projects analyzed (Insufficient history)"
            ref_str = "Requires at least 3 historical projects for statistical evaluation"
        else:
            actual_str = f"{agency}: {count} projects evaluated (Delay rate: {delay_rate*100:.1f}%, Progress gap rate: {mismatch_rate*100:.1f}%)"
            ref_str = "Healthy institutional benchmark: < 25.0% historical delay frequency"

        evidence_items = [
            EvidenceItem(
                metric_key="projects_analyzed",
                label="Historical Portfolio Size",
                actual_value=count,
                formatted_value=f"{count} projects",
                reference_value=3,
                formatted_reference=">= 3 projects required",
                unit="projects",
                context="Number of projects executed by this implementing agency in database.",
            ),
            EvidenceItem(
                metric_key="delay_rate",
                label="Historical Delay Rate",
                actual_value=delay_rate,
                formatted_value=f"{delay_rate*100:.1f}%",
                reference_value=0.25,
                formatted_reference="Normal benchmark: < 25.0%",
                unit="%",
                context="Proportion of historical projects that experienced schedule overruns.",
            ),
            EvidenceItem(
                metric_key="mismatch_rate",
                label="Historical Progress Mismatch Rate",
                actual_value=mismatch_rate,
                formatted_value=f"{mismatch_rate*100:.1f}%",
                reference_value=0.20,
                formatted_reference="Normal benchmark: < 20.0%",
                unit="%",
                context="Proportion of agency projects with notable financial/physical progress gaps.",
            ),
            EvidenceItem(
                metric_key="cost_anomaly_rate",
                label="Historical Cost Anomaly Rate",
                actual_value=cost_anom_rate,
                formatted_value=f"{cost_anom_rate*100:.1f}%",
                reference_value=0.10,
                formatted_reference="Normal benchmark: < 10.0%",
                unit="%",
                context="Proportion of agency projects flagged as significant cost outliers.",
            ),
        ]

        evidence_statements: List[EvidenceStatement] = []
        evidence_statements.append(
            self.evidence_generator.generate_agency_statement(
                agency_name=agency,
                projects_analyzed=count,
                delay_rate=delay_rate,
                insufficient_history=insufficient or count < 3,
            )
        )

        return ExplanationFactor(
            factor_name=meta["factor_name"],
            detector_name="agency_pattern",
            severity=severity,
            triggered_status=triggered,
            contribution_to_risk_score=contribution,
            threshold_used=meta["threshold_desc"],
            actual_value=actual_str,
            expected_reference_value=ref_str,
            evidence=evidence_items,
            raw_evidence_dict=details,
            explanation_text=reason,
            evidence_statements=evidence_statements,
        )

    # -------------------------------------------------------------------------
    # Recommendation Synthesis
    # -------------------------------------------------------------------------

    def _generate_recommendations(
        self,
        factors: List[ExplanationFactor],
        detector_map: Dict[str, Any],
        overall_score: float,
        project_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[RecommendationAction]:
        """Generates ranked, concrete administrative review action items."""
        actions: List[RecommendationAction] = []
        action_counter = 1

        for f in factors:
            det = f.detector_name
            sev_str = f.severity.value if hasattr(f.severity, "value") else str(f.severity)

            if f.triggered_status or sev_str in ("HIGH", "CRITICAL"):
                priority = ActionPriority.HIGH if sev_str == "CRITICAL" else ActionPriority.MEDIUM

                if det == "delay_detection":
                    actions.append(RecommendationAction(
                        action_id=f"REC-DELAY-{action_counter:02d}",
                        priority=priority,
                        category=ActionCategory.ADMINISTRATIVE,
                        recommendation=(
                            "Review contractor milestone logs and site engineering journals to determine "
                            "root causes of schedule slippage and verify formal extension approvals."
                        ),
                        target_detector="delay_detection",
                    ))
                    action_counter += 1

                elif det == "progress_mismatch":
                    actions.append(RecommendationAction(
                        action_id=f"REC-PROG-{action_counter:02d}",
                        priority=priority,
                        category=ActionCategory.FIELD_VERIFICATION,
                        recommendation=(
                            "Cross-reference physical measurement book (MB) records with financial payment vouchers "
                            "to reconcile disbursement lead over on-site milestone completion."
                        ),
                        target_detector="progress_mismatch",
                    ))
                    action_counter += 1

                elif det == "cost_anomaly":
                    actions.append(RecommendationAction(
                        action_id=f"REC-COST-{action_counter:02d}",
                        priority=priority,
                        category=ActionCategory.ENGINEERING,
                        recommendation=(
                            "Conduct an independent bill-of-quantities (BOQ) review against the standard schedule of "
                            "rates (SoR) to verify unit cost justification."
                        ),
                        target_detector="cost_anomaly",
                    ))
                    action_counter += 1

                elif det == "duplicate_detection":
                    matched_id = f.raw_evidence_dict.get("matched_project_id", "identified match")
                    actions.append(RecommendationAction(
                        action_id=f"REC-DUP-{action_counter:02d}",
                        priority=ActionPriority.HIGH,
                        category=ActionCategory.FIELD_VERIFICATION,
                        recommendation=(
                            f"Perform physical GPS coordinate verification and asset tagging to confirm project scope "
                            f"is distinct from project '{matched_id}'."
                        ),
                        target_detector="duplicate_detection",
                    ))
                    action_counter += 1

                elif det == "agency_pattern":
                    agency = f.raw_evidence_dict.get("agency_name", "implementing agency")
                    actions.append(RecommendationAction(
                        action_id=f"REC-AGENCY-{action_counter:02d}",
                        priority=ActionPriority.MEDIUM,
                        category=ActionCategory.ADMINISTRATIVE,
                        recommendation=(
                            f"Examine overall active workload, staffing capacity, and past completion track record of "
                            f"'{agency}' to identify systemic execution bottlenecks."
                        ),
                        target_detector="agency_pattern",
                    ))
                    action_counter += 1

        # Baseline governance check if no specific detector triggered
        if not actions:
            actions.append(RecommendationAction(
                action_id="REC-GEN-01",
                priority=ActionPriority.LOW,
                category=ActionCategory.COMPLIANCE,
                recommendation="Continue routine quarterly milestone tracking and maintain regular monitoring reports.",
                target_detector=None,
            ))

        return actions

    # -------------------------------------------------------------------------
    # UI Presentation Helpers
    # -------------------------------------------------------------------------

    def _generate_ui_display(
        self,
        factors: List[ExplanationFactor],
        overall_score: float,
        risk_level: str,
        detector_map: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generates pre-computed visual helpers for frontend dashboards."""
        # Color tokens
        color_map = {
            "LOW": "emerald",
            "MEDIUM": "amber",
            "HIGH": "orange",
            "CRITICAL": "rose",
        }
        risk_str = risk_level.value if hasattr(risk_level, "value") else str(risk_level)
        badge_color = color_map.get(risk_str, "slate")

        # Warning chips
        chips = []
        cards: List[Dict[str, Any]] = []

        for f in factors:
            meta = self.DETECTOR_METADATA.get(f.detector_name, {})
            sev_str = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
            det_color = color_map.get(sev_str, "slate")
            det_score = float(detector_map.get(f.detector_name, {}).get("score", 0.0))

            card = {
                "id": f.detector_name,
                "title": meta.get("display_name", f.detector_name),
                "badge_label": sev_str,
                "badge_color": det_color,
                "score": det_score,
                "contribution_points": f.contribution_to_risk_score,
                "primary_metric": f.actual_value or "Normal",
                "secondary_metric": f.expected_reference_value or "Baseline",
                "icon": meta.get("icon", "info"),
                "is_alert": f.triggered_status,
            }
            cards.append(card)

            if f.triggered_status:
                if f.detector_name == "delay_detection":
                    chips.append("Overdue Schedule")
                elif f.detector_name == "progress_mismatch":
                    chips.append("Progress Gap")
                elif f.detector_name == "cost_anomaly":
                    chips.append("Cost Elevation")
                elif f.detector_name == "duplicate_detection":
                    chips.append("Similar Proposal")
                elif f.detector_name == "agency_pattern":
                    chips.append("Agency Friction")

        return {
            "badge_color": badge_color,
            "badge_label": risk_level,
            "display_cards": cards,
            "warning_chips": chips,
            "score_progress_pct": min(100.0, max(0.0, overall_score)),
        }

    def _synthesize_summary(
        self,
        overall_score: float,
        risk_level: str,
        factors: List[ExplanationFactor],
    ) -> str:
        """Synthesizes deterministic executive summary."""
        triggered = [f for f in factors if f.triggered_status]
        if not triggered:
            return (
                f"Project exhibits {risk_level.lower()} overall risk (score {overall_score:.1f}/100, tier: {risk_level}). "
                "All evaluated financial, timeline, scope, and institutional metrics are within expected parameters."
            )

        top_names = [f.factor_name for f in triggered[:2]]
        factors_str = " and ".join(top_names)
        return (
            f"Project exhibits {risk_level.lower()} overall risk (score {overall_score:.1f}/100, tier: {risk_level}) "
            f"with notable contributions from {factors_str}. "
            "Routine operational verification is advised to maintain project trajectory."
        )


# Singleton instance for simple imports
explainability_service = ExplainabilityService()
