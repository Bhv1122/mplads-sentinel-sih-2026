"""
backend/app/services/risk/agency_pattern_engine.py
=============================================================================
Engine 5: Agency Pattern Detection Engine for MPLADS Projects.
=============================================================================

Implements the common BaseRiskEngine interface contract:
{
    "engine": "agency_pattern",
    "score": 0-100,
    "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
    "reason": "...",
    "details": {
        "projects_analyzed": 0,
        "delay_rate": 0.0,
        "cost_anomaly_rate": 0.0,
        "mismatch_rate": 0.0
    },
    "confidence": 0-1
}

Methodology & Audit Guardrails:
1. Entity Identification & Grouping:
   - Evaluates the responsible executing/implementing body.
   - Searches prioritized candidate fields on Project:
     implementing_agency -> executing_agency -> department -> contractor -> authority.
   - Trims whitespace and executes case-insensitive matching across agency fields.
2. Historical Portfolio Aggregation:
   - Queries all projects associated with the identified agency across the database.
   - Calculates aggregate institutional statistics:
     * projects_analyzed (N)
     * average_cost & median_cost
     * delay_rate: proportion of scheduled projects exceeding delivery milestones (> 30 days)
     * cost_anomaly_rate: proportion with cost overruns / budget deviations
     * mismatch_rate: proportion with financial-to-physical progress gaps (> 15%)
     * average_utilization: mean fund absorption rate
     * completion_rate: proportion of projects successfully delivered
     * high_risk_frequency: proportion of projects with multiple concurrent friction signals
     * auditable raw counts for delayed, anomalous, mismatched, and completed projects
3. Gating on Minimum Project Volume (min_projects):
   - Requires a configurable minimum project count (default >= 3) before making strong
     historical assertions.
   - If N < min_projects, score is strictly capped at <= 15 (LOW) and confidence is damped (<= 0.35),
     explaining that historical track record cannot yet be reliably profiled.
4. Small Sample Size Protection against False Positives:
   - If min_projects <= N < 5, score is capped at <= 55 (MEDIUM max), strictly preventing
     premature HIGH or CRITICAL risk classifications on limited sample sizes.
   - If 5 <= N < 10, score is capped at <= 75 (HIGH max), requiring N >= 10 for CRITICAL.
5. Distinction Between Agency History & Project Risk:
   - Explicitly separates the agency's institutional historical track record from
     the specific individual project's immediate state in the generated rationale.
6. Non-Accusatory Governance Tone:
   - Never claims fraud or corruption; characterizes findings as execution bottlenecks,
     delivery track record, and operational monitoring requirements.
"""

import logging
import statistics
from datetime import date
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

try:
    from app.config import settings
    from app.models.project import Project, Financial, Progress, ProjectFeature
    from app.schemas.risk_engine import RiskLevel, EngineResult
    from app.services.risk.engine_base import BaseRiskEngine
except ImportError:
    from backend.app.config import settings
    from backend.app.models.project import Project, Financial, Progress, ProjectFeature
    from backend.app.schemas.risk_engine import RiskLevel, EngineResult
    from backend.app.services.risk.engine_base import BaseRiskEngine

logger = logging.getLogger(__name__)


