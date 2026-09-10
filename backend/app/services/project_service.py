"""
backend/app/services/project_service.py
=============================================================================
Business logic and database access layer for MPLADS project lifecycle.
=============================================================================
"""

import math
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select, func, desc, asc, text, or_, and_
from sqlalchemy.orm import Session, joinedload, selectinload

try:
    from app.models.project import (
        State,
        Constituency,
        Project,
        Financial,
        Progress,
        RiskScore,
        RiskFactor,
        ProjectHistory,
        ProjectFeature,
        ProjectSnapshot,
        RiskHistory
    )
    from app.schemas.project import (
        ProjectCreate,
        ProjectUpdate,
        ProjectSummary,
        ProjectDetail,
        PaginatedResponse,
        ProjectHistoryRead,
        ProgressRead,
        ProjectFeatureRead
    )
    from app.schemas.history import (
        ProjectSnapshotRead,
        RiskHistoryRead,
        ProjectChangeRecord,
        FieldChangeItem
    )
except ImportError:
    from backend.app.models.project import (
        State,
        Constituency,
        Project,
        Financial,
        Progress,
        RiskScore,
        RiskFactor,
        ProjectHistory,
        ProjectFeature,
        ProjectSnapshot,
        RiskHistory
    )
    from backend.app.schemas.project import (
        ProjectCreate,
        ProjectUpdate,
        ProjectSummary,
        ProjectDetail,
        PaginatedResponse,
        ProjectHistoryRead,
        ProgressRead,
        ProjectFeatureRead
    )
    from backend.app.schemas.history import (
        ProjectSnapshotRead,
        RiskHistoryRead,
        ProjectChangeRecord,
        FieldChangeItem
    )


