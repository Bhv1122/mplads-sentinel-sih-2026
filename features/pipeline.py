"""
features/pipeline.py
=============================================================================
End-to-end Feature Engineering Pipeline orchestrator.
Loads, merges, transforms, validates, and profiles all derived features
for the MPLADS project governance and predictive risk engine.
=============================================================================
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
import pandas as pd
import numpy as np

from features.config import FeatureConfig
from features.date_features import compute_delay_days, compute_project_duration
from features.financial_features import compute_utilization_ratio, compute_cost_deviation
from features.progress_features import compute_progress_gap
from features.category_features import compute_cost_per_category

logger = logging.getLogger("features.pipeline")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class FeatureEngineeringPipeline:
    """
    Deterministic pipeline for engineering derived governance and risk features
    from raw and cleaned MPLADS microdata.
    """

    def __init__(self, config: Optional[FeatureConfig] = None):
        self.config = config or FeatureConfig()

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Applies all feature transformations sequentially to an input DataFrame.
        Preserves all raw/original columns without mutation.

        Derived Features Added:
            1. Date & Timeline:
                - delay_days, is_delayed, sanction_sla_delay_days
                - planned_duration_days, actual_duration_days, elapsed_duration_days
                - admin_sanction_duration_days, tendering_duration_days, total_planned_lifecycle_days
            2. Financial & Variance:
                - utilization_ratio, utilization_ratio_sanctioned, utilization_ratio_released
                - cost_deviation, cost_deviation_sanction, cost_deviation_sanction_pct
                - cost_deviation_expenditure, cost_deviation_expenditure_pct, has_cost_overrun
                - unreleased_allocation
            3. Progress Telemetry:
                - planned_schedule_pct, progress_gap, progress_gap_schedule, progress_gap_fin_phy
                - is_schedule_lagging, is_disbursement_skewed
            4. Categorical Benchmarks:
                - category_mean_cost, category_median_cost, category_std_cost
                - cost_per_category, cost_relative_to_category, cost_category_zscore
                - category_project_count
        """
        logger.info(f"Executing Feature Engineering Pipeline on {len(df)} records...")
        featured_df = df.copy()

        # Step 1: Date & Lifecycle Durations
        featured_df = compute_delay_days(featured_df, self.config)
        featured_df = compute_project_duration(featured_df, self.config)

        # Step 2: Financial Utilization & Cost Deviations
        featured_df = compute_utilization_ratio(featured_df, self.config)
        featured_df = compute_cost_deviation(featured_df, self.config)

        # Step 3: Progress Discrepancy & Schedule Trajectory
        featured_df = compute_progress_gap(featured_df, self.config)

        # Step 4: Categorical Sector Cost Benchmarks
        featured_df = compute_cost_per_category(featured_df, self.config)

        logger.info(f"Pipeline complete. Generated {len(featured_df.columns)} total columns ({len(featured_df.columns) - len(df.columns)} newly derived).")
        return featured_df

    @staticmethod
    def load_cleaned_data(data_dir: Optional[Union[str, Path]] = None) -> pd.DataFrame:
        """
        Loads and joins Phase 2 cleaned CSV files:
        clean_projects.csv + clean_financials.csv + clean_progress.csv
        """
        if data_dir is None:
            # Default to data/cleaned/ in repository root
            base_dir = Path(__file__).resolve().parent.parent
            data_dir = base_dir / "data" / "cleaned"
        else:
            data_dir = Path(data_dir)

        proj_path = data_dir / "clean_projects.csv"
        fin_path = data_dir / "clean_financials.csv"
        prog_path = data_dir / "clean_progress.csv"

        if not proj_path.exists():
            raise FileNotFoundError(f"Projects file not found at {proj_path}")

        logger.info(f"Loading cleaned data from {data_dir}...")
        projects_df = pd.read_csv(proj_path)

        # Merge financials if present
        if fin_path.exists():
            fin_df = pd.read_csv(fin_path)
            # Avoid duplicate project_id columns on merge
            common_cols = [c for c in fin_df.columns if c in projects_df.columns and c != "project_id"]
            if common_cols:
                fin_df = fin_df.drop(columns=common_cols)
            merged = pd.merge(projects_df, fin_df, on="project_id", how="left")
        else:
            logger.warning(f"Financials file not found at {fin_path}. Proceeding with projects only.")
            merged = projects_df

        # Merge latest progress telemetry if present
        if prog_path.exists():
            prog_df = pd.read_csv(prog_path)
            # Ensure chronological latest reported_date per project
            prog_df["reported_date"] = pd.to_datetime(prog_df["reported_date"], errors="coerce")
            latest_prog = prog_df.sort_values("reported_date").groupby("project_id").last().reset_index()

            common_prog_cols = [c for c in latest_prog.columns if c in merged.columns and c != "project_id"]
            if common_prog_cols:
                latest_prog = latest_prog.drop(columns=common_prog_cols)
            merged = pd.merge(merged, latest_prog, on="project_id", how="left")
        else:
            logger.warning(f"Progress file not found at {prog_path}. Proceeding without progress telemetry.")

        logger.info(f"Joined dataset ready with {len(merged)} rows and {len(merged.columns)} columns.")
        return merged

    def run(
        self,
        input_data: Optional[pd.DataFrame] = None,
        data_dir: Optional[Union[str, Path]] = None,
        output_path: Optional[Union[str, Path]] = None
    ) -> pd.DataFrame:
        """
        Executes end-to-end data ingestion, feature generation, and export.
        """
        if input_data is not None:
            raw_df = input_data
        else:
            raw_df = self.load_cleaned_data(data_dir=data_dir)

        featured_df = self.transform(raw_df)

        if output_path is not None:
            out_file = Path(output_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            featured_df.to_csv(out_file, index=False)
            logger.info(f"Exported engineered feature dataset to {out_file}")

            # Also export dedicated clean_project_features.csv for database loading
            cleaned_dir = out_file.parent.parent / "cleaned"
            if cleaned_dir.exists():
                derived_cols = ["project_id"] + [
                    c for c in featured_df.columns if c not in raw_df.columns
                ]
                # Ensure unique columns
                derived_cols = list(dict.fromkeys(derived_cols))
                features_table_df = featured_df[derived_cols].copy()
                clean_feat_file = cleaned_dir / "clean_project_features.csv"
                features_table_df.to_csv(clean_feat_file, index=False)
                logger.info(f"Exported clean_project_features.csv to {clean_feat_file}")

        return featured_df

    @staticmethod
    def get_feature_groups() -> Dict[str, List[str]]:
        """
        Returns categorized feature listings separating pre-sanction modeling features
        from in-flight governance surveillance features.
        """
        return {
            "core_identity": [
                "project_id", "project_code", "project_title", "sector", "sub_sector",
                "state_id", "constituency_id", "district_name", "implementing_agency",
                "mp_name", "financial_year", "current_status"
            ],
            "recommendation_time_features": [
                "recommended_amount", "sanctioned_amount",
                "cost_deviation_sanction", "cost_deviation_sanction_pct",
                "cost_per_category", "cost_relative_to_category", "cost_category_zscore",
                "planned_duration_days", "admin_sanction_duration_days",
                "tendering_duration_days", "sanction_sla_delay_days", "category_project_count"
            ],
            "in_flight_monitoring_features": [
                "released_amount", "expenditure_amount", "unspent_balance",
                "utilization_ratio", "utilization_ratio_sanctioned", "utilization_ratio_released",
                "cost_deviation_expenditure", "cost_deviation_expenditure_pct", "has_cost_overrun",
                "unreleased_allocation", "physical_progress_pct", "financial_progress_pct",
                "planned_schedule_pct", "progress_gap", "progress_gap_schedule", "progress_gap_fin_phy",
                "delay_days", "is_delayed", "elapsed_duration_days", "actual_duration_days",
                "project_duration", "project_duration_days",
                "is_schedule_lagging", "is_disbursement_skewed"
            ]
        }