class AgencyPatternEngine(BaseRiskEngine):
    """
    Independent risk engine analyzing historical agency-level performance,
    systemic delay tendencies, cost deviation patterns, and portfolio delivery track record.
    """
    engine_name: str = "agency_pattern"
    version: str = "1.0.0"

    def __init__(
        self,
        min_projects: Optional[int] = None,
        delay_rate_threshold: Optional[float] = None,
        cost_anomaly_rate_threshold: Optional[float] = None,
        mismatch_rate_threshold: Optional[float] = None,
    ):
        """
        Initializes the agency pattern engine with configurable historical thresholds.
        Ensures default min_projects is at least 3 to prevent small-sample false alarms.
        """
        thresholds = self.get_engine_thresholds()
        raw_min = thresholds.get("default_count_threshold", 3)
        self.min_projects: int = (
            min_projects
            if min_projects is not None
            else max(3, int(raw_min))
        )
        self.delay_rate_threshold: float = (
            delay_rate_threshold
            if delay_rate_threshold is not None
            else float(thresholds.get("delay_rate_threshold", 0.40))
        )
        self.cost_anomaly_rate_threshold: float = (
            cost_anomaly_rate_threshold
            if cost_anomaly_rate_threshold is not None
            else float(thresholds.get("cost_overrun_rate_threshold", 0.25))
        )
        self.mismatch_rate_threshold: float = (
            mismatch_rate_threshold
            if mismatch_rate_threshold is not None
            else float(thresholds.get("mismatch_rate_threshold", 0.30))
        )
        self._agency_cache: Dict[str, Tuple[int, float, str, Dict[str, Any]]] = {}

    def clear_cache(self) -> None:
        """Clears the instance-level agency evaluation cache."""
        self._agency_cache.clear()

    def cache_size(self) -> int:
        """Returns the number of cached agency evaluations."""
        return len(self._agency_cache)

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
        Evaluates historical agency pattern risk for a project.
        """
        try:
            # 1. Resolve runtime thresholds
            min_projects = self.min_projects
            delay_thresh = self.delay_rate_threshold
            cost_thresh = self.cost_anomaly_rate_threshold
            mismatch_thresh = self.mismatch_rate_threshold

            if context:
                if "min_projects" in context:
                    min_projects = max(1, int(context["min_projects"]))
                elif "default_count_threshold" in context:
                    min_projects = max(1, int(context["default_count_threshold"]))
                if "delay_rate_threshold" in context:
                    delay_thresh = float(context["delay_rate_threshold"])
                if "cost_anomaly_rate_threshold" in context:
                    cost_thresh = float(context["cost_anomaly_rate_threshold"])
                if "mismatch_rate_threshold" in context:
                    mismatch_thresh = float(context["mismatch_rate_threshold"])

            # 2. Fetch project master record
            proj_stmt = select(Project).where(Project.project_id == project_id)
            project = db.execute(proj_stmt).scalar_one_or_none()

            if not project:
                return self.build_result(
                    score=0,
                    reason=f"Project '{project_id}' not found in database.",
                    details={
                        "projects_analyzed": 0,
                        "delay_rate": 0.0,
                        "cost_anomaly_rate": 0.0,
                        "mismatch_rate": 0.0,
                        "status": "not_found",
                        "error": "not_found",
                        "project_id": project_id,
                    },
                    confidence=0.0
                )

            # 3. Identify agency entity
            agency_name, agency_field = self._resolve_agency(project)

            if not agency_name:
                return self.build_result(
                    score=0,
                    reason="Implementing agency is not specified in project records; historical agency pattern cannot be evaluated.",
                    details={
                        "projects_analyzed": 0,
                        "delay_rate": 0.0,
                        "cost_anomaly_rate": 0.0,
                        "mismatch_rate": 0.0,
                        "agency_name": None,
                        "agency_field_used": None,
                        "missing_agency": True,
                        "project_id": project_id,
                    },
                    confidence=0.0
                )

            # 4. Fetch all projects handled by this agency (with caching)
            clean_name = agency_name.strip().lower()
            agency_cache = context.get("agency_cache") if context else None
            active_cache = agency_cache if agency_cache is not None else self._agency_cache

            if active_cache is not None and clean_name in active_cache:
                c_score, c_conf, c_reason, c_details = active_cache[clean_name]
                proj_details = dict(c_details)
                proj_details["agency_field_used"] = agency_field
                proj_details["project_id"] = project_id
                proj_details["agency_cached"] = True
                return self.build_result(
                    score=c_score,
                    reason=c_reason,
                    details=proj_details,
                    confidence=c_conf,
                )

            # Search across implementing_agency and any available agency columns with trimmed case-insensitive match
            conditions = [func.trim(func.lower(Project.implementing_agency)) == clean_name]
            for fallback_field in ("executing_agency", "department", "contractor", "authority"):
                if hasattr(Project, fallback_field):
                    conditions.append(func.trim(func.lower(getattr(Project, fallback_field))) == clean_name)

            portfolio_stmt = select(Project).where(or_(*conditions))
            raw_portfolio = db.execute(portfolio_stmt).scalars().all()

            # Deduplicate by project_id in case multiple candidate columns matched
            seen_pids = set()
            portfolio = []
            for p in raw_portfolio:
                if p.project_id not in seen_pids:
                    seen_pids.add(p.project_id)
                    portfolio.append(p)

            projects_analyzed = len(portfolio)

            if projects_analyzed == 0:
                # Agency has no recorded projects
                return self.build_result(
                    score=0,
                    reason=f"No historical records found for agency '{agency_name}'; pattern analysis cannot be conducted.",
                    details={
                        "projects_analyzed": 0,
                        "delay_rate": 0.0,
                        "cost_anomaly_rate": 0.0,
                        "mismatch_rate": 0.0,
                        "agency_name": agency_name,
                        "agency_field_used": agency_field,
                        "insufficient_history": True,
                        "project_id": project_id,
                    },
                    confidence=0.0
                )

            # 5. Extract portfolio project IDs and query associated records
            portfolio_pids = [p.project_id for p in portfolio]

            fin_records = {
                f.project_id: f
                for f in db.execute(
                    select(Financial).where(Financial.project_id.in_(portfolio_pids))
                ).scalars().all()
            }

            prog_records = {
                pr.project_id: pr
                for pr in db.execute(
                    select(Progress).where(Progress.project_id.in_(portfolio_pids))
                ).scalars().all()
            }

            # Reference date for schedule delay calculation
            ref_date = date.today()
            if context:
                for date_key in ("as_of_date", "reference_date", "status_date", "current_date"):
                    if date_key in context:
                        raw_as_of = context[date_key]
                        if isinstance(raw_as_of, date):
                            ref_date = raw_as_of
                            break
                        elif isinstance(raw_as_of, str):
                            try:
                                from datetime import datetime
                                ref_date = datetime.fromisoformat(raw_as_of.replace("Z", "+00:00")).date()
                                break
                            except Exception:
                                pass

            # 6. Aggregate portfolio statistical indicators
            stats = self._aggregate_portfolio_stats(
                portfolio=portfolio,
                fin_records=fin_records,
                prog_records=prog_records,
                ref_date=ref_date,
            )

            delay_rate = stats["delay_rate"]
            cost_anomaly_rate = stats["cost_anomaly_rate"]
            mismatch_rate = stats["mismatch_rate"]
            completion_rate = stats["completion_rate"]
            avg_cost = stats["average_cost"]
            med_cost = stats["median_cost"]
            avg_utilization = stats["average_utilization"]
            high_risk_frequency = stats["high_risk_frequency"]

            # 7. Check Gating: Minimum Project History Threshold
            if projects_analyzed < min_projects:
                score = min(15, int(round((delay_rate * 40.0 + cost_anomaly_rate * 30.0 + mismatch_rate * 30.0))))
                confidence = round(max(0.10, min(0.35, 0.35 * (projects_analyzed / float(max(1, min_projects))))), 2)
                reason = (
                    f"Insufficient historical project history for agency '{agency_name}' "
                    f"({projects_analyzed} project(s) analyzed; minimum threshold is {min_projects}); "
                    "historical agency pattern cannot be reliably established."
                )
                details = {
                    "projects_analyzed": projects_analyzed,
                    "delay_rate": delay_rate,
                    "cost_anomaly_rate": cost_anomaly_rate,
                    "mismatch_rate": mismatch_rate,
                    "average_cost": avg_cost,
                    "median_cost": med_cost,
                    "average_utilization": avg_utilization,
                    "completion_rate": completion_rate,
                    "high_risk_frequency": high_risk_frequency,
                    "agency_name": agency_name,
                    "agency_field_used": agency_field,
                    "min_projects_threshold": min_projects,
                    "insufficient_history": True,
                    "evidence": {
                        "total_projects": projects_analyzed,
                        "delayed_count": stats["delayed_count"],
                        "scheduled_count": stats["scheduled_count"],
                        "cost_anomaly_count": stats["cost_anomaly_count"],
                        "financial_evaluated_count": stats["financial_count"],
                        "mismatch_count": stats["mismatch_count"],
                        "progress_evaluated_count": stats["progress_count"],
                        "completed_count": stats["completed_count"],
                        "stalled_count": stats["stalled_count"],
                        "active_count": stats["active_count"],
                        "sample_size_status": "INSUFFICIENT",
                        "data_completeness_pct": stats["data_completeness_pct"],
                    },
                    "project_id": project_id,
                }
                return self.build_result(
                    score=score,
                    reason=reason,
                    details=details,
                    confidence=confidence,
                )

            # 8. Score Normalization for Agencies with Sufficient History
            score = self._score_agency_pattern(
                delay_rate=delay_rate,
                cost_anomaly_rate=cost_anomaly_rate,
                mismatch_rate=mismatch_rate,
                completion_rate=completion_rate,
                high_risk_freq=high_risk_frequency,
                delay_thresh=delay_thresh,
                cost_thresh=cost_thresh,
                mismatch_thresh=mismatch_thresh,
                projects_analyzed=projects_analyzed,
            )

            # 9. Diagnostic Confidence based on portfolio sample size and data completeness
            confidence = self._calculate_confidence(
                projects_analyzed=projects_analyzed,
                min_projects=min_projects,
                scheduled_count=stats["scheduled_count"],
                financial_count=stats["financial_count"],
                progress_count=stats["progress_count"],
            )

            is_limited = (projects_analyzed < 5)
            sample_status = "LIMITED" if is_limited else ("SUFFICIENT" if projects_analyzed < 10 else "ROBUST")

            # 10. Formulate Non-Accusatory Governance Explanation with concrete evidence
            reason = self._generate_explanation(
                agency_name=agency_name,
                projects_analyzed=projects_analyzed,
                delayed_count=stats["delayed_count"],
                delay_rate=delay_rate,
                cost_anomaly_count=stats["cost_anomaly_count"],
                cost_anomaly_rate=cost_anomaly_rate,
                mismatch_count=stats["mismatch_count"],
                mismatch_rate=mismatch_rate,
                completed_count=stats["completed_count"],
                completion_rate=completion_rate,
                score=score,
                is_limited_sample=is_limited,
            )

            details = {
                "projects_analyzed": projects_analyzed,
                "delay_rate": delay_rate,
                "cost_anomaly_rate": cost_anomaly_rate,
                "mismatch_rate": mismatch_rate,
                "average_cost": avg_cost,
                "median_cost": med_cost,
                "average_utilization": avg_utilization,
                "completion_rate": completion_rate,
                "high_risk_frequency": high_risk_frequency,
                "agency_name": agency_name,
                "agency_field_used": agency_field,
                "min_projects_threshold": min_projects,
                "insufficient_history": False,
                "evidence": {
                    "total_projects": projects_analyzed,
                    "delayed_count": stats["delayed_count"],
                    "scheduled_count": stats["scheduled_count"],
                    "cost_anomaly_count": stats["cost_anomaly_count"],
                    "financial_evaluated_count": stats["financial_count"],
                    "mismatch_count": stats["mismatch_count"],
                    "progress_evaluated_count": stats["progress_count"],
                    "completed_count": stats["completed_count"],
                    "stalled_count": stats["stalled_count"],
                    "active_count": stats["active_count"],
                    "sample_size_status": sample_status,
                    "data_completeness_pct": stats["data_completeness_pct"],
                },
                "project_id": project_id,
            }

            evidence_items = [
                {
                    "metric": "agency_projects_analyzed",
                    "label": "Projects Evaluated",
                    "value": projects_analyzed,
                    "formatted": f"{projects_analyzed} projects",
                },
                {
                    "metric": "agency_delay_rate",
                    "label": "Agency Delay Rate",
                    "value": round(delay_rate * 100, 1),
                    "formatted": f"{delay_rate*100:.1f}%",
                },
                {
                    "metric": "agency_mismatch_rate",
                    "label": "Agency Progress Mismatch Rate",
                    "value": round(mismatch_rate * 100, 1),
                    "formatted": f"{mismatch_rate*100:.1f}%",
                },
                {
                    "metric": "agency_cost_anomaly_rate",
                    "label": "Agency Cost Anomaly Rate",
                    "value": round(cost_anomaly_rate * 100, 1),
                    "formatted": f"{cost_anomaly_rate*100:.1f}%",
                },
                {
                    "metric": "peer_comparison",
                    "label": "Institutional Benchmark",
                    "value": 25.0,
                    "formatted": "< 25.0% expected",
                },
            ]

            if active_cache is not None:
                active_cache[clean_name] = (score, confidence, reason, details)
            self._agency_cache[clean_name] = (score, confidence, reason, details)

            return self.build_result(
                score=score,
                reason=reason,
                details=details,
                confidence=confidence,
                triggered=(score >= 30),
                threshold="Historical delay or mismatch rate > 25.0% (minimum 3 projects)",
                actual_value=f"{agency_name}: {projects_analyzed} projects evaluated (Delay rate: {delay_rate*100:.1f}%, Mismatch rate: {mismatch_rate*100:.1f}%)",
                expected_value="Healthy institutional benchmark: < 25.0% historical delay frequency",
                reference_value=f"Agency portfolio: {projects_analyzed} projects (Sample status: {sample_status})",
                evidence=evidence_items,
                metadata=details,
            )

        except Exception as e:
            logger.error(
                "AgencyPatternEngine failed for project '%s': %s",
                project_id, str(e), exc_info=True
            )
            return self.build_result(
                score=0,
                reason=f"Agency pattern analysis encountered runtime error: {str(e)}",
                details={
                    "projects_analyzed": 0,
                    "delay_rate": 0.0,
                    "cost_anomaly_rate": 0.0,
                    "mismatch_rate": 0.0,
                    "status": "error",
                    "error": str(e),
                    "project_id": project_id,
                },
                confidence=0.0
            )

    def evaluate_agency_portfolio(
        self,
        portfolio: List[Project],
        db: Session,
        agency_name: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates historical institutional performance for a given agency portfolio.
        """
        min_projects = self.min_projects
        delay_thresh = self.delay_rate_threshold
        cost_thresh = self.cost_anomaly_rate_threshold
        mismatch_thresh = self.mismatch_rate_threshold

        projects_analyzed = len(portfolio)
        if projects_analyzed == 0:
            return {
                "score": 0,
                "risk_level": "LOW",
                "confidence": 0.0,
                "reason": f"No historical records found for agency '{agency_name}'.",
                "stats": {
                    "delay_rate": 0.0,
                    "cost_anomaly_rate": 0.0,
                    "mismatch_rate": 0.0,
                    "completion_rate": 0.0,
                    "average_cost": 0.0,
                    "median_cost": 0.0,
                    "average_utilization": 0.0,
                    "delayed_count": 0,
                    "cost_anomaly_count": 0,
                    "mismatch_count": 0,
                    "completed_count": 0,
                },
            }

        portfolio_pids = [p.project_id for p in portfolio]
        fin_records = {
            f.project_id: f
            for f in db.execute(
                select(Financial).where(Financial.project_id.in_(portfolio_pids))
            ).scalars().all()
        }
        prog_records = {
            pr.project_id: pr
            for pr in db.execute(
                select(Progress).where(Progress.project_id.in_(portfolio_pids))
            ).scalars().all()
        }

        ref_date = date.today()
        stats = self._aggregate_portfolio_stats(
            portfolio=portfolio,
            fin_records=fin_records,
            prog_records=prog_records,
            ref_date=ref_date,
        )

        delay_rate = stats["delay_rate"]
        cost_anomaly_rate = stats["cost_anomaly_rate"]
        mismatch_rate = stats["mismatch_rate"]
        completion_rate = stats["completion_rate"]
        high_risk_frequency = stats["high_risk_frequency"]

        if projects_analyzed < min_projects:
            score = min(15, int(round((delay_rate * 40.0 + cost_anomaly_rate * 30.0 + mismatch_rate * 30.0))))
            confidence = round(max(0.10, min(0.35, 0.35 * (projects_analyzed / float(max(1, min_projects))))), 2)
            reason = (
                f"Insufficient historical project history for agency '{agency_name}' "
                f"({projects_analyzed} project(s) analyzed; minimum threshold is {min_projects}); "
                "historical agency pattern cannot be reliably established."
            )
        else:
            score = self._score_agency_pattern(
                delay_rate=delay_rate,
                cost_anomaly_rate=cost_anomaly_rate,
                mismatch_rate=mismatch_rate,
                completion_rate=completion_rate,
                high_risk_freq=high_risk_frequency,
                delay_thresh=delay_thresh,
                cost_thresh=cost_thresh,
                mismatch_thresh=mismatch_thresh,
                projects_analyzed=projects_analyzed,
            )
            confidence = self._calculate_confidence(
                projects_analyzed=projects_analyzed,
                min_projects=min_projects,
                scheduled_count=stats["scheduled_count"],
                financial_count=stats["financial_count"],
                progress_count=stats["progress_count"],
            )
            reason = self._generate_explanation(
                agency_name=agency_name,
                projects_analyzed=projects_analyzed,
                delayed_count=stats["delayed_count"],
                delay_rate=delay_rate,
                cost_anomaly_count=stats["cost_anomaly_count"],
                cost_anomaly_rate=cost_anomaly_rate,
                mismatch_count=stats["mismatch_count"],
                mismatch_rate=mismatch_rate,
                completed_count=stats["completed_count"],
                completion_rate=completion_rate,
                score=score,
                is_limited_sample=(projects_analyzed < 5),
            )

        risk_tier = self.calculate_risk_level(score).value
        return {
            "score": score,
            "risk_level": risk_tier,
            "confidence": confidence,
            "reason": reason,
            "stats": stats,
        }

    # -------------------------------------------------------------------------
    # Helper: Agency Entity Resolution
    # -------------------------------------------------------------------------

    @classmethod
    def _resolve_agency(cls, project: Project) -> Tuple[Optional[str], Optional[str]]:
        """
        Resolves the agency name through prioritized attribute inspection:
        implementing_agency -> executing_agency -> department -> contractor -> authority.
        """
        candidate_fields = (
            "implementing_agency",
            "executing_agency",
            "department",
            "contractor",
            "authority",
        )
        for field in candidate_fields:
            val = getattr(project, field, None)
            if val and isinstance(val, str) and val.strip():
                return val.strip(), field

        return None, None

    # -------------------------------------------------------------------------
    # Helper: Portfolio Statistical Aggregation
    # -------------------------------------------------------------------------

    @classmethod
    def _aggregate_portfolio_stats(
        cls,
        portfolio: List[Project],
        fin_records: Dict[str, Financial],
        prog_records: Dict[str, Progress],
        ref_date: date,
    ) -> Dict[str, Any]:
        """
        Computes portfolio-level delay, cost anomaly, progress gap rates, and raw counts.
        """
        n_total = len(portfolio)
        costs: List[float] = []
        utilizations: List[float] = []

        delayed_count = 0
        scheduled_count = 0

        cost_anomaly_count = 0
        financial_count = 0

        mismatch_count = 0
        progress_count = 0

        completed_count = 0
        stalled_count = 0
        active_count = 0
        multi_risk_count = 0

        for p in portfolio:
            pid = p.project_id
            status_clean = (p.current_status or "").strip().lower()
            is_comp = (
                status_clean in {"completed", "physically complete", "closed"}
                or p.actual_completion_date is not None
            )
            is_stalled = (status_clean in {"stalled", "stopped", "held up", "pending approval"})
            is_cancelled = (status_clean in {"cancelled", "dropped", "rejected"})

            if is_comp:
                completed_count += 1
            elif is_stalled:
                stalled_count += 1
            elif not is_cancelled:
                active_count += 1

            project_risk_signals = 0

            # 1. Cost & Financials
            fin = fin_records.get(pid)
            sanc = None
            spent = None
            rel = None

            if fin:
                sanc = float(fin.sanctioned_amount) if (fin.sanctioned_amount and float(fin.sanctioned_amount) > 0) else None
                spent = float(fin.expenditure_amount) if fin.expenditure_amount is not None else None
                rel = float(fin.released_amount) if (fin.released_amount and float(fin.released_amount) > 0) else None

                if sanc:
                    costs.append(sanc)

                if spent is not None and rel:
                    util = (spent / rel) * 100.0
                    utilizations.append(min(150.0, max(0.0, util)))

                if sanc and spent is not None:
                    financial_count += 1
                    # Anomaly: cost overrun or expenditure exceeding sanction by > 10%, or unreleased expenditure
                    has_overrun = (
                        (fin.cost_overrun_pct and float(fin.cost_overrun_pct) > 10.0)
                        or (spent > sanc * 1.10)
                        or (rel and spent > rel * 1.05)
                    )
                    if has_overrun:
                        cost_anomaly_count += 1
                        project_risk_signals += 1

            # 2. Schedule & Delays (skip cancelled/dropped projects)
            if not is_cancelled:
                exp_comp = p.expected_completion_date
                act_comp = p.actual_completion_date

                if exp_comp:
                    scheduled_count += 1
                    is_delayed = False
                    if is_comp and act_comp:
                        if (act_comp - exp_comp).days > 30:
                            is_delayed = True
                    elif not is_comp:
                        if (ref_date - exp_comp).days > 30:
                            is_delayed = True

                    if is_delayed:
                        delayed_count += 1
                        project_risk_signals += 1

            # 3. Progress Mismatch (with fallbacks for missing progress table records)
            prog = prog_records.get(pid)
            phy_pct = None
            fin_pct = None

            if prog:
                if prog.physical_progress_pct is not None:
                    phy_pct = float(prog.physical_progress_pct)
                if prog.financial_progress_pct is not None:
                    fin_pct = float(prog.financial_progress_pct)

            # Fallback physical progress for completed projects
            if phy_pct is None and is_comp:
                phy_pct = 100.0

            # Fallback financial progress from financial accounting if unrecorded in progress
            if fin_pct is None and fin:
                if spent is not None and sanc:
                    fin_pct = min(100.0, max(0.0, (spent / sanc) * 100.0))
                elif spent is not None and rel:
                    fin_pct = min(100.0, max(0.0, (spent / rel) * 100.0))

            if phy_pct is not None and fin_pct is not None:
                progress_count += 1
                if abs(fin_pct - phy_pct) > 15.0:
                    mismatch_count += 1
                    project_risk_signals += 1

            if project_risk_signals >= 2:
                multi_risk_count += 1

        # Rates calculation
        delay_rate = round(delayed_count / float(scheduled_count), 3) if scheduled_count > 0 else 0.0
        cost_anomaly_rate = round(cost_anomaly_count / float(financial_count), 3) if financial_count > 0 else 0.0
        mismatch_rate = round(mismatch_count / float(progress_count), 3) if progress_count > 0 else 0.0
        completion_rate = round((completed_count / float(n_total)) * 100.0, 1) if n_total > 0 else 0.0
        high_risk_frequency = round(multi_risk_count / float(n_total), 3) if n_total > 0 else 0.0

        avg_cost = round(statistics.mean(costs), 2) if costs else 0.0
        med_cost = round(statistics.median(costs), 2) if costs else 0.0
        avg_utilization = round(statistics.mean(utilizations), 1) if utilizations else 0.0

        data_completeness_pct = (
            round(((scheduled_count + financial_count + progress_count) / (3.0 * n_total)) * 100.0, 1)
            if n_total > 0
            else 0.0
        )

        return {
            "delay_rate": delay_rate,
            "cost_anomaly_rate": cost_anomaly_rate,
            "mismatch_rate": mismatch_rate,
            "completion_rate": completion_rate,
            "high_risk_frequency": high_risk_frequency,
            "average_cost": avg_cost,
            "median_cost": med_cost,
            "average_utilization": avg_utilization,
            "delayed_count": delayed_count,
            "scheduled_count": scheduled_count,
            "cost_anomaly_count": cost_anomaly_count,
            "financial_count": financial_count,
            "mismatch_count": mismatch_count,
            "progress_count": progress_count,
            "completed_count": completed_count,
            "stalled_count": stalled_count,
            "active_count": active_count,
            "data_completeness_pct": data_completeness_pct,
        }

    # -------------------------------------------------------------------------
    # Helper: Normalization Scoring (0-100) with Small-Sample Guardrails
    # -------------------------------------------------------------------------

    def _score_agency_pattern(
        self,
        delay_rate: float,
        cost_anomaly_rate: float,
        mismatch_rate: float,
        completion_rate: float,
        high_risk_freq: float,
        delay_thresh: float,
        cost_thresh: float,
        mismatch_thresh: float,
        projects_analyzed: int = 10,
    ) -> int:
        """
        Normalizes composite agency portfolio metrics into a standardized 0–100 risk score:
        - 0 to 29: LOW (healthy agency track record)
        - 30 to 59: MEDIUM (moderate historical variance / delivery friction)
        - 60 to 79: HIGH (elevated recurring delays / anomalies; requires N >= 5)
        - 80 to 100: CRITICAL (chronic delivery failure across portfolio; requires N >= 10)
        """
        # Normalized signal ratios relative to thresholds
        r_delay = delay_rate / max(0.01, delay_thresh)
        r_cost = cost_anomaly_rate / max(0.01, cost_thresh)
        r_mismatch = mismatch_rate / max(0.01, mismatch_thresh)

        # Baseline composite score (weights: delay 40%, cost 30%, mismatch 25%, completion 5%)
        delay_pts = min(40.0, r_delay * 20.0)
        cost_pts = min(30.0, r_cost * 15.0)
        mismatch_pts = min(25.0, r_mismatch * 12.5)

        # Incompletion penalty: lower completion rate adds up to 5 points
        incompletion_factor = max(0.0, (100.0 - completion_rate) / 100.0) * 5.0

        raw_score = delay_pts + cost_pts + mismatch_pts + incompletion_factor

        # Escalations for severe multi-signal stress
        if high_risk_freq >= 0.35:
            raw_score += 10.0
        elif high_risk_freq >= 0.20:
            raw_score += 5.0

        if delay_rate >= 0.70:
            raw_score = max(65.0, raw_score + 10.0)

        # Healthy agency bonus: if completion rate is high and delay rate is low
        if completion_rate >= 80.0 and delay_rate <= 0.15:
            raw_score = min(raw_score, 18.0)

        # Small sample size guardrails to prevent strong risk conclusions on few projects:
        # - If projects_analyzed < 5: cap score at 55 (MEDIUM max, cannot reach HIGH or CRITICAL)
        # - If projects_analyzed < 10: cap score at 75 (HIGH max, cannot reach CRITICAL)
        if projects_analyzed < 5:
            raw_score = min(55.0, raw_score)
        elif projects_analyzed < 10:
            raw_score = min(75.0, raw_score)

        return int(round(max(0.0, min(100.0, raw_score))))

    # -------------------------------------------------------------------------
    # Helper: Diagnostic Confidence
    # -------------------------------------------------------------------------

    @classmethod
    def _calculate_confidence(
        cls,
        projects_analyzed: int,
        min_projects: int,
        scheduled_count: int,
        financial_count: int,
        progress_count: int,
    ) -> float:
        """
        Calculates diagnostic confidence based on portfolio size and data completeness:
        - N < min_projects: 0.10 - 0.35 (insufficient sample)
        - min_projects <= N < 5: 0.50 - 0.65 (small sample)
        - 5 <= N < 10: 0.75 - 0.85 (moderate sample)
        - N >= 10: 0.90 - 0.95 (large, representative sample)
        """
        if projects_analyzed < min_projects:
            ratio = projects_analyzed / float(max(1, min_projects))
            return round(max(0.10, min(0.35, 0.35 * ratio)), 2)

        if projects_analyzed >= 15:
            base_conf = 0.95
        elif projects_analyzed >= 10:
            base_conf = 0.90
        elif projects_analyzed >= 5:
            base_conf = 0.85
        else:
            base_conf = 0.60

        expected_signals = projects_analyzed * 3.0
        actual_signals = scheduled_count + financial_count + progress_count
        completeness = actual_signals / max(1.0, expected_signals)

        if completeness < 0.75:
            base_conf = base_conf * max(0.5, completeness)

        return round(max(0.10, min(0.95, base_conf)), 2)

    # -------------------------------------------------------------------------
    # Helper: Non-Accusatory Governance Explanation
    # -------------------------------------------------------------------------

    @classmethod
    def _generate_explanation(
        cls,
        agency_name: str,
        projects_analyzed: int,
        delayed_count: Optional[int] = None,
        delay_rate: float = 0.0,
        cost_anomaly_count: Optional[int] = None,
        cost_anomaly_rate: float = 0.0,
        mismatch_count: Optional[int] = None,
        mismatch_rate: float = 0.0,
        completed_count: Optional[int] = None,
        completion_rate: float = 0.0,
        score: int = 0,
        is_limited_sample: bool = False,
    ) -> str:
        """
        Generates objective, non-accusatory governance text distinguishing
        agency history from individual project performance.
        Includes concrete counts alongside percentages for auditability.
        """
        if delayed_count is None:
            delayed_count = int(round(delay_rate * projects_analyzed))
        if cost_anomaly_count is None:
            cost_anomaly_count = int(round(cost_anomaly_rate * projects_analyzed))
        if mismatch_count is None:
            mismatch_count = int(round(mismatch_rate * projects_analyzed))
        if completed_count is None:
            completed_count = int(round((completion_rate / 100.0) * projects_analyzed))

        pct_del = f"{delay_rate * 100.0:.1f}%"
        pct_mismatch = f"{mismatch_rate * 100.0:.1f}%"
        pct_cost = f"{cost_anomaly_rate * 100.0:.1f}%"

        if is_limited_sample:
            return (
                f"Preliminary agency track record for '{agency_name}' indicates moderate variance "
                f"across {projects_analyzed} historical projects ({delayed_count} delayed [{pct_del}], "
                f"{mismatch_count} progress gaps [{pct_mismatch}]); limited sample size prevents strong "
                "institutional conclusions and is distinguished from current individual project delivery performance."
            )

        if score >= 80:
            return (
                f"Historical agency track record for '{agency_name}' indicates chronic delivery bottlenecks "
                f"across {projects_analyzed} historical projects ({delayed_count} delayed [{pct_del}], "
                f"{mismatch_count} progress gaps [{pct_mismatch}], {cost_anomaly_count} cost anomalies [{pct_cost}]); "
                "indicates systemic execution constraints requiring district-level administrative review."
            )
        elif score >= 60:
            return (
                f"Historical agency track record for '{agency_name}' exhibits elevated schedule delay frequency "
                f"across {projects_analyzed} historical projects ({delayed_count} delayed [{pct_del}], "
                f"{mismatch_count} progress gaps [{pct_mismatch}], {cost_anomaly_count} cost anomalies [{pct_cost}]); "
                "indicates recurring delivery friction requiring operational monitoring."
            )
        elif score >= 30:
            return (
                f"Historical agency track record for '{agency_name}' shows moderate variance "
                f"across {projects_analyzed} historical projects ({delayed_count} delayed [{pct_del}], "
                f"{cost_anomaly_count} cost anomalies [{pct_cost}], {mismatch_count} progress gaps [{pct_mismatch}]); "
                "distinguished from current individual project delivery performance."
            )
        else:
            return (
                f"Agency '{agency_name}' exhibits a consistent historical execution track record "
                f"across {projects_analyzed} analyzed projects ({completed_count} completed [{completion_rate:.1f}%], "
                f"{delayed_count} delayed [{pct_del}], {cost_anomaly_count} cost anomalies) within normal governance parameters."
            )