class ProjectService:

    @staticmethod
    def list_projects(
        db: Session,
        skip: int = 0,
        limit: int = 20,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        state_id: Optional[int] = None,
        district_name: Optional[str] = None,
        constituency_id: Optional[int] = None,
        sector: Optional[str] = None,
        current_status: Optional[str] = None,
        mp_name: Optional[str] = None,
        house_of_parliament: Optional[str] = None,
        implementing_agency: Optional[str] = None,
        financial_year: Optional[str] = None,
        min_sanctioned: Optional[Decimal] = None,
        max_sanctioned: Optional[Decimal] = None,
        delayed_only: Optional[bool] = None,
        min_risk_score: Optional[Decimal] = None,
        risk_level: Optional[str] = None,
        q: Optional[str] = None,
        sort_by: str = "recommendation_date",
        sort_order: str = "desc"
    ) -> PaginatedResponse[ProjectSummary]:
        """
        Retrieves a paginated list of projects from PostgreSQL with multi-criteria
        filtering, skip/limit pagination, full-text search, and relational aggregations.
        Handles empty result sets cleanly.
        """
        if page is not None and (skip == 0 or page > 1):
            effective_limit = page_size if page_size is not None else limit
            effective_limit = max(1, min(100, effective_limit))
            effective_skip = (max(1, page) - 1) * effective_limit
            effective_page = max(1, page)
            effective_page_size = effective_limit
        else:
            effective_skip = max(0, skip)
            effective_limit = max(1, min(100, limit))
            effective_page = (effective_skip // effective_limit) + 1
            effective_page_size = effective_limit

        # Latest progress subquery per project
        latest_progress_subq = (
            select(
                Progress.project_id,
                Progress.physical_progress_pct,
                Progress.days_delayed,
                Progress.milestone_status
            )
            .distinct(Progress.project_id)
            .order_by(Progress.project_id, desc(Progress.reported_date))
            .subquery("latest_progress")
        )

        # Base query joining project with state, financials, latest progress, and risk scores
        query = (
            select(
                Project.project_id,
                Project.project_code,
                Project.project_title,
                Project.sector,
                State.state_name,
                Project.district_name,
                Project.mp_name,
                Project.current_status,
                Project.financial_year,
                Financial.sanctioned_amount,
                Financial.released_amount,
                Financial.expenditure_amount,
                latest_progress_subq.c.physical_progress_pct,
                func.coalesce(latest_progress_subq.c.days_delayed, 0).label("days_delayed"),
                RiskScore.overall_risk_score,
                RiskScore.risk_level
            )
            .join(State, Project.state_id == State.state_id)
            .outerjoin(Financial, Project.project_id == Financial.project_id)
            .outerjoin(latest_progress_subq, Project.project_id == latest_progress_subq.c.project_id)
            .outerjoin(RiskScore, Project.project_id == RiskScore.project_id)
        )

        # Filters
        filters = []
        if state_id:
            filters.append(Project.state_id == state_id)
        if district_name:
            filters.append(Project.district_name.ilike(f"%{district_name}%"))
        if constituency_id:
            filters.append(Project.constituency_id == constituency_id)
        if sector:
            filters.append(Project.sector == sector)
        if current_status:
            filters.append(Project.current_status == current_status)
        if mp_name:
            filters.append(Project.mp_name.ilike(f"%{mp_name}%"))
        if house_of_parliament:
            filters.append(Project.house_of_parliament == house_of_parliament)
        if implementing_agency:
            filters.append(Project.implementing_agency.ilike(f"%{implementing_agency}%"))
        if financial_year:
            filters.append(Project.financial_year == financial_year)
        if min_sanctioned is not None:
            filters.append(Financial.sanctioned_amount >= min_sanctioned)
        if max_sanctioned is not None:
            filters.append(Financial.sanctioned_amount <= max_sanctioned)
        if delayed_only:
            filters.append(or_(
                latest_progress_subq.c.days_delayed > 0,
                latest_progress_subq.c.milestone_status.in_(["Delayed", "Critical"]),
                Project.current_status == "Stalled"
            ))
        if min_risk_score is not None:
            filters.append(RiskScore.overall_risk_score >= min_risk_score)
        if risk_level:
            filters.append(RiskScore.risk_level == risk_level)

        # Full-text and keyword search
        search_rank_col = None
        if q and q.strip():
            clean_q = q.strip()
            # Check if websearch_to_tsquery matches, or fallback to ILIKE substring matching
            fts_filter = text("projects.search_vector @@ websearch_to_tsquery('english', :q_fts)")
            ilike_filter = or_(
                Project.project_id.ilike(f"%{clean_q}%"),
                Project.project_code.ilike(f"%{clean_q}%"),
                Project.project_title.ilike(f"%{clean_q}%"),
                Project.mp_name.ilike(f"%{clean_q}%"),
                Project.implementing_agency.ilike(f"%{clean_q}%")
            )
            filters.append(or_(fts_filter, ilike_filter))
            search_rank_col = func.ts_rank(
                text("projects.search_vector"),
                func.websearch_to_tsquery("english", clean_q)
            ).label("search_relevance")

        if filters:
            query = query.where(and_(*filters))

        # Count total matching rows
        count_query = select(func.count()).select_from(query.subquery())
        if q and q.strip():
            total = db.execute(count_query.params(q_fts=q.strip())).scalar() or 0
        else:
            total = db.execute(count_query).scalar() or 0

        # Sorting
        sort_column_map = {
            "project_id": Project.project_id,
            "project_code": Project.project_code,
            "project_title": Project.project_title,
            "recommendation_date": Project.recommendation_date,
            "sanctioned_amount": Financial.sanctioned_amount,
            "expenditure_amount": Financial.expenditure_amount,
            "days_delayed": text("days_delayed"),
            "overall_risk_score": RiskScore.overall_risk_score,
            "current_status": Project.current_status
        }
        order_col = sort_column_map.get(sort_by, Project.recommendation_date)

        if search_rank_col is not None and sort_by == "search_rank":
            query = query.add_columns(search_rank_col).order_by(desc(search_rank_col))
        elif sort_order.lower() == "asc":
            query = query.order_by(asc(order_col))
        else:
            query = query.order_by(desc(order_col))

        # Pagination limit and offset (skip/limit)
        query = query.offset(effective_skip).limit(effective_limit)

        # Execute
        if q and q.strip():
            rows = db.execute(query.params(q_fts=q.strip())).fetchall()
        else:
            rows = db.execute(query).fetchall()

        items: List[ProjectSummary] = []
        for r in rows:
            items.append(ProjectSummary(
                project_id=r.project_id,
                project_code=r.project_code,
                project_title=r.project_title,
                sector=r.sector,
                state_name=r.state_name,
                district_name=r.district_name,
                mp_name=r.mp_name,
                current_status=r.current_status,
                financial_year=r.financial_year,
                sanctioned_amount=r.sanctioned_amount,
                released_amount=r.released_amount,
                expenditure_amount=r.expenditure_amount,
                physical_progress_pct=r.physical_progress_pct,
                days_delayed=r.days_delayed,
                overall_risk_score=r.overall_risk_score,
                risk_level=r.risk_level,
                search_relevance=getattr(r, "search_relevance", None)
            ))

        total_pages = math.ceil(total / effective_limit) if (total > 0 and effective_limit > 0) else 0

        return PaginatedResponse[ProjectSummary](
            items=items,
            total=total,
            skip=effective_skip,
            limit=effective_limit,
            page=effective_page,
            page_size=effective_page_size,
            total_pages=total_pages
        )

    @staticmethod
    def get_project_by_id(db: Session, project_id: str) -> ProjectDetail:
        """
        Retrieves a 360-degree detailed project view with all joined relations.
        Raises 404 if project does not exist.
        """
        stmt = (
            select(Project)
            .where(Project.project_id == project_id)
            .options(
                joinedload(Project.state),
                joinedload(Project.constituency),
                joinedload(Project.financial),
                selectinload(Project.progress_records),
                joinedload(Project.risk_score).selectinload(RiskScore.factors),
                selectinload(Project.risk_factors),
                selectinload(Project.history_records),
                joinedload(Project.features)
            )
        )
        project = db.execute(stmt).scalars().first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found."
            )

        return ProjectDetail.model_validate(project)

    @staticmethod
    def get_project_features(db: Session, project_id: str) -> ProjectFeatureRead:
        """
        Retrieves the engineered Phase 5 features for a specific project.
        Raises 404 if project or its features do not exist.
        """
        stmt = select(ProjectFeature).where(ProjectFeature.project_id == project_id)
        feat = db.execute(stmt).scalars().first()
        if not feat:
            # Check if project itself exists to provide accurate 404
            proj_exists = db.execute(select(Project.project_id).where(Project.project_id == project_id)).first()
            if not proj_exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Project with ID '{project_id}' not found."
                )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Engineered features for project '{project_id}' not found."
            )
        return ProjectFeatureRead.model_validate(feat)

    @staticmethod
    def create_project(
        db: Session,
        project_in: ProjectCreate,
        performed_by: str = "System Admin"
    ) -> ProjectDetail:
        """
        Creates a new project record, initializes financial accounting,
        and logs a 'Created' audit event inside an atomic transaction.
        """
        # Validate state and constituency exist
        state = db.get(State, project_in.state_id)
        if not state:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid state_id: State {project_in.state_id} does not exist."
            )

        constituency = db.get(Constituency, project_in.constituency_id)
        if not constituency:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid constituency_id: Constituency {project_in.constituency_id} does not exist."
            )

        # Check unique project_code
        existing_code = db.execute(
            select(Project).where(Project.project_code == project_in.project_code)
        ).scalars().first()
        if existing_code:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project with code '{project_in.project_code}' already exists."
            )

        # Generate project_id if not provided
        if not project_in.project_id:
            count = db.execute(select(func.count(Project.project_id))).scalar() or 0
            year = datetime.now().year
            project_id = f"MPLADS-{year}-{count + 1:04d}"
        else:
            project_id = project_in.project_id

        # Check unique project_id
        existing_id = db.get(Project, project_id)
        if existing_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project with ID '{project_id}' already exists."
            )

        try:
            # 1. Project Master
            new_project = Project(
                project_id=project_id,
                project_code=project_in.project_code,
                project_title=project_in.project_title,
                project_description=project_in.project_description,
                sector=project_in.sector,
                sub_sector=project_in.sub_sector,
                state_id=project_in.state_id,
                constituency_id=project_in.constituency_id,
                district_name=project_in.district_name,
                block_name=project_in.block_name,
                implementing_agency=project_in.implementing_agency,
                mp_name=project_in.mp_name,
                house_of_parliament=project_in.house_of_parliament,
                financial_year=project_in.financial_year,
                current_status=project_in.current_status,
                recommendation_date=project_in.recommendation_date,
                sanction_date=project_in.sanction_date,
                work_order_date=project_in.work_order_date,
                expected_completion_date=project_in.expected_completion_date,
                actual_completion_date=project_in.actual_completion_date
            )
            db.add(new_project)
            db.flush()

            # 2. Financials
            new_financial = Financial(
                project_id=project_id,
                currency="INR",
                recommended_amount=project_in.recommended_amount,
                sanctioned_amount=project_in.recommended_amount if project_in.current_status != "Recommended" else None,
                released_amount=Decimal("0.00"),
                expenditure_amount=Decimal("0.00"),
                cost_overrun_amount=Decimal("0.00"),
                cost_overrun_pct=Decimal("0.00")
            )
            db.add(new_financial)

            # 3. Project History Audit Record
            new_history = ProjectHistory(
                project_id=project_id,
                event_type="Created",
                previous_status=None,
                new_status=project_in.current_status,
                performed_by=performed_by,
                event_description=f"Project created with status '{project_in.current_status}' by {performed_by}."
            )
            db.add(new_history)

            db.commit()
            return ProjectService.get_project_by_id(db, project_id)

        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create project: {str(e)}"
            )

    @staticmethod
    def update_project(
        db: Session,
        project_id: str,
        project_in: ProjectUpdate,
        performed_by: str = "System Admin"
    ) -> ProjectDetail:
        """
        Updates project attributes with historical tracking, automated snapshotting,
        and integrated 6-engine risk recalculation inside an atomic transaction.
        """
        project = db.get(Project, project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID '{project_id}' not found."
            )

        update_data = project_in.model_dump(exclude_unset=True)
        if not update_data:
            return ProjectService.get_project_by_id(db, project_id)

        try:
            from app.services.historical_risk_integration_service import historical_risk_integration_service
        except ImportError:
            from backend.app.services.historical_risk_integration_service import historical_risk_integration_service

        try:
            historical_risk_integration_service.process_project_update_transactional(
                db=db,
                project_id=project_id,
                update_payload=update_data,
                performed_by=performed_by
            )
            return ProjectService.get_project_by_id(db, project_id)

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update project '{project_id}': {str(e)}"
            )

    @staticmethod
    def get_project_timeline(db: Session, project_id: str) -> List[ProjectHistoryRead]:
        """
        Retrieves chronological audit events for a project.
        """
        ProjectService.get_project_by_id(db, project_id)  # Validate project exists
        stmt = (
            select(ProjectHistory)
            .where(ProjectHistory.project_id == project_id)
            .order_by(desc(ProjectHistory.event_timestamp))
        )
        records = db.execute(stmt).scalars().all()
        return [ProjectHistoryRead.model_validate(r) for r in records]

    @staticmethod
    def get_project_progress_history(db: Session, project_id: str) -> List[ProgressRead]:
        """
        Retrieves physical execution milestone trajectory.
        """
        ProjectService.get_project_by_id(db, project_id)  # Validate project exists
        stmt = (
            select(Progress)
            .where(Progress.project_id == project_id)
            .order_by(desc(Progress.reported_date))
        )
        records = db.execute(stmt).scalars().all()
        return [ProgressRead.model_validate(r) for r in records]

    @staticmethod
    def get_project_snapshots(
        db: Session,
        project_id: str,
        sort_order: str = "asc",
        limit: Optional[int] = None
    ) -> List[ProjectSnapshotRead]:
        """
        Retrieves chronological immutable project snapshots for a project.
        Raises 404 if project does not exist.
        Returns empty list [] if project exists but has no historical snapshots.
        """
        ProjectService.get_project_by_id(db, project_id)  # 404 validation

        stmt = select(ProjectSnapshot).where(ProjectSnapshot.project_id == project_id)
        if sort_order.lower() == "desc":
            stmt = stmt.order_by(desc(ProjectSnapshot.snapshot_datetime), desc(ProjectSnapshot.snapshot_id))
        else:
            stmt = stmt.order_by(asc(ProjectSnapshot.snapshot_datetime), asc(ProjectSnapshot.snapshot_id))

        if limit is not None:
            stmt = stmt.limit(limit)

        snapshots = db.execute(stmt).scalars().all()
        return [ProjectSnapshotRead.model_validate(s) for s in snapshots]

    @staticmethod
    def get_project_risk_history(
        db: Session,
        project_id: str,
        sort_order: str = "asc",
        limit: Optional[int] = None
    ) -> List[RiskHistoryRead]:
        """
        Retrieves chronological risk evaluation and detector score history for a project.
        Raises 404 if project does not exist.
        Returns empty list [] if project exists but has no risk history.
        """
        ProjectService.get_project_by_id(db, project_id)  # 404 validation

        stmt = select(RiskHistory).where(RiskHistory.project_id == project_id)
        if sort_order.lower() == "desc":
            stmt = stmt.order_by(desc(RiskHistory.calculated_at), desc(RiskHistory.history_id))
        else:
            stmt = stmt.order_by(asc(RiskHistory.calculated_at), asc(RiskHistory.history_id))

        if limit is not None:
            stmt = stmt.limit(limit)

        records = db.execute(stmt).scalars().all()
        return [RiskHistoryRead.model_validate(r) for r in records]

    @staticmethod
    def get_project_changes(
        db: Session,
        project_id: str,
        sort_order: str = "asc"
    ) -> List[ProjectChangeRecord]:
        """
        Retrieves meaningful changes between consecutive project snapshots.
        Raises 404 if project does not exist.
        Returns empty list [] if project exists but has no snapshots.
        """
        ProjectService.get_project_by_id(db, project_id)  # 404 validation

        stmt = (
            select(ProjectSnapshot)
            .where(ProjectSnapshot.project_id == project_id)
            .order_by(asc(ProjectSnapshot.snapshot_datetime), asc(ProjectSnapshot.snapshot_id))
        )
        snapshots = db.execute(stmt).scalars().all()
        if not snapshots:
            return []

        try:
            from app.services.historical_comparison_service import HistoricalComparisonService
        except ImportError:
            from backend.app.services.historical_comparison_service import HistoricalComparisonService

        records: List[ProjectChangeRecord] = []

        # First snapshot (initial baseline)
        s0 = snapshots[0]
        records.append(ProjectChangeRecord(
            snapshot_id=s0.snapshot_id,
            previous_snapshot_id=None,
            snapshot_datetime=s0.snapshot_datetime,
            project_status=s0.project_status,
            overall_risk_score=s0.overall_risk_score,
            risk_level=s0.risk_level,
            change_summary=s0.change_summary or "Initial baseline project snapshot recorded upon first ingestion.",
            changes_count=1,
            modified_fields=["initial_baseline"],
            field_changes=[]
        ))

        # Subsequent snapshots compared against preceding snapshot
        for i in range(1, len(snapshots)):
            prev_s = snapshots[i - 1]
            curr_s = snapshots[i]

            comp = HistoricalComparisonService.compare_data(prev_s, curr_s)
            field_changes = [
                FieldChangeItem(
                    field_name=fc.field_name,
                    display_name=fc.display_name,
                    category=fc.category,
                    previous_value=fc.previous_value,
                    new_value=fc.new_value,
                    delta=fc.delta,
                    delta_pct=fc.delta_pct,
                    summary=fc.summary
                )
                for fc in comp.field_changes
            ]

            records.append(ProjectChangeRecord(
                snapshot_id=curr_s.snapshot_id,
                previous_snapshot_id=prev_s.snapshot_id,
                snapshot_datetime=curr_s.snapshot_datetime,
                project_status=curr_s.project_status,
                overall_risk_score=curr_s.overall_risk_score,
                risk_level=curr_s.risk_level,
                change_summary=curr_s.change_summary or comp.change_summary_text,
                changes_count=comp.changes_count,
                modified_fields=[fc.field_name for fc in comp.field_changes],
                field_changes=field_changes
            ))

        if sort_order.lower() == "desc":
            records.reverse()

        return records
