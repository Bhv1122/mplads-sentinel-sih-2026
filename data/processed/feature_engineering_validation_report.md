# Phase 5 Feature Engineering Validation Report

Evaluation of derived features, formulas, numerical boundaries, and validity metrics.

| feature | formula | minimum | maximum | mean | median | missing_count | invalid_count | example_values |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| delay_days | (actual_completion - expected_completion) if completed else max(0, as_of_date - expected_completion) | -10 | 95 | 7.65 | 0 | 0 | 0 | -10, 0, -5 |
| is_delayed | delay_days > 0 | False | True | 0.10 | False | 0 | 0 | False, True |
| utilization_ratio | expenditure_amount / (sanctioned_amount + epsilon) | 0.1250 | 0.9875 | 0.7063 | 0.8750 | 0 | 0 | 0.9667, 0.9, 0.875 |
| utilization_ratio_released | expenditure_amount / (released_amount + epsilon) | 0.1250 | 0.9875 | 0.7063 | 0.8750 | 0 | 0 | 0.9667, 0.9, 0.875 |
| utilization_ratio_sanctioned | expenditure_amount / (sanctioned_amount + epsilon) | 0.0625 | 0.9875 | 0.5626 | 0.4375 | 0 | 0 | 0.9667, 0.72, 0.4375 |
| cost_per_category | mean(sanctioned_amount) grouped by sector | 1,600,000.00 | 3,900,000.00 | 2,570,000.00 | 2,333,333.33 | 0 | 0 | 1775000.0, 2433333.33, 3900000.0 |
| cost_relative_to_category | sanctioned_amount / category_mean_cost | 0.4038 | 1.6901 | 1.0000 | 1.0071 | 0 | 0 | 0.8451, 1.0274, 0.8205 |
| cost_category_zscore | (sanctioned_amount - category_mean_cost) / (category_std_cost + epsilon) | -1.1388 | 1.3346 | 0.0000 | 0.0136 | 0 | 0 | -0.2996, 0.165, -1.0675 |
| progress_gap | planned_schedule_pct - physical_progress_pct | -41.36 | 41.38 | -6.1105 | 0.0000 | 0 | 0 | 0.0, -11.95, -30.7 |
| progress_gap_schedule | planned_schedule_pct - physical_progress_pct | -41.36 | 41.38 | -6.1105 | 0.0000 | 0 | 0 | 0.0, -11.95, -30.7 |
| progress_gap_fin_phy | financial_progress_pct - physical_progress_pct | -45.00 | 30.00 | 0.1295 | -1.3800 | 0 | 0 | -3.33, 25.0, 22.5 |
| cost_deviation | expenditure_amount - sanctioned_amount | -3,000,000 | -20,000 | -1,274,000.00 | -1,500,000 | 0 | 0 | -50000.0, -700000.0, -1800000.0 |
| cost_deviation_sanction | sanctioned_amount - recommended_amount | -300,000 | 0 | -70,000.00 | 0 | 0 | 0 | 0.0, -300000.0, -200000.0 |
| cost_deviation_sanction_pct | ((sanctioned - recommended) / recommended) * 100 | -9.0900 | 0.0000 | -1.9790 | 0.0000 | 0 | 0 | 0.0, -8.57, -6.67 |
| cost_deviation_expenditure | expenditure_amount - sanctioned_amount | -3,000,000 | -20,000 | -1,274,000.00 | -1,500,000 | 0 | 0 | -50000.0, -700000.0, -1800000.0 |
| cost_deviation_expenditure_pct | ((expenditure - sanctioned) / sanctioned) * 100 | -93.75 | -1.2500 | -43.74 | -56.25 | 0 | 0 | -3.33, -28.0, -56.25 |
| project_duration | max(0, (actual_completion if completed else ref_date) - start_date) | 46 | 118 | 77.40 | 74 | 0 | 0 | 118, 87, 71 |
| project_duration_days | max(0, (actual_completion if completed else ref_date) - start_date) | 46 | 118 | 77.40 | 74 | 0 | 0 | 118, 87, 71 |
| planned_duration_days | max(0, expected_completion_date - start_date) | 49 | 258 | 151.75 | 157 | 0 | 0 | 128, 164, 207 |
| actual_duration_days | max(0, actual_completion_date - start_date) (NaN if ongoing) | 46 | 118 | 81.75 | 82 | 12 | 0 | 118.0, 87.0, 65.0 |
| elapsed_duration_days | max(0, ref_date - start_date) | 48 | 128 | 91.35 | 101 | 0 | 0 | 113, 87, 71 |
| admin_sanction_duration_days | max(0, sanction_date - recommendation_date) | 17 | 45 | 32.55 | 38 | 0 | 0 | 25, 42, 45 |
| sanction_sla_delay_days | max(0, (sanction_date - recommendation_date) - 75) | 0 | 0 | 0.00 | 0 | 0 | 0 | 0 |
| unreleased_allocation | max(0, sanctioned_amount - released_amount) | 0 | 2,400,000 | 872,500.00 | 850,000 | 0 | 0 | 0.0, 500000.0, 1600000.0 |

### Validation Summary
- Total Features Profiled: 24
- Features with Zero Invalid Values: 24 / 24
- Features with Zero Missing Values: 23 / 24
- Note: `actual_duration_days` missing count is expected for active/ongoing works (avoids survival bias).
