"""
backend/app/services/analytics_service.py
=============================================================================
Analytics and governance business logic querying optimized database views.
=============================================================================
"""

from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy import text, select, func
from sqlalchemy.orm import Session

from app.schemas.project import (
    KPIOverviewResponse,
    SectorAnalyticsItem,
    DelayedProjectItem,
    HighRiskProjectItem,
    MissingInfoAuditItem,
    StateEquityItem,
    StateEfficiencyItem,
    BudgetHistoricalItem,
    AnalyticsSummaryResponse,
    FinancialSummaryStats,
    RiskDistributionSummary,
    StateAggregationItem,
    DistrictAggregationItem
)
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    StateAnalyticsItem,
    StateAnalyticsResponse,
    DistrictAnalyticsItem,
    DistrictAnalyticsResponse,
    TopDelayedProjectItem,
    DelayAnalyticsResponse,
    TopCostAnomalyItem,
    CostAnomalyAnalyticsResponse,
    TrendPointItem,
    TrendAnalyticsResponse,
    MapStateItem,
    MapAnalyticsResponse,
)


class AnalyticsService:

    @staticmethod
    def get_analytics_summary(db: Session) -> AnalyticsSummaryResponse:
        """
        Calculates project-level statistics, financial aggregates, risk distribution,
        and geographic/sectoral breakdowns from live PostgreSQL data.
        """
        # 1. Project-level and financial aggregations
        sql_summary = text("""
            SELECT 
                count(p.project_id) AS total_projects,
                count(CASE WHEN p.current_status = 'Completed' THEN 1 END) AS completed_projects,
                count(CASE WHEN p.current_status = 'In Progress' THEN 1 END) AS in_progress_projects,
                count(CASE WHEN p.current_status IN ('In Progress', 'Work Order Issued', 'Sanctioned') THEN 1 END) AS ongoing_projects,
                count(CASE WHEN p.current_status = 'Stalled' THEN 1 END) AS stalled_projects,
                coalesce(sum(f.recommended_amount), 0.0) AS total_allocated_amount,
                coalesce(sum(f.sanctioned_amount), 0.0) AS total_sanctioned_amount,
                coalesce(sum(f.released_amount), 0.0) AS total_released_amount,
                coalesce(sum(f.expenditure_amount), 0.0) AS total_expenditure_amount,
                coalesce(sum(f.unspent_balance), 0.0) AS total_unspent_balance,
                CASE 
                    WHEN sum(f.released_amount) > 0 
                    THEN round(sum(f.expenditure_amount) / sum(f.released_amount) * 100.0, 2)
                    ELSE 0.0 
                END AS overall_utilization_pct,
                coalesce(round(avg(pr.physical_progress_pct), 2), 0.0) AS average_progress,
                count(CASE WHEN pr.days_delayed > 0 OR pr.milestone_status IN ('Delayed', 'Critical') OR p.current_status = 'Stalled' THEN 1 END) AS delayed_projects
            FROM projects p
            LEFT JOIN financials f ON p.project_id = f.project_id
            LEFT JOIN (
                SELECT DISTINCT ON (project_id) project_id, physical_progress_pct, days_delayed, milestone_status
                FROM progress
                ORDER BY project_id, reported_date DESC
            ) pr ON p.project_id = pr.project_id;
        """)
        summary_row = db.execute(sql_summary).mappings().first()

        # 2. Risk distribution
        sql_risk = text("""
            SELECT 
                risk_level, 
                count(*) AS count
            FROM risk_scores
            GROUP BY risk_level;
        """)
        risk_rows = db.execute(sql_risk).mappings().all()
        risk_dist: Dict[str, int] = {"Low": 0, "Moderate": 0, "High": 0, "Critical": 0}
        total_assessed = 0
        for r in risk_rows:
            lvl = r["risk_level"]
            cnt = r["count"]
            risk_dist[lvl] = cnt
            total_assessed += cnt

        risk_stats = RiskDistributionSummary(
            low=risk_dist.get("Low", 0),
            moderate=risk_dist.get("Moderate", 0),
            high=risk_dist.get("High", 0),
            critical=risk_dist.get("Critical", 0),
            total_assessed=total_assessed,
            distribution_by_level=risk_dist
        )

        # 3. Status distribution
        sql_status = text("""
            SELECT current_status, count(*) AS count
            FROM projects
            GROUP BY current_status
            ORDER BY count DESC;
        """)
        status_rows = db.execute(sql_status).mappings().all()
        status_dist = {r["current_status"]: r["count"] for r in status_rows}

        # 4. State-level aggregations
        sql_states = text("""
            SELECT 
                s.state_id,
                s.state_name,
                count(p.project_id) AS total_projects,
                count(CASE WHEN p.current_status = 'Completed' THEN 1 END) AS completed_projects,
                count(CASE WHEN p.current_status IN ('In Progress', 'Work Order Issued', 'Sanctioned') THEN 1 END) AS ongoing_projects,
                coalesce(sum(f.sanctioned_amount), 0.0) AS total_sanctioned,
                coalesce(sum(f.released_amount), 0.0) AS total_released,
                coalesce(sum(f.expenditure_amount), 0.0) AS total_expenditure,
                coalesce(round(avg(pr.physical_progress_pct), 2), 0.0) AS avg_progress_pct
            FROM states s
            JOIN projects p ON s.state_id = p.state_id
            LEFT JOIN financials f ON p.project_id = f.project_id
            LEFT JOIN (
                SELECT DISTINCT ON (project_id) project_id, physical_progress_pct
                FROM progress
                ORDER BY project_id, reported_date DESC
            ) pr ON p.project_id = pr.project_id
            GROUP BY s.state_id, s.state_name
            ORDER BY total_projects DESC, total_sanctioned DESC;
        """)
        state_rows = db.execute(sql_states).mappings().all()
        state_aggs = [
            StateAggregationItem(
                state_id=r["state_id"],
                state_name=r["state_name"],
                total_projects=r["total_projects"],
                completed_projects=r["completed_projects"],
                ongoing_projects=r["ongoing_projects"],
                total_sanctioned=Decimal(str(r["total_sanctioned"])),
                total_released=Decimal(str(r["total_released"])),
                total_expenditure=Decimal(str(r["total_expenditure"])),
                avg_progress_pct=Decimal(str(r["avg_progress_pct"]))
            )
            for r in state_rows
        ]

        # 5. District-level aggregations
        sql_districts = text("""
            SELECT 
                p.district_name,
                s.state_name,
                count(p.project_id) AS total_projects,
                count(CASE WHEN p.current_status = 'Completed' THEN 1 END) AS completed_projects,
                count(CASE WHEN p.current_status IN ('In Progress', 'Work Order Issued', 'Sanctioned') THEN 1 END) AS ongoing_projects,
                coalesce(sum(f.sanctioned_amount), 0.0) AS total_sanctioned,
                coalesce(sum(f.expenditure_amount), 0.0) AS total_expenditure,
                coalesce(round(avg(pr.physical_progress_pct), 2), 0.0) AS avg_progress_pct
            FROM projects p
            JOIN states s ON p.state_id = s.state_id
            LEFT JOIN financials f ON p.project_id = f.project_id
            LEFT JOIN (
                SELECT DISTINCT ON (project_id) project_id, physical_progress_pct
                FROM progress
                ORDER BY project_id, reported_date DESC
            ) pr ON p.project_id = pr.project_id
            GROUP BY p.district_name, s.state_name
            ORDER BY total_projects DESC, total_sanctioned DESC;
        """)
        district_rows = db.execute(sql_districts).mappings().all()
        district_aggs = [
            DistrictAggregationItem(
                district_name=r["district_name"],
                state_name=r["state_name"],
                total_projects=r["total_projects"],
                completed_projects=r["completed_projects"],
                ongoing_projects=r["ongoing_projects"],
                total_sanctioned=Decimal(str(r["total_sanctioned"])),
                total_expenditure=Decimal(str(r["total_expenditure"])),
                avg_progress_pct=Decimal(str(r["avg_progress_pct"]))
            )
            for r in district_rows
        ]

        # 6. Sector aggregations
        sector_aggs = AnalyticsService.get_sector_summary(db=db)

        # Financial Summary stats object
        financials = FinancialSummaryStats(
            total_allocated_amount=Decimal(str(summary_row["total_allocated_amount"] or "0.00")),
            total_sanctioned_amount=Decimal(str(summary_row["total_sanctioned_amount"] or "0.00")),
            total_released_amount=Decimal(str(summary_row["total_released_amount"] or "0.00")),
            total_expenditure_amount=Decimal(str(summary_row["total_expenditure_amount"] or "0.00")),
            total_unspent_balance=Decimal(str(summary_row["total_unspent_balance"] or "0.00")),
            overall_utilization_pct=Decimal(str(summary_row["overall_utilization_pct"] or "0.00"))
        )

        return AnalyticsSummaryResponse(
            total_projects=summary_row["total_projects"] or 0,
            completed_projects=summary_row["completed_projects"] or 0,
            ongoing_projects=summary_row["ongoing_projects"] or 0,
            delayed_projects=summary_row["delayed_projects"] or 0,
            stalled_projects=summary_row["stalled_projects"] or 0,
            average_progress=Decimal(str(summary_row["average_progress"] or "0.00")),
            total_allocated_amount=financials.total_allocated_amount,
            total_sanctioned_amount=financials.total_sanctioned_amount,
            total_released_amount=financials.total_released_amount,
            total_expenditure_amount=financials.total_expenditure_amount,
            total_unspent_balance=financials.total_unspent_balance,
            overall_utilization_pct=financials.overall_utilization_pct,
            financials=financials,
            risk_distribution=risk_dist,
            risk_stats=risk_stats,
            status_distribution=status_dist,
            state_aggregations=state_aggs,
            district_aggregations=district_aggs,
            sector_aggregations=sector_aggs
        )

    @staticmethod
    def get_kpis(db: Session) -> KPIOverviewResponse:
        """
        Computes high-level national and portfolio-wide KPI summary metrics.
        """
        sql = text("""
            SELECT 
                count(p.project_id) AS total_projects,
                coalesce(round(sum(f.sanctioned_amount) / 10000000.0, 2), 0.0) AS total_sanctioned_cr,
                coalesce(round(sum(f.released_amount) / 10000000.0, 2), 0.0) AS total_released_cr,
                coalesce(round(sum(f.expenditure_amount) / 10000000.0, 2), 0.0) AS total_expenditure_cr,
                CASE 
                    WHEN sum(f.released_amount) > 0 
                    THEN round(sum(f.expenditure_amount) / sum(f.released_amount) * 100.0, 2)
                    ELSE 0.0 
                END AS overall_utilization_pct,
                count(CASE WHEN p.current_status = 'Completed' THEN 1 END) AS completed_projects_count,
                count(CASE WHEN p.current_status = 'In Progress' THEN 1 END) AS in_progress_projects_count,
                count(CASE WHEN p.current_status = 'Stalled' THEN 1 END) AS stalled_projects_count,
                (SELECT count(*) FROM v_delayed_projects) AS delayed_projects_count,
                (SELECT count(*) FROM v_high_risk_projects) AS high_risk_projects_count
            FROM projects p
            LEFT JOIN financials f ON p.project_id = f.project_id;
        """)
        row = db.execute(sql).mappings().first()

        return KPIOverviewResponse(
            total_projects=row["total_projects"] or 0,
            total_sanctioned_cr=Decimal(str(row["total_sanctioned_cr"] or "0.0")),
            total_released_cr=Decimal(str(row["total_released_cr"] or "0.0")),
            total_expenditure_cr=Decimal(str(row["total_expenditure_cr"] or "0.0")),
            overall_utilization_pct=Decimal(str(row["overall_utilization_pct"] or "0.0")),
            completed_projects_count=row["completed_projects_count"] or 0,
            in_progress_projects_count=row["in_progress_projects_count"] or 0,
            stalled_projects_count=row["stalled_projects_count"] or 0,
            delayed_projects_count=row["delayed_projects_count"] or 0,
            high_risk_projects_count=row["high_risk_projects_count"] or 0
        )

    @staticmethod
    def get_sector_summary(db: Session) -> List[SectorAnalyticsItem]:
        """
        Retrieves financial, physical progress, and risk breakdown by developmental sector.
        """
        sql = text("""
            SELECT 
                sector,
                total_projects,
                completed_projects,
                in_progress_projects,
                stalled_projects,
                coalesce(avg_physical_progress_pct, 0.0) AS avg_physical_progress_pct,
                coalesce(total_sanctioned_amount, 0.0) AS total_sanctioned_amount,
                coalesce(total_released_amount, 0.0) AS total_released_amount,
                coalesce(total_expenditure_amount, 0.0) AS total_expenditure_amount,
                coalesce(total_unspent_balance, 0.0) AS total_unspent_balance,
                coalesce(overall_utilization_pct, 0.0) AS overall_utilization_pct,
                coalesce(avg_sector_risk_score, 0.0) AS avg_sector_risk_score,
                coalesce(delayed_projects_count, 0) AS delayed_projects_count
            FROM v_sector_financial_summary
            ORDER BY total_sanctioned_amount DESC;
        """)
        rows = db.execute(sql).mappings().all()

        return [
            SectorAnalyticsItem(
                sector=r["sector"],
                total_projects=r["total_projects"],
                completed_projects=r["completed_projects"],
                in_progress_projects=r["in_progress_projects"],
                stalled_projects=r["stalled_projects"],
                avg_physical_progress_pct=Decimal(str(r["avg_physical_progress_pct"])),
                total_sanctioned_amount=Decimal(str(r["total_sanctioned_amount"])),
                total_released_amount=Decimal(str(r["total_released_amount"])),
                total_expenditure_amount=Decimal(str(r["total_expenditure_amount"])),
                total_unspent_balance=Decimal(str(r["total_unspent_balance"])),
                overall_utilization_pct=Decimal(str(r["overall_utilization_pct"])),
                avg_sector_risk_score=Decimal(str(r["avg_sector_risk_score"])),
                delayed_projects_count=r["delayed_projects_count"]
            )
            for r in rows
        ]

    @staticmethod
    def get_delayed_projects(
        db: Session,
        limit: int = 50,
        offset: int = 0
    ) -> List[DelayedProjectItem]:
        """
        Retrieves real-time delayed, stalled, and critical milestone projects.
        """
        sql = text("""
            SELECT 
                project_id,
                project_code,
                project_title,
                state_name,
                constituency_name,
                district_name,
                mp_name,
                sector,
                implementing_agency,
                current_status,
                days_delayed,
                milestone_status,
                coalesce(physical_progress_pct, 0.0) AS physical_progress_pct,
                sanctioned_amount,
                coalesce(delay_risk_score, 0.0) AS delay_risk_score,
                risk_level
            FROM v_delayed_projects
            ORDER BY days_delayed DESC, delay_risk_score DESC
            LIMIT :limit OFFSET :offset;
        """)
        rows = db.execute(sql.params(limit=limit, offset=offset)).mappings().all()

        return [
            DelayedProjectItem(
                project_id=r["project_id"],
                project_code=r["project_code"],
                project_title=r["project_title"],
                state_name=r["state_name"],
                constituency_name=r["constituency_name"],
                district_name=r["district_name"],
                mp_name=r["mp_name"],
                sector=r["sector"],
                implementing_agency=r["implementing_agency"],
                current_status=r["current_status"],
                days_delayed=r["days_delayed"],
                milestone_status=r["milestone_status"],
                physical_progress_pct=Decimal(str(r["physical_progress_pct"])),
                sanctioned_amount=Decimal(str(r["sanctioned_amount"])) if r["sanctioned_amount"] is not None else None,
                delay_risk_score=Decimal(str(r["delay_risk_score"])),
                risk_level=r["risk_level"]
            )
            for r in rows
        ]

    @staticmethod
    def get_high_risk_projects(
        db: Session,
        limit: int = 50,
        offset: int = 0,
        min_score: Optional[float] = None
    ) -> List[HighRiskProjectItem]:
        """
        Retrieves high-risk projects with contributing causal factors in structured JSON.
        Optionally filters by minimum overall risk score threshold.
        """
        where_clause = ""
        params: dict = {"limit": limit, "offset": offset}
        if min_score is not None:
            where_clause = "WHERE overall_risk_score >= :min_score"
            params["min_score"] = float(min_score)

        sql = text(f"""
            SELECT 
                project_id,
                project_code,
                project_title,
                state_name,
                constituency_name,
                district_name,
                mp_name,
                sector,
                implementing_agency,
                current_status,
                overall_risk_score,
                delay_risk_score,
                cost_overrun_risk_score,
                risk_level,
                confidence_score,
                sanctioned_amount,
                days_delayed,
                primary_risk_factors
            FROM v_high_risk_projects
            {where_clause}
            ORDER BY overall_risk_score DESC
            LIMIT :limit OFFSET :offset;
        """)
        rows = db.execute(sql.params(**params)).mappings().all()

        return [
            HighRiskProjectItem(
                project_id=r["project_id"],
                project_code=r["project_code"],
                project_title=r["project_title"],
                project_name=r["project_title"],
                state_name=r["state_name"],
                constituency_name=r["constituency_name"],
                district_name=r["district_name"],
                mp_name=r["mp_name"],
                sector=r["sector"],
                implementing_agency=r["implementing_agency"],
                current_status=r["current_status"],
                risk_score=Decimal(str(r["overall_risk_score"])),
                overall_risk_score=Decimal(str(r["overall_risk_score"])),
                delay_risk_score=Decimal(str(r["delay_risk_score"])),
                cost_overrun_risk_score=Decimal(str(r["cost_overrun_risk_score"])),
                risk_level=r["risk_level"],
                confidence_score=Decimal(str(r["confidence_score"])),
                sanctioned_amount=Decimal(str(r["sanctioned_amount"])) if r["sanctioned_amount"] is not None else None,
                days_delayed=r["days_delayed"],
                important_risk_factors=r["primary_risk_factors"],
                risk_factors=r["primary_risk_factors"],
                primary_risk_factors=r["primary_risk_factors"]
            )
            for r in rows
        ]

    @staticmethod
    def get_missing_info_audit(
        db: Session,
        limit: int = 50,
        offset: int = 0
    ) -> List[MissingInfoAuditItem]:
        """
        Audits governance completeness and missing field flags.
        """
        sql = text("""
            SELECT 
                project_id,
                project_code,
                project_title,
                state_name,
                constituency_name,
                current_status,
                missing_fields_count,
                missing_fields
            FROM v_projects_missing_information
            ORDER BY missing_fields_count DESC, project_id ASC
            LIMIT :limit OFFSET :offset;
        """)
        rows = db.execute(sql.params(limit=limit, offset=offset)).mappings().all()

        return [
            MissingInfoAuditItem(
                project_id=r["project_id"],
                project_code=r["project_code"],
                project_title=r["project_title"],
                state_name=r["state_name"],
                constituency_name=r["constituency_name"],
                current_status=r["current_status"],
                missing_fields_count=r["missing_fields_count"],
                missing_fields=list(r["missing_fields"]) if r["missing_fields"] else []
            )
            for r in rows
        ]

    @staticmethod
    def get_state_equity_summary(db: Session) -> List[StateEquityItem]:
        """
        Retrieves SC/ST statutory quota and disbursement equity analysis.
        """
        sql = text("""
            SELECT 
                state_id,
                state_name,
                category,
                total_lok_sabha_seats,
                sc_reserved_seats,
                sc_seat_share_pct,
                statutory_sc_allocation_pct,
                sc_share_vs_statutory_delta_pct,
                st_reserved_seats,
                st_seat_share_pct,
                statutory_st_allocation_pct,
                st_share_vs_statutory_delta_pct,
                cumulative_released_cr,
                mandated_sc_outlay_target_cr,
                mandated_st_outlay_target_cr
            FROM v_state_equity_analysis
            ORDER BY total_lok_sabha_seats DESC;
        """)
        rows = db.execute(sql).mappings().all()

        return [
            StateEquityItem(
                state_id=r["state_id"],
                state_name=r["state_name"],
                category=r["category"],
                total_lok_sabha_seats=r["total_lok_sabha_seats"],
                sc_reserved_seats=r["sc_reserved_seats"],
                sc_seat_share_pct=Decimal(str(r["sc_seat_share_pct"])),
                statutory_sc_allocation_pct=Decimal(str(r["statutory_sc_allocation_pct"])),
                sc_share_vs_statutory_delta_pct=Decimal(str(r["sc_share_vs_statutory_delta_pct"])),
                st_reserved_seats=r["st_reserved_seats"],
                st_seat_share_pct=Decimal(str(r["st_seat_share_pct"])),
                statutory_st_allocation_pct=Decimal(str(r["statutory_st_allocation_pct"])),
                st_share_vs_statutory_delta_pct=Decimal(str(r["st_share_vs_statutory_delta_pct"])),
                cumulative_released_cr=Decimal(str(r["cumulative_released_cr"])),
                mandated_sc_outlay_target_cr=Decimal(str(r["mandated_sc_outlay_target_cr"])) if r["mandated_sc_outlay_target_cr"] is not None else None,
                mandated_st_outlay_target_cr=Decimal(str(r["mandated_st_outlay_target_cr"])) if r["mandated_st_outlay_target_cr"] is not None else None
            )
            for r in rows
        ]

    @staticmethod
    def get_state_efficiency_rankings(db: Session, limit: int = 36) -> List[StateEfficiencyItem]:
        """
        Retrieves State/UT efficiency rankings based on fund utilization and works completion.
        """
        sql = text("""
            SELECT 
                state_id,
                state_name,
                category,
                released_cr,
                expenditure_cr,
                unspent_balance_cr,
                utilization_rate_pct,
                rank_utilization,
                sanction_rate_pct,
                rank_sanction_rate,
                completion_rate_pct,
                rank_completion_rate,
                works_recommended,
                works_sanctioned,
                works_completed
            FROM v_state_efficiency_ranking
            ORDER BY rank_utilization ASC
            LIMIT :limit;
        """)
        rows = db.execute(sql.params(limit=limit)).mappings().all()

        return [
            StateEfficiencyItem(
                state_id=r["state_id"],
                state_name=r["state_name"],
                category=r["category"],
                released_cr=Decimal(str(r["released_cr"])),
                expenditure_cr=Decimal(str(r["expenditure_cr"])),
                unspent_balance_cr=Decimal(str(r["unspent_balance_cr"])),
                utilization_rate_pct=Decimal(str(r["utilization_rate_pct"])),
                rank_utilization=r["rank_utilization"],
                sanction_rate_pct=Decimal(str(r["sanction_rate_pct"])),
                rank_sanction_rate=r["rank_sanction_rate"],
                completion_rate_pct=Decimal(str(r["completion_rate_pct"])),
                rank_completion_rate=r["rank_completion_rate"],
                works_recommended=r["works_recommended"],
                works_sanctioned=r["works_sanctioned"],
                works_completed=r["works_completed"]
            )
            for r in rows
        ]

    @staticmethod
    def get_budget_history(db: Session) -> List[BudgetHistoricalItem]:
        """
        Retrieves 33-year Union Budget Demand No. 91 fiscal performance trends.
        """
        sql = text("""
            SELECT 
                financial_year,
                start_year,
                scheme_entitlement_per_mp_cr,
                budget_estimate_cr,
                revised_estimate_cr,
                actual_expenditure_cr,
                be_vs_actual_variance_cr,
                budget_utilization_pct,
                status_notes
            FROM v_budget_historical_performance
            ORDER BY start_year ASC;
        """)
        rows = db.execute(sql).mappings().all()

        return [
            BudgetHistoricalItem(
                financial_year=r["financial_year"],
                start_year=r["start_year"],
                scheme_entitlement_per_mp_cr=Decimal(str(r["scheme_entitlement_per_mp_cr"])),
                budget_estimate_cr=Decimal(str(r["budget_estimate_cr"])),
                revised_estimate_cr=Decimal(str(r["revised_estimate_cr"])) if r["revised_estimate_cr"] is not None else None,
                actual_expenditure_cr=Decimal(str(r["actual_expenditure_cr"])) if r["actual_expenditure_cr"] is not None else None,
                be_vs_actual_variance_cr=Decimal(str(r["be_vs_actual_variance_cr"])) if r["be_vs_actual_variance_cr"] is not None else None,
                budget_utilization_pct=Decimal(str(r["budget_utilization_pct"])) if r["budget_utilization_pct"] is not None else None,
                status_notes=r["status_notes"]
            )
            for r in rows
        ]

    # =========================================================================
    # Phase 10: Dedicated Analytics & Visualization Queries
    # =========================================================================

    STATE_NAME_TO_CODE: Dict[str, str] = {
        "Andhra Pradesh": "IN-AP",
        "Arunachal Pradesh": "IN-AR",
        "Assam": "IN-AS",
        "Bihar": "IN-BR",
        "Chhattisgarh": "IN-CT",
        "Goa": "IN-GA",
        "Gujarat": "IN-GJ",
        "Haryana": "IN-HR",
        "Himachal Pradesh": "IN-HP",
        "Jharkhand": "IN-JH",
        "Karnataka": "IN-KA",
        "Kerala": "IN-KL",
        "Madhya Pradesh": "IN-MP",
        "Maharashtra": "IN-MH",
        "Manipur": "IN-MN",
        "Meghalaya": "IN-ML",
        "Mizoram": "IN-MZ",
        "Nagaland": "IN-NL",
        "Odisha": "IN-OR",
        "Punjab": "IN-PB",
        "Rajasthan": "IN-RJ",
        "Sikkim": "IN-SK",
        "Tamil Nadu": "IN-TN",
        "Telangana": "IN-TG",
        "Tripura": "IN-TR",
        "Uttar Pradesh": "IN-UP",
        "Uttarakhand": "IN-UT",
        "West Bengal": "IN-WB",
        "Andaman and Nicobar Islands": "IN-AN",
        "Chandigarh": "IN-CH",
        "Dadra and Nagar Haveli and Daman and Diu": "IN-DH",
        "Delhi": "IN-DL",
        "Jammu and Kashmir": "IN-JK",
        "Ladakh": "IN-LA",
        "Lakshadweep": "IN-LD",
        "Puducherry": "IN-PY",
    }

    @staticmethod
    def _build_project_filters(
        state_name: Optional[str] = None,
        district_name: Optional[str] = None,
        risk_level: Optional[str] = None,
        status: Optional[str] = None,
        sector: Optional[str] = None,
        financial_year: Optional[str] = None,
    ) -> tuple[str, dict]:
        clauses = ["1=1"]
        params = {}
        if state_name and state_name.strip() and state_name.lower() != "all":
            clauses.append("LOWER(s.state_name) = LOWER(:state_name)")
            params["state_name"] = state_name.strip()
        if district_name and district_name.strip() and district_name.lower() != "all":
            clauses.append("LOWER(p.district_name) = LOWER(:district_name)")
            params["district_name"] = district_name.strip()
        if status and status.strip() and status.lower() != "all":
            clauses.append("LOWER(p.current_status) = LOWER(:status)")
            params["status"] = status.strip()
        if sector and sector.strip() and sector.lower() != "all":
            clauses.append("LOWER(p.sector) = LOWER(:sector)")
            params["sector"] = sector.strip()
        if financial_year and financial_year.strip() and financial_year.lower() != "all":
            clauses.append("p.financial_year = :financial_year")
            params["financial_year"] = financial_year.strip()
        if risk_level and risk_level.strip() and risk_level.lower() != "all":
            rl = risk_level.strip().upper()
            if rl == "CRITICAL":
                clauses.append("(UPPER(r.risk_level) = 'CRITICAL' OR r.overall_risk_score >= 80)")
            elif rl == "HIGH":
                clauses.append("(UPPER(r.risk_level) = 'HIGH' OR (r.overall_risk_score >= 60 AND r.overall_risk_score < 80))")
            elif rl in ("MODERATE", "MEDIUM"):
                clauses.append("(UPPER(r.risk_level) IN ('MODERATE', 'MEDIUM') OR (r.overall_risk_score >= 30 AND r.overall_risk_score < 60))")
            elif rl == "LOW":
                clauses.append("(UPPER(r.risk_level) = 'LOW' OR (r.overall_risk_score < 30 AND r.overall_risk_score IS NOT NULL))")
        return " AND ".join(clauses), params

    @staticmethod
    def get_overview_filtered(
        db: Session,
        state_name: Optional[str] = None,
        district_name: Optional[str] = None,
        risk_level: Optional[str] = None,
        status: Optional[str] = None,
        sector: Optional[str] = None,
        financial_year: Optional[str] = None,
    ) -> AnalyticsOverviewResponse:
        """
        Calculates executive summary KPIs filtered by state, district, risk level, status, sector.
        """
        where_sql, params = AnalyticsService._build_project_filters(
            state_name, district_name, risk_level, status, sector, financial_year
        )

        sql = text(f"""
            SELECT 
                count(p.project_id) AS total_projects,
                count(CASE WHEN UPPER(r.risk_level) = 'CRITICAL' OR r.overall_risk_score >= 80 THEN 1 END) AS critical_count,
                count(CASE WHEN UPPER(r.risk_level) = 'HIGH' OR (r.overall_risk_score >= 60 AND r.overall_risk_score < 80) THEN 1 END) AS high_count,
                count(CASE WHEN UPPER(r.risk_level) IN ('MODERATE', 'MEDIUM') OR (r.overall_risk_score >= 30 AND r.overall_risk_score < 60) THEN 1 END) AS moderate_count,
                count(CASE WHEN UPPER(r.risk_level) = 'LOW' OR (r.overall_risk_score < 30 AND r.overall_risk_score IS NOT NULL) THEN 1 END) AS low_count,
                coalesce(round(avg(r.overall_risk_score), 2), 0.0) AS avg_risk_score,
                count(CASE WHEN r.overall_risk_score >= 40 OR pf.is_delayed = True OR pf.cost_deviation > 0 THEN 1 END) AS flagged_count,
                coalesce(sum(f.sanctioned_amount), 0.0) AS total_sanctioned,
                coalesce(sum(f.expenditure_amount), 0.0) AS total_expenditure,
                CASE 
                    WHEN sum(f.released_amount) > 0 
                    THEN round(sum(f.expenditure_amount) / sum(f.released_amount) * 100.0, 2)
                    WHEN sum(f.sanctioned_amount) > 0
                    THEN round(sum(f.expenditure_amount) / sum(f.sanctioned_amount) * 100.0, 2)
                    ELSE 0.0 
                END AS overall_utilization_pct,
                count(CASE WHEN pf.delay_days > 0 OR pf.is_delayed = True OR p.current_status = 'Stalled' THEN 1 END) AS delayed_count,
                coalesce(round(avg(CASE WHEN pf.delay_days > 0 THEN pf.delay_days END), 1), 0.0) AS avg_delay_days
            FROM projects p
            JOIN states s ON p.state_id = s.state_id
            LEFT JOIN financials f ON p.project_id = f.project_id
            LEFT JOIN risk_scores r ON p.project_id = r.project_id
            LEFT JOIN project_features pf ON p.project_id = pf.project_id
            WHERE {where_sql};
        """)

        row = db.execute(sql, params).mappings().first()
        total = row["total_projects"] or 0
        flagged = row["flagged_count"] or 0
        flagged_pct = round((flagged / total) * 100.0, 1) if total > 0 else 0.0

        return AnalyticsOverviewResponse(
            total_projects=total,
            high_risk_projects=row["high_count"] or 0,
            critical_risk_projects=row["critical_count"] or 0,
            moderate_risk_projects=row["moderate_count"] or 0,
            low_risk_projects=row["low_count"] or 0,
            average_risk_score=float(row["avg_risk_score"] or 0.0),
            flagged_projects_count=flagged,
            flagged_percentage=flagged_pct,
            total_sanctioned_amount=Decimal(str(row["total_sanctioned"] or "0.00")),
            total_expenditure_amount=Decimal(str(row["total_expenditure"] or "0.00")),
            overall_utilization_pct=float(row["overall_utilization_pct"] or 0.0),
            delayed_projects_count=row["delayed_count"] or 0,
            average_delay_days=float(row["avg_delay_days"] or 0.0),
        )

    @staticmethod
    def get_risk_distribution_filtered(
        db: Session,
        state_name: Optional[str] = None,
        district_name: Optional[str] = None,
        status: Optional[str] = None,
        sector: Optional[str] = None,
        financial_year: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Computes risk distribution and engine averages matching applied filters.
        """
        where_sql, params = AnalyticsService._build_project_filters(
            state_name, district_name, None, status, sector, financial_year
        )

        sql = text(f"""
            SELECT 
                count(p.project_id) AS total_projects,
                count(CASE WHEN UPPER(r.risk_level) = 'CRITICAL' OR r.overall_risk_score >= 80 THEN 1 END) AS critical_count,
                count(CASE WHEN UPPER(r.risk_level) = 'HIGH' OR (r.overall_risk_score >= 60 AND r.overall_risk_score < 80) THEN 1 END) AS high_count,
                count(CASE WHEN UPPER(r.risk_level) IN ('MODERATE', 'MEDIUM') OR (r.overall_risk_score >= 30 AND r.overall_risk_score < 60) THEN 1 END) AS medium_count,
                count(CASE WHEN UPPER(r.risk_level) = 'LOW' OR (r.overall_risk_score < 30 AND r.overall_risk_score IS NOT NULL) THEN 1 END) AS low_count,
                coalesce(round(avg(r.overall_risk_score), 2), 0.0) AS avg_score
            FROM projects p
            JOIN states s ON p.state_id = s.state_id
            LEFT JOIN risk_scores r ON p.project_id = r.project_id
            WHERE {where_sql};
        """)
        row = db.execute(sql, params).mappings().first()
        total = row["total_projects"] or 0

        dist = {
            "LOW": row["low_count"] or 0,
            "MEDIUM": row["medium_count"] or 0,
            "HIGH": row["high_count"] or 0,
            "CRITICAL": row["critical_count"] or 0,
        }
        percentages = {
            tier: round((count / total) * 100.0, 2) if total > 0 else 0.0
            for tier, count in dist.items()
        }

        # Engine averages under filtered projects
        sql_engines = text(f"""
            SELECT rf.engine_name, round(avg(rf.score), 2) AS avg_score
            FROM risk_factors rf
            JOIN projects p ON rf.project_id = p.project_id
            JOIN states s ON p.state_id = s.state_id
            LEFT JOIN risk_scores r ON p.project_id = r.project_id
            WHERE {where_sql} AND rf.engine_name IS NOT NULL
            GROUP BY rf.engine_name;
        """)
        eng_rows = db.execute(sql_engines, params).mappings().all()
        engine_averages = {r["engine_name"]: float(r["avg_score"] or 0.0) for r in eng_rows}

        return {
            "total_projects": total,
            "distribution": dist,
            "percentages": percentages,
            "average_overall_score": float(row["avg_score"] or 0.0),
            "engine_averages": engine_averages,
        }

    @staticmethod
    def get_states_analytics(
        db: Session,
        metric: str = "projects",
        state_name: Optional[str] = None,
        risk_level: Optional[str] = None,
        status: Optional[str] = None,
        sector: Optional[str] = None,
        financial_year: Optional[str] = None,
        limit: int = 36,
    ) -> StateAnalyticsResponse:
        """
        Ranks and aggregates projects across States and UTs.
        """
        where_sql, params = AnalyticsService._build_project_filters(
            state_name, None, risk_level, status, sector, financial_year
        )

        sql = text(f"""
            SELECT 
                s.state_id,
                s.state_name,
                count(p.project_id) AS total_projects,
                count(CASE WHEN UPPER(r.risk_level) = 'HIGH' OR (r.overall_risk_score >= 60 AND r.overall_risk_score < 80) THEN 1 END) AS high_risk_projects,
                count(CASE WHEN UPPER(r.risk_level) = 'CRITICAL' OR r.overall_risk_score >= 80 THEN 1 END) AS critical_risk_projects,
                coalesce(round(avg(r.overall_risk_score), 2), 0.0) AS average_risk_score,
                coalesce(round(avg(CASE WHEN pf.delay_days > 0 THEN pf.delay_days ELSE 0 END), 1), 0.0) AS average_delay_days,
                count(CASE WHEN rf_cost.score >= 40 OR pf.cost_deviation > 0 THEN 1 END) AS cost_anomaly_count,
                coalesce(sum(f.sanctioned_amount), 0.0) AS total_sanctioned,
                coalesce(sum(f.expenditure_amount), 0.0) AS total_expenditure,
                CASE 
                    WHEN sum(f.released_amount) > 0 
                    THEN round(sum(f.expenditure_amount) / sum(f.released_amount) * 100.0, 2)
                    WHEN sum(f.sanctioned_amount) > 0
                    THEN round(sum(f.expenditure_amount) / sum(f.sanctioned_amount) * 100.0, 2)
                    ELSE 0.0 
                END AS utilization_pct
            FROM states s
            JOIN projects p ON s.state_id = p.state_id
            LEFT JOIN financials f ON p.project_id = f.project_id
            LEFT JOIN risk_scores r ON p.project_id = r.project_id
            LEFT JOIN project_features pf ON p.project_id = pf.project_id
            LEFT JOIN risk_factors rf_cost ON p.project_id = rf_cost.project_id AND rf_cost.engine_name = 'cost_anomaly'
            WHERE {where_sql}
            GROUP BY s.state_id, s.state_name;
        """)

        rows = db.execute(sql, params).mappings().all()

        items = [
            StateAnalyticsItem(
                state_id=r["state_id"],
                state_name=r["state_name"],
                total_projects=r["total_projects"],
                high_risk_projects=r["high_risk_projects"],
                critical_risk_projects=r["critical_risk_projects"],
                average_risk_score=float(r["average_risk_score"] or 0.0),
                average_delay_days=float(r["average_delay_days"] or 0.0),
                cost_anomaly_count=r["cost_anomaly_count"],
                total_sanctioned=Decimal(str(r["total_sanctioned"])),
                total_expenditure=Decimal(str(r["total_expenditure"])),
                utilization_pct=float(r["utilization_pct"] or 0.0),
            )
            for r in rows
        ]

        # Sort dynamically by metric
        metric_clean = (metric or "projects").lower()
        if metric_clean in ("risk_score", "risk"):
            items.sort(key=lambda x: (x.average_risk_score, x.total_projects), reverse=True)
        elif metric_clean in ("delay", "delays", "average_delay_days"):
            items.sort(key=lambda x: (x.average_delay_days, x.total_projects), reverse=True)
        elif metric_clean in ("cost_anomaly", "cost_anomalies"):
            items.sort(key=lambda x: (x.cost_anomaly_count, x.total_projects), reverse=True)
        elif metric_clean in ("sanctioned", "funds", "total_sanctioned"):
            items.sort(key=lambda x: (x.total_sanctioned, x.total_projects), reverse=True)
        elif metric_clean in ("critical", "critical_risk_projects"):
            items.sort(key=lambda x: (x.critical_risk_projects, x.total_projects), reverse=True)
        elif metric_clean in ("high_risk", "high_risk_projects"):
            items.sort(key=lambda x: (x.high_risk_projects, x.total_projects), reverse=True)
        else:
            items.sort(key=lambda x: (x.total_projects, x.total_sanctioned), reverse=True)

        sliced_items = items[:limit]
        return StateAnalyticsResponse(states=sliced_items, total_states=len(items))

    @staticmethod
    def get_districts_analytics(
        db: Session,
        state_name: Optional[str] = None,
        district_name: Optional[str] = None,
        risk_level: Optional[str] = None,
        status: Optional[str] = None,
        sector: Optional[str] = None,
        financial_year: Optional[str] = None,
        limit: int = 15,
        sort_by: str = "projects",
    ) -> DistrictAnalyticsResponse:
        """
        District-level rankings with state filter and top-N ranking support.
        """
        where_sql, params = AnalyticsService._build_project_filters(
            state_name, district_name, risk_level, status, sector, financial_year
        )

        sql = text(f"""
            SELECT 
                p.district_name,
                s.state_name,
                count(p.project_id) AS total_projects,
                count(CASE WHEN UPPER(r.risk_level) = 'HIGH' OR (r.overall_risk_score >= 60 AND r.overall_risk_score < 80) THEN 1 END) AS high_risk_projects,
                count(CASE WHEN UPPER(r.risk_level) = 'CRITICAL' OR r.overall_risk_score >= 80 THEN 1 END) AS critical_risk_projects,
                coalesce(round(avg(r.overall_risk_score), 2), 0.0) AS average_risk_score,
                coalesce(round(avg(CASE WHEN pf.delay_days > 0 THEN pf.delay_days ELSE 0 END), 1), 0.0) AS average_delay_days,
                coalesce(sum(f.sanctioned_amount), 0.0) AS total_sanctioned,
                coalesce(sum(f.expenditure_amount), 0.0) AS total_expenditure
            FROM projects p
            JOIN states s ON p.state_id = s.state_id
            LEFT JOIN financials f ON p.project_id = f.project_id
            LEFT JOIN risk_scores r ON p.project_id = r.project_id
            LEFT JOIN project_features pf ON p.project_id = pf.project_id
            WHERE {where_sql} AND p.district_name IS NOT NULL
            GROUP BY p.district_name, s.state_name;
        """)

        rows = db.execute(sql, params).mappings().all()

        items = [
            DistrictAnalyticsItem(
                district_name=r["district_name"],
                state_name=r["state_name"],
                total_projects=r["total_projects"],
                high_risk_projects=r["high_risk_projects"],
                critical_risk_projects=r["critical_risk_projects"],
                average_risk_score=float(r["average_risk_score"] or 0.0),
                average_delay_days=float(r["average_delay_days"] or 0.0),
                total_sanctioned=Decimal(str(r["total_sanctioned"])),
                total_expenditure=Decimal(str(r["total_expenditure"])),
            )
            for r in rows
        ]

        sort_clean = (sort_by or "projects").lower()
        if sort_clean in ("risk_score", "risk"):
            items.sort(key=lambda x: (x.average_risk_score, x.total_projects), reverse=True)
        elif sort_clean in ("delay", "delays"):
            items.sort(key=lambda x: (x.average_delay_days, x.total_projects), reverse=True)
        elif sort_clean in ("critical", "high_risk"):
            items.sort(key=lambda x: (x.critical_risk_projects + x.high_risk_projects, x.total_projects), reverse=True)
        elif sort_clean in ("sanctioned", "funds"):
            items.sort(key=lambda x: (x.total_sanctioned, x.total_projects), reverse=True)
        else:
            items.sort(key=lambda x: (x.total_projects, x.total_sanctioned), reverse=True)

        return DistrictAnalyticsResponse(
            districts=items[:limit],
            total_districts=len(items)
        )

    @staticmethod
    def get_delays_analytics(
        db: Session,
        state_name: Optional[str] = None,
        district_name: Optional[str] = None,
        status: Optional[str] = None,
        sector: Optional[str] = None,
        risk_level: Optional[str] = None,
        financial_year: Optional[str] = None,
    ) -> DelayAnalyticsResponse:
        """
        Delay statistics, delay buckets histogram, and top overdue projects.
        """
        where_sql, params = AnalyticsService._build_project_filters(
            state_name, district_name, risk_level, status, sector, financial_year
        )

        sql = text(f"""
            SELECT 
                p.project_id,
                p.project_title,
                s.state_name,
                p.district_name,
                p.sector,
                p.current_status,
                to_char(p.expected_completion_date, 'YYYY-MM-DD') AS expected_completion_date,
                coalesce(pf.delay_days, 0) AS pf_delay_days,
                rf.details AS delay_details,
                coalesce(r.overall_risk_score, 0.0) AS risk_score
            FROM projects p
            JOIN states s ON p.state_id = s.state_id
            LEFT JOIN project_features pf ON p.project_id = pf.project_id
            LEFT JOIN risk_scores r ON p.project_id = r.project_id
            LEFT JOIN risk_factors rf ON p.project_id = rf.project_id AND rf.engine_name = 'delay_detection'
            WHERE {where_sql};
        """)

        rows = db.execute(sql, params).mappings().all()

        delay_buckets = {
            "0 days": 0,
            "1-30 days": 0,
            "31-90 days": 0,
            "91-180 days": 0,
            "181-365 days": 0,
            "365+ days": 0,
        }

        on_time = 0
        delayed = 0
        severely_delayed = 0
        delays_list = []
        project_delays = []

        for r in rows:
            is_completed = (r["current_status"] or "").lower() == "completed"
            pf_d = r["pf_delay_days"] or 0
            details = r["delay_details"] or {}
            overdue_days = details.get("overdue_days") if isinstance(details, dict) else None

            if is_completed:
                delay = max(0, pf_d)
            else:
                delay = int(overdue_days if overdue_days is not None else max(0, pf_d))

            project_delays.append({
                "project_id": r["project_id"],
                "project_title": r["project_title"] or "Developmental Project",
                "state_name": r["state_name"],
                "district_name": r["district_name"] or "District",
                "sector": r["sector"] or "General",
                "days_delayed": delay,
                "expected_completion_date": r["expected_completion_date"],
                "current_status": r["current_status"] or "In Progress",
                "risk_score": float(r["risk_score"] or 0.0),
            })

            if delay <= 0:
                on_time += 1
                delay_buckets["0 days"] += 1
            else:
                delayed += 1
                delays_list.append(delay)
                if delay > 90:
                    severely_delayed += 1

                if 1 <= delay <= 30:
                    delay_buckets["1-30 days"] += 1
                elif 31 <= delay <= 90:
                    delay_buckets["31-90 days"] += 1
                elif 91 <= delay <= 180:
                    delay_buckets["91-180 days"] += 1
                elif 181 <= delay <= 365:
                    delay_buckets["181-365 days"] += 1
                else:
                    delay_buckets["365+ days"] += 1

        avg_delay = round(sum(delays_list) / len(delays_list), 1) if delays_list else 0.0
        max_delay = max(delays_list) if delays_list else 0

        # Sort top delayed
        project_delays.sort(key=lambda x: (x["days_delayed"], x["risk_score"]), reverse=True)
        top_delayed = [TopDelayedProjectItem(**p) for p in project_delays[:10]]

        return DelayAnalyticsResponse(
            total_projects_assessed=len(rows),
            on_time_count=on_time,
            delayed_count=delayed,
            severely_delayed_count=severely_delayed,
            average_delay_days=avg_delay,
            max_delay_days=max_delay,
            delay_buckets=delay_buckets,
            top_delayed_projects=top_delayed,
        )

    @staticmethod
    def get_cost_anomalies_analytics(
        db: Session,
        state_name: Optional[str] = None,
        district_name: Optional[str] = None,
        status: Optional[str] = None,
        sector: Optional[str] = None,
        risk_level: Optional[str] = None,
        financial_year: Optional[str] = None,
    ) -> CostAnomalyAnalyticsResponse:
        """
        Cost anomaly statistics, peer median comparisons, and deviation histogram.
        """
        where_sql, params = AnalyticsService._build_project_filters(
            state_name, district_name, risk_level, status, sector, financial_year
        )

        sql = text(f"""
            SELECT 
                p.project_id,
                p.project_title,
                s.state_name,
                p.district_name,
                p.sector,
                rf.score AS cost_score,
                rf.reason,
                rf.details,
                coalesce(r.overall_risk_score, 0.0) AS risk_score,
                coalesce(f.expenditure_amount, 0.0) AS expenditure,
                coalesce(f.sanctioned_amount, 0.0) AS sanctioned
            FROM projects p
            JOIN states s ON p.state_id = s.state_id
            LEFT JOIN financials f ON p.project_id = f.project_id
            LEFT JOIN risk_scores r ON p.project_id = r.project_id
            LEFT JOIN risk_factors rf ON p.project_id = rf.project_id AND rf.engine_name = 'cost_anomaly'
            WHERE {where_sql};
        """)

        rows = db.execute(sql, params).mappings().all()

        dev_buckets = {
            "<= 0%": 0,
            "1-25%": 0,
            "26-50%": 0,
            "51-100%": 0,
            "> 100%": 0,
        }

        normal_count = 0
        anomalous_count = 0
        deviations = []
        anomaly_items = []

        for r in rows:
            details = r["details"] if isinstance(r["details"], dict) else {}
            score = float(r["cost_score"] or 0.0)
            dev_pct = float(details.get("deviation_percentage") or 0.0)
            peer_med = Decimal(str(details.get("peer_median") or (r["sanctioned"] or 0)))
            eval_cost = Decimal(str(details.get("evaluated_cost") or (r["expenditure"] or 0)))
            z_score = float(details.get("robust_z_score") or 0.0)
            anom_type = str(details.get("anomaly_type") or "STANDARD_COST")

            is_anomaly = score >= 30 or dev_pct > 25.0
            if is_anomaly:
                anomalous_count += 1
            else:
                normal_count += 1

            deviations.append(dev_pct)

            if dev_pct <= 0:
                dev_buckets["<= 0%"] += 1
            elif 1 <= dev_pct <= 25:
                dev_buckets["1-25%"] += 1
            elif 26 <= dev_pct <= 50:
                dev_buckets["26-50%"] += 1
            elif 51 <= dev_pct <= 100:
                dev_buckets["51-100%"] += 1
            else:
                dev_buckets["> 100%"] += 1

            anomaly_items.append(TopCostAnomalyItem(
                project_id=r["project_id"],
                project_title=r["project_title"] or "Developmental Project",
                state_name=r["state_name"],
                district_name=r["district_name"] or "District",
                sector=r["sector"] or "General",
                evaluated_cost=eval_cost,
                peer_median=peer_med,
                deviation_percentage=round(dev_pct, 1),
                robust_z_score=round(z_score, 2),
                anomaly_type=anom_type,
                reason=r["reason"] or "Cost evaluation against peer median",
                risk_score=float(r["risk_score"] or 0.0),
            ))

        total = len(rows)
        rate_pct = round((anomalous_count / total) * 100.0, 1) if total > 0 else 0.0
        avg_dev = round(sum(deviations) / len(deviations), 1) if deviations else 0.0

        # Sort largest deviations
        anomaly_items.sort(key=lambda x: (x.deviation_percentage, x.risk_score), reverse=True)

        return CostAnomalyAnalyticsResponse(
            total_projects_assessed=total,
            normal_cost_count=normal_count,
            cost_anomalous_count=anomalous_count,
            cost_anomaly_rate_pct=rate_pct,
            average_deviation_pct=avg_dev,
            deviation_distribution=dev_buckets,
            largest_deviations=anomaly_items[:10],
        )

    @staticmethod
    def get_temporal_trends(
        db: Session,
        state_name: Optional[str] = None,
        district_name: Optional[str] = None,
        risk_level: Optional[str] = None,
        sector: Optional[str] = None,
        status: Optional[str] = None,
        financial_year: Optional[str] = None,
        granularity: str = "month",
    ) -> TrendAnalyticsResponse:
        """
        Longitudinal time-series analysis over project sanction dates.
        """
        where_sql, params = AnalyticsService._build_project_filters(
            state_name, district_name, risk_level, status, sector, financial_year
        )

        sql = text(f"""
            SELECT 
                to_char(p.sanction_date, 'YYYY-MM') AS period,
                count(p.project_id) AS project_count,
                coalesce(round(avg(r.overall_risk_score), 2), 0.0) AS avg_risk,
                count(CASE WHEN UPPER(r.risk_level) IN ('HIGH', 'CRITICAL') OR r.overall_risk_score >= 60 THEN 1 END) AS high_risk_count,
                count(CASE WHEN pf.delay_days > 0 OR p.current_status = 'Stalled' THEN 1 END) AS delayed_count,
                count(CASE WHEN rf_cost.score >= 30 OR pf.cost_deviation > 0 THEN 1 END) AS cost_anomalies_count,
                coalesce(sum(f.sanctioned_amount), 0.0) AS sanctioned_amt,
                coalesce(sum(f.expenditure_amount), 0.0) AS expenditure_amt,
                coalesce(sum(f.released_amount), 0.0) AS released_amt
            FROM projects p
            JOIN states s ON p.state_id = s.state_id
            LEFT JOIN financials f ON p.project_id = f.project_id
            LEFT JOIN risk_scores r ON p.project_id = r.project_id
            LEFT JOIN project_features pf ON p.project_id = pf.project_id
            LEFT JOIN risk_factors rf_cost ON p.project_id = rf_cost.project_id AND rf_cost.engine_name = 'cost_anomaly'
            WHERE {where_sql} AND p.sanction_date IS NOT NULL
            GROUP BY to_char(p.sanction_date, 'YYYY-MM')
            ORDER BY period ASC;
        """)

        rows = db.execute(sql, params).mappings().all()

        points = []
        cum_count = 0
        for r in rows:
            cnt = r["project_count"] or 0
            cum_count += cnt
            sanctioned_cr = round(float(r["sanctioned_amt"] or 0.0) / 10000000.0, 2)
            spent_cr = round(float(r["expenditure_amt"] or 0.0) / 10000000.0, 2)
            rel_cr = round(float(r["released_amt"] or 0.0) / 10000000.0, 2)
            util_rate = round((spent_cr / rel_cr) * 100.0, 1) if rel_cr > 0 else (round((spent_cr / sanctioned_cr) * 100.0, 1) if sanctioned_cr > 0 else 0.0)

            points.append(TrendPointItem(
                period=r["period"],
                project_count=cnt,
                cumulative_projects=cum_count,
                average_risk_score=float(r["avg_risk"] or 0.0),
                high_risk_count=r["high_risk_count"] or 0,
                delayed_count=r["delayed_count"] or 0,
                cost_anomalies_count=r["cost_anomalies_count"] or 0,
                sanctioned_amount_cr=sanctioned_cr,
                expenditure_amount_cr=spent_cr,
                utilization_rate_pct=util_rate,
            ))

        return TrendAnalyticsResponse(
            granularity=granularity,
            trend_points=points,
        )

    @staticmethod
    def get_map_analytics(
        db: Session,
        metric: str = "projects",
        state_name: Optional[str] = None,
        risk_level: Optional[str] = None,
        status: Optional[str] = None,
        sector: Optional[str] = None,
        financial_year: Optional[str] = None,
    ) -> MapAnalyticsResponse:
        """
        Generates geospatial choropleth state data with normalized density scores.
        """
        where_sql, params = AnalyticsService._build_project_filters(
            state_name, None, risk_level, status, sector, financial_year
        )

        sql = text(f"""
            SELECT 
                s.state_name,
                count(p.project_id) AS total_projects,
                count(CASE WHEN UPPER(r.risk_level) = 'HIGH' OR (r.overall_risk_score >= 60 AND r.overall_risk_score < 80) THEN 1 END) AS high_risk_projects,
                count(CASE WHEN UPPER(r.risk_level) = 'CRITICAL' OR r.overall_risk_score >= 80 THEN 1 END) AS critical_risk_projects,
                coalesce(round(avg(r.overall_risk_score), 2), 0.0) AS average_risk_score,
                coalesce(round(avg(CASE WHEN pf.delay_days > 0 THEN pf.delay_days ELSE 0 END), 1), 0.0) AS average_delay_days,
                coalesce(sum(f.sanctioned_amount), 0.0) AS total_sanctioned,
                coalesce(sum(f.expenditure_amount), 0.0) AS total_expenditure
            FROM states s
            JOIN projects p ON s.state_id = p.state_id
            LEFT JOIN financials f ON p.project_id = f.project_id
            LEFT JOIN risk_scores r ON p.project_id = r.project_id
            LEFT JOIN project_features pf ON p.project_id = pf.project_id
            WHERE {where_sql}
            GROUP BY s.state_name;
        """)

        rows = db.execute(sql, params).mappings().all()

        state_data = []
        max_val = 1.0

        for r in rows:
            name = r["state_name"]
            code = AnalyticsService.STATE_NAME_TO_CODE.get(name, f"IN-{name[:2].upper()}")
            s_cr = round(float(r["total_sanctioned"] or 0.0) / 10000000.0, 2)
            e_cr = round(float(r["total_expenditure"] or 0.0) / 10000000.0, 2)
            cnt = r["total_projects"] or 0
            risk_sc = float(r["average_risk_score"] or 0.0)
            del_days = float(r["average_delay_days"] or 0.0)

            # Determine value by active metric
            m = (metric or "projects").lower()
            if m == "risk_score":
                val = risk_sc
            elif m == "delay":
                val = del_days
            elif m in ("sanctioned", "funds"):
                val = s_cr
            else:
                val = float(cnt)

            if val > max_val:
                max_val = val

            state_data.append({
                "state_name": name,
                "state_code": code,
                "total_projects": cnt,
                "high_risk_projects": r["high_risk_projects"] or 0,
                "critical_risk_projects": r["critical_risk_projects"] or 0,
                "average_risk_score": risk_sc,
                "average_delay_days": del_days,
                "sanctioned_amount_cr": s_cr,
                "expenditure_amount_cr": e_cr,
                "metric_val": val,
            })

        # Calculate normalized density score (10 to 100)
        items = []
        for d in state_data:
            density = round((d["metric_val"] / max_val) * 90.0 + 10.0, 1) if max_val > 0 else 10.0
            items.append(MapStateItem(
                state_name=d["state_name"],
                state_code=d["state_code"],
                total_projects=d["total_projects"],
                high_risk_projects=d["high_risk_projects"],
                critical_risk_projects=d["critical_risk_projects"],
                average_risk_score=d["average_risk_score"],
                average_delay_days=d["average_delay_days"],
                sanctioned_amount_cr=d["sanctioned_amount_cr"],
                expenditure_amount_cr=d["expenditure_amount_cr"],
                density_score=density,
            ))

        return MapAnalyticsResponse(
            states=items,
            active_metric=metric or "projects",
            max_value=max_val,
        )

