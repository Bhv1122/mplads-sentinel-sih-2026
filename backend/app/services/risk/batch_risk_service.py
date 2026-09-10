"""
backend/app/services/risk/batch_risk_service.py
=============================================================================
Batch-Processing Service for Calculating Risk Across the Complete MPLADS Dataset.
=============================================================================

Pipeline Architecture:
    Load project & metadata
    ↓
    Engine 1 — Cost Anomaly Engine
    ↓
    Engine 2 — Duplicate Detection Engine (with cached embeddings & pre-warmed candidate pool)
    ↓
    Engine 3 — Delay Detection Engine
    ↓
    Engine 4 — Financial/Physical Progress Mismatch Engine
    ↓
    Engine 5 — Agency Pattern Engine (with shared in-memory agency statistics cache)
    ↓
    Central Risk Aggregation (weighted composite score 0–100, risk tiers)
    ↓
    Engine 6 — Explained Risk Engine (ranked factor contribution & evidence narrative)
    ↓
    PostgreSQL Persistence (atomic upsert of RiskScore and all 6 RiskFactor records)

Features:
- Execution Scopes: Single project, selected project IDs, or all projects in database.
- Database Query Minimization: Pre-fetches candidate pools and distinct agency metadata.
- Embedding Reuse: Reuses in-memory vector cache across the entire batch run.
- Zero Agency Redundancy: Caches expensive agency statistics per agency name.
- Fault Tolerance: Per-project transaction isolation; a failure in one project rolls back
  its own transaction and logs the failure without stopping the batch.
- Comprehensive Summary: Tracks processed, successful, failed, risk tiers (LOW, MEDIUM,
  HIGH, CRITICAL), execution time, and failure details.
"""

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional, List, Tuple, Union
from pydantic import BaseModel, Field

from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

try:
    from app.config import settings
    from app.database import SessionLocal
    from app.models.project import Project, RiskScore, RiskFactor
    from app.services.risk.duplicate_detection_engine import DuplicateDetectionEngine
    from app.services.risk.agency_pattern_engine import AgencyPatternEngine
except ImportError:
    from backend.app.config import settings
    from backend.app.database import SessionLocal
    from backend.app.models.project import Project, RiskScore, RiskFactor
    from backend.app.services.risk.duplicate_detection_engine import DuplicateDetectionEngine
    from backend.app.services.risk.agency_pattern_engine import AgencyPatternEngine

logger = logging.getLogger(__name__)


# =============================================================================
# Batch Processing Summary Schema
# =============================================================================

class FailedProjectDetail(BaseModel):
    """Details of a project that encountered an unrecoverable failure during batch run."""
    project_id: str
    error: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BatchRiskSummary(BaseModel):
    """
    Standardized execution summary returned at the conclusion of a batch risk run.
    """
    projects_processed: int = 0
    successful: int = 0
    failed: int = 0
    low: int = 0
    medium: int = 0
    high: int = 0
    critical: int = 0
    average_score: float = 0.0
    execution_time_seconds: float = 0.0
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    failed_projects: List[FailedProjectDetail] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to standard dictionary."""
        return {
            "projects_processed": self.projects_processed,
            "successful": self.successful,
            "failed": self.failed,
            "low": self.low,
            "medium": self.medium,
            "high": self.high,
            "critical": self.critical,
            "average_score": round(self.average_score, 2),
            "execution_time_seconds": round(self.execution_time_seconds, 2),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "failed_projects": [f.model_dump() for f in self.failed_projects],
        }

    def format_ascii_report(self) -> str:
        """Renders an ASCII text report for console, terminal, or log output."""
        duration_str = f"{self.execution_time_seconds:.2f}s"
        total = max(1, self.projects_processed)
        success_pct = (self.successful / total) * 100.0
        fail_pct = (self.failed / total) * 100.0

        low_pct = (self.low / total) * 100.0 if self.successful > 0 else 0.0
        med_pct = (self.medium / total) * 100.0 if self.successful > 0 else 0.0
        high_pct = (self.high / total) * 100.0 if self.successful > 0 else 0.0
        crit_pct = (self.critical / total) * 100.0 if self.successful > 0 else 0.0

        lines = [
            "================================================================================",
            "                        MPLADS BATCH RISK PROCESSING SUMMARY                    ",
            "================================================================================",
            f"  Projects Processed   : {self.projects_processed:,}",
            f"  Successful           : {self.successful:,} ({success_pct:.1f}%)",
            f"  Failed               : {self.failed:,} ({fail_pct:.1f}%)",
            f"  Average Risk Score   : {self.average_score:.2f} / 100",
            f"  Execution Time       : {duration_str}",
            f"  Started At           : {self.started_at}",
            f"  Completed At         : {self.completed_at}",
            "--------------------------------------------------------------------------------",
            "  RISK TIER BREAKDOWN (Successful Projects):",
            f"    - LOW      ( 0–29) : {self.low:4d}  ({low_pct:5.1f}%)",
            f"    - MEDIUM   (30–59) : {self.medium:4d}  ({med_pct:5.1f}%)",
            f"    - HIGH     (60–79) : {self.high:4d}  ({high_pct:5.1f}%)",
            f"    - CRITICAL (80–100): {self.critical:4d}  ({crit_pct:5.1f}%)",
            "================================================================================",
        ]

        if self.failed_projects:
            lines.append("  FAILED PROJECTS LIST:")
            for item in self.failed_projects[:10]:
                lines.append(f"    * {item.project_id}: {item.error}")
            if len(self.failed_projects) > 10:
                lines.append(f"    ... and {len(self.failed_projects) - 10} more.")
            lines.append("================================================================================")

        return "\n".join(lines)


# =============================================================================
# Batch Risk Service Implementation
# =============================================================================

class BatchRiskService:
    """
    Orchestrates batch risk calculation across the entire MPLADS dataset
    or selected projects with query minimization, embedding reuse, and fault tolerance.
    """

    def __init__(
        self,
        risk_engine: Optional[Any] = None,
        db_session_factory=SessionLocal,
    ):
        """
        Initializes the batch risk processing service.
        """
        self._risk_engine = risk_engine
        self.db_session_factory = db_session_factory

    @property
    def risk_engine(self) -> Any:
        """Lazily instantiates central RiskEngine upon first use."""
        if self._risk_engine is None:
            try:
                from app.services.risk_engine import RiskEngine
            except ImportError:
                from backend.app.services.risk_engine import RiskEngine
            self._risk_engine = RiskEngine()
        return self._risk_engine

    @risk_engine.setter
    def risk_engine(self, value: Any):
        self._risk_engine = value

    # -------------------------------------------------------------------------
    # Optimization & Context Helpers
    # -------------------------------------------------------------------------

    def _prepare_shared_context(
        self,
        db: Session,
        project_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Pre-loads shared read-only data across projects to eliminate redundant queries:
        1. Duplicate candidate corpus (normalized text pool for semantic comparison)
        2. In-memory agency statistics cache to prevent duplicate agency calculations
        """
        logger.info("Initializing batch processing context and optimization caches...")
        start_t = time.perf_counter()

        # 1. Fetch candidate corpus for duplicate detection once
        cand_stmt = select(
            Project.project_id,
            Project.project_title,
            Project.project_description,
            Project.sector,
            Project.sub_sector,
            Project.state_id,
            Project.district_name,
            Project.block_name,
        )
        cand_rows = db.execute(cand_stmt).all()
        prepared_candidates = DuplicateDetectionEngine.prepare_candidate_pool(cand_rows)

        # 2. Shared in-memory agency statistics cache
        # Mapping: clean_agency_name -> (score, confidence, reason, details)
        agency_cache: Dict[str, Tuple[int, float, str, Dict[str, Any]]] = {}

        elapsed = time.perf_counter() - start_t
        logger.info(
            "Batch context ready: %d candidates preloaded, embedding cache size=%d (%0.2fs)",
            len(prepared_candidates),
            DuplicateDetectionEngine.cache_size(),
            elapsed,
        )

        return {
            "candidates": prepared_candidates,
            "agency_cache": agency_cache,
            "batch_mode": True,
        }

    # -------------------------------------------------------------------------
    # Core Evaluation Pipeline
    # -------------------------------------------------------------------------

    def process_project(
        self,
        project_id: str,
        db: Optional[Session] = None,
        persist: bool = True,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Processes a single project through the full 6-engine risk pipeline.
        
        Order of operations:
            1. Load project & related data
            2. Engine 1 — Cost Anomaly
            3. Engine 2 — Duplicate Detection (reusing cached embeddings)
            4. Engine 3 — Delay Detection
            5. Engine 4 — Financial/Physical Progress Mismatch
            6. Engine 5 — Agency Pattern (reusing cached agency stats)
            7. Central Risk Aggregation
            8. Engine 6 — Explanation
            9. PostgreSQL Persistence (if persist=True)

        Returns the full evaluation dictionary conforming to RiskEngineResult.
        """
        own_session = False
        if db is None:
            db = self.db_session_factory()
            own_session = True

        try:
            # Build local context if none provided
            if context is None:
                context = self._prepare_shared_context(db=db, project_ids=[project_id])

            # Evaluate via central RiskEngine
            result = self.risk_engine.evaluate(
                project_id=project_id,
                db=db,
                persist=persist,
                context=context,
            )

            if own_session and persist:
                db.commit()

            return result

        except Exception as e:
            if own_session:
                db.rollback()
            logger.error("Error processing risk for project '%s': %s", project_id, str(e), exc_info=True)
            raise
        finally:
            if own_session:
                db.close()

    def process_selected(
        self,
        project_ids: List[str],
        db: Optional[Session] = None,
        persist: bool = True,
        chunk_size: int = 50,
    ) -> BatchRiskSummary:
        """
        Executes the batch risk pipeline for an explicit list of project identifiers.
        Guarantees fault isolation: an error in one project does not crash the batch.
        """
        return self._execute_batch(
            project_ids=project_ids,
            db=db,
            persist=persist,
            chunk_size=chunk_size,
        )

    def process_all(
        self,
        db: Optional[Session] = None,
        persist: bool = True,
        chunk_size: int = 50,
    ) -> BatchRiskSummary:
        """
        Executes the batch risk pipeline for ALL projects currently in the database.
        """
        own_session = False
        if db is None:
            db = self.db_session_factory()
            own_session = True

        try:
            # Discover all project IDs ordered deterministically
            stmt = select(Project.project_id).order_by(Project.recommendation_date.desc(), Project.project_id)
            all_ids = [str(r[0]) for r in db.execute(stmt).all()]
            logger.info("Found %d total projects in database for batch risk processing.", len(all_ids))

            return self._execute_batch(
                project_ids=all_ids,
                db=db,
                persist=persist,
                chunk_size=chunk_size,
            )
        finally:
            if own_session:
                db.close()

    # -------------------------------------------------------------------------
    # Internal Batch Execution Driver
    # -------------------------------------------------------------------------

    def _execute_batch(
        self,
        project_ids: List[str],
        db: Optional[Session] = None,
        persist: bool = True,
        chunk_size: int = 50,
    ) -> BatchRiskSummary:
        """
        Underlying execution loop with transaction isolation, progress tracking,
        and statistical summary generation.
        """
        summary = BatchRiskSummary()
        summary.started_at = datetime.now(timezone.utc).isoformat()
        summary.projects_processed = len(project_ids)

        start_time = time.perf_counter()
        total_projects = len(project_ids)

        if total_projects == 0:
            summary.completed_at = datetime.now(timezone.utc).isoformat()
            summary.execution_time_seconds = 0.0
            logger.info("Batch execution finished: 0 projects provided.")
            return summary

        own_session = False
        if db is None:
            db = self.db_session_factory()
            own_session = True

        total_score_accum = 0.0

        try:
            # 1. Initialize shared optimization context once for the entire batch
            context = self._prepare_shared_context(db=db, project_ids=project_ids)

            logger.info(
                "Starting batch risk processing for %d projects (persist=%s, chunk_size=%d)...",
                total_projects,
                persist,
                chunk_size,
            )

            # 2. Iterate through projects with per-project exception containment
            for idx, pid in enumerate(project_ids, start=1):
                try:
                    # Evaluate project through all 6 engines
                    res = self.risk_engine.evaluate(
                        project_id=pid,
                        db=db,
                        persist=persist,
                        context=context,
                    )

                    score = float(res.get("overall_score", res.get("overall_risk_score", 0.0)))
                    tier = str(res.get("risk_level", "LOW")).upper()

                    # Commit project changes immediately or flush per chunk
                    if persist:
                        db.commit()

                    summary.successful += 1
                    total_score_accum += score

                    # Map tier count
                    if tier == "CRITICAL" or score >= 80.0:
                        summary.critical += 1
                    elif tier == "HIGH" or score >= 60.0:
                        summary.high += 1
                    elif tier in ("MEDIUM", "MODERATE") or score >= 30.0:
                        summary.medium += 1
                    else:
                        summary.low += 1

                    # Log milestone progress
                    progress_pct = (idx / total_projects) * 100.0
                    logger.info(
                        "[%d/%d (%.1f%%)] Project '%s' evaluated -> Score: %.1f, Tier: %s (Agency cached: %s)",
                        idx,
                        total_projects,
                        progress_pct,
                        pid,
                        score,
                        tier,
                        res.get("evidence", {}).get("agency_pattern", {}).get("agency_cached", False)
                    )

                except Exception as proj_err:
                    # Project failure isolation: rollback only this project and proceed
                    if persist:
                        try:
                            db.rollback()
                        except Exception:
                            pass

                    summary.failed += 1
                    error_msg = str(proj_err)
                    logger.error(
                        "[%d/%d] Project '%s' failed in batch: %s",
                        idx,
                        total_projects,
                        pid,
                        error_msg,
                        exc_info=True,
                    )
                    summary.failed_projects.append(
                        FailedProjectDetail(project_id=pid, error=error_msg)
                    )

            # 3. Finalize timing and statistical summary
            end_time = time.perf_counter()
            summary.execution_time_seconds = end_time - start_time
            summary.completed_at = datetime.now(timezone.utc).isoformat()

            if summary.successful > 0:
                summary.average_score = round(total_score_accum / summary.successful, 2)
            else:
                summary.average_score = 0.0

            # Log formatted report
            logger.info("\n" + summary.format_ascii_report())

            return summary

        finally:
            if own_session:
                db.close()


# Module-level default singleton instance
batch_risk_service = BatchRiskService()
