# MPLADS Machine Learning & Analytical Feasibility Assessment
**Project**: SIH 2026 – Member of Parliament Local Area Development Scheme (MPLADS) Data & Governance Analytics  
**Date**: September 2026  
**Status**: Comprehensive Feasibility & Task Viability Evaluation  
**Basis**: Grounded strictly on actual MPLADS data discovered in `data/raw/`, `data/processed/`, and the e-SAKSHI / GoI portal architecture.  

---

## Executive Summary & Feasibility Scorecard

This assessment evaluates the mathematical, statistical, and operational viability of six proposed machine learning and data science tasks based **strictly on the actual MPLADS data discovered and downloaded**. In adherence to ML best practices and data governance standards, field meanings are grounded in official guidelines, and no phantom capabilities are assumed.

### Feasibility Summary Matrix

| # | Task Name | Task Type | Target Availability | Observation Sample Size ($N$) | Data Leakage Risk | Feasibility Confidence | Recommended Action for SIH 2026 |
|---|---|---|---|---|---|---|---|
| **1** | **Project Completion Prediction** | Binary Classification / Survival Analysis | **Unavailable at work level** in current tables; Biased in API | $N = 0$ (Current)<br>$N \approx 34,564$ (If scraped) | **High** (Progress post-sanction leaks completion) | **LOW** | Pivot to aggregate completion rate forecasting or scrape work microdata with survival censoring. |
| **2** | **Project Cost Prediction** | Supervised Regression | **Unavailable at work level** (No BOQ/specifications) | $N = 0$ (Current)<br>$N \approx 79,483$ (If scraped) | **High** (Sanction cap proxies recommendation) | **LOW** | Not viable for engineering overruns; viable only for predicting allocation ceilings. |
| **3** | **Delay & SLA Breach Prediction** | Regression / Classification (SLA >75 days) | **Partial** (Paired dates in e-SAKSHI modal tables) | $N = 0$ (Current)<br>$N \approx 79,483$ (If scraped) | **Medium** (Lookahead leakage if post-sanction vars used) | **MEDIUM** *(HIGH for Sanction SLA Breach)* | Focus specifically on **75-Day Statutory Sanction SLA Breach** using recommendation-time features. |
| **4** | **Expenditure & Utilization Forecasting** | Time Series Forecasting / Panel Regression | **Fully Available** (33-yr national series + 36-state panel) | $N = 33$ (Years)<br>$N = 36$ (States) | **Low** (If chronological splits are strictly maintained) | **HIGH** | Build ARIMA / Ridge / ElasticNet models for national outlays and state utilization trajectories. |
| **5** | **Work Status Prediction** | Multi-Class Classification | **Unavailable at work level** in current tables; Censored in API | $N = 0$ (Current)<br>$N \approx 107,266$ (If scraped) | **Critical** (Sanction fields directly disclose status) | **LOW to MEDIUM** | Feasible only if strictly restricted to recommendation-time text and sector metadata. |
| **6** | **Constituency-Level Analysis** | Clustering, Benchmarking & Anomaly Detection | **Fully Available** (543 seats with reservations & state metrics) | $N = 543$ (Seats)<br>$N = 36$ (States) | **Zero** (Unsupervised & normative benchmarking) | **VERY HIGH** | **Prime Candidate for SIH 2026**: Cluster constituencies, audit SC/ST equity compliance, and flag outliers. |

---

## Detailed Task-by-Task Feasibility Audit

---

### Task 1: Project Completion Prediction
*Predict whether an individual recommended project will reach 'Completed' status or remain incomplete / abandoned.*

#### 1. Target Availability
- **In Downloaded Datasets**: **Unavailable**. Current downloaded tables contain macro work counts (`works_completed`, `works_sanctioned`, `works_recommended`) aggregated at the national level (`esakshi_national_summary.csv`) and state level (`parliament_qa_state_expenditure.csv`), but zero individual project rows with a completion label.
- **In Discovered e-SAKSHI API**: **Heavily Biased / Truncated**. The public endpoint `/rest/PreLoginCitizenWorkRcmdRest/getAllCompletedWorkByMP` returns *only works that have already completed*. In modal tables (`poptable.js`), works are divided into status buckets (`Works Completed`, `Works Sanctioned`), but without persistent lifecycle tracking showing stalled vs. abandoned works.

#### 2. Candidate Features Available
- *Geographic*: State, Parliamentary Constituency, District (IDA).
- *Institutional*: Member of Parliament Name, House (Lok Sabha / Rajya Sabha), Reservation Category (General, SC, ST).
- *Project-Level (from e-SAKSHI modal tables)*: Work Category / Sector (e.g. Drinking Water, Roads, Sanitation, Health), Recommended Date, Sanction Date, Sanction Amount (₹).

#### 3. Missing Critical Information
- **Contractor / Implementing Agency Profile**: Agency type (Gram Panchayat, PWD, CPWD, private contractor), past delivery record, bonding capacity.
- **Physical Milestone Telemetry**: Percentage completion intervals (25%, 50%, 75%).
- **Land & Regulatory Clearances**: Site ownership confirmation, Forest / Environmental clearances, Right-of-Way (RoW) approvals.
- **Terrain & Accessibility Indices**: Rural isolation, flood-plain status, hill-terrain difficulty.
- **True Negative Labels**: The portal does not publish a clear status of "Abandoned" or "Defunct"; works simply remain in "Sanctioned / In Progress" indefinitely (right-censoring).

#### 4. Sample-Size Limitations
- Current structured dataset: $N = 0$ work-level records.
- If e-SAKSHI modal tables are scraped: $N \approx 34,564$ completed works nationally, but with near-zero verified "abandoned" negative labels, leading to severe class imbalance and survival bias.

#### 5. Data Leakage Risks
- **Catastrophic Lookahead Leakage**:
  - `Payment Status` (`Paid` / `Pending`): If included, a payment status of `Paid` directly reveals that the work was completed and billed.
  - `Image` (Geo-tagged asset photo): Completed works have post-construction photographs uploaded via mobile app; using attachment existence as a feature directly leaks the target.
  - `Sanction Date` / `Sanction Amount`: Cannot be used if predicting completion from the point of initial MP recommendation.

#### 6. Feasibility Confidence: **LOW**
- *Verdict*: Supervised binary classification at the project level is **not feasible** on current downloaded data. Even with microdata scraping, severe right-censoring (lack of true terminal failure labels) and survival bias make standard classification problematic without survival analysis modeling.

---

### Task 2: Project Cost & Cost-Overrun Prediction
*Predict the final expenditure or sanctioned cost of a proposed MPLADS developmental work.*

#### 1. Target Availability
- **In Downloaded Datasets**: **Unavailable at project level**. Available only as macro cumulative expenditures and calamity consent amounts (`consented_amount_inr` for 12 disaster relief events).
- **In Discovered e-SAKSHI API**: `Sanction Amount (₹)` is exposed in modal tables, but the *actual final billed cost* is rarely differentiated from the administrative sanction limit in the public view.

#### 2. Candidate Features Available
- Work Category (Sector), Constituency, State, Recommendation Year, MP House.
- Text description from the `WORK` field (e.g. "Construction of Community Hall at Village X").

#### 3. Missing Critical Information
- **Bill of Quantities (BOQ)**: Structural engineering quantities (bags of cement, metric tons of reinforcement steel, cubic meters of earthwork).
- **Physical Asset Dimensions**: Road length (km), width (m), building plinth area (sq ft), water tank capacity (liters). Without physical dimensions, predicting whether a "Community Hall" costs ₹5 Lakhs or ₹50 Lakhs is mathematically ill-posed.
- **Schedule of Rates (SOR)**: District-level PWD Schedule of Rates applicable during the sanction year.
- **Tender Competition Metrics**: Number of bidding contractors, tender discount/premium percentage.

#### 4. Sample-Size Limitations
- Current downloaded tables: $N = 0$ project construction cost records ($N = 12$ for calamity consents).
- If scraped from e-SAKSHI: $N \approx 79,483$ sanctioned projects, but all lack physical dimension attributes.

#### 5. Data Leakage Risks
- **Proxy / Tautological Leakage**: Under MPLADS guidelines, MPs frequently recommend an exact round figure allocation (e.g. "₹10,00,000 for road works"). The District Authority typically issues administrative sanction up to that exact ceiling. Predicting `Sanction Amount` from `Recommended Amount` achieves an artificial $R^2 \approx 1.0$, which is trivial administrative tautology rather than genuine civil engineering cost estimation.

#### 6. Feasibility Confidence: **LOW**
- *Verdict*: Predicting actual construction expenditure or cost overruns is **not feasible** because physical engineering dimensions (length, area, volume) and contractor procurement bids are completely absent from the data.

---

### Task 3: Delay & Statutory SLA Breach Prediction
*Predict the time elapsed between MP recommendation and administrative sanction, and classify whether the work will breach the statutory 75-day SLA under Paragraph 3.5 of Guidelines.*

#### 1. Target Availability
- **In Downloaded Datasets**: **Unavailable at work level** (available as state sanction rates).
- **In Discovered e-SAKSHI API**: **High Quality & Grounded in Law**.
  - Modal tables contain paired timestamps: `Recommended date` and `Sanction Date`.
  - Target Variable 1 (Regression): $\text{Sanction Delay} = \text{Sanction Date} - \text{Recommended date}$ (in calendar days).
  - Target Variable 2 (Binary Classification): $\text{SLA Breach} = \mathbb{I}(\text{Sanction Delay} > 75\text{ days})$. This maps directly to Paragraph 3.5 of the statutory MPLADS Guidelines!

#### 2. Candidate Features Available (Strictly at Recommendation Time)
- State ID, State Name, Territorial Category (`State` vs `Union Territory`).
- Parliamentary Constituency ID, Reservation Category (`General`, `SC`, `ST`).
- Implementing District Authority (IDA / District Collectorate).
- Member of Parliament Name, House of Parliament (`Lok Sabha` vs `Rajya Sabha`).
- Work Category / Sector (Drinking Water, Sanitation, Roads, Education, Health, Community Assets).
- Temporal Features: Month of recommendation, Quarter, Financial Year, Proximity to Election Year (General / State Assembly elections).
- Text Features: NLP embeddings of project scope from `WORK` description.

#### 3. Missing Critical Information
- Dates when line agencies (PWD, Jal Nigam) returned technical feasibility estimates to the District Collector.
- Official Election Commission of India (ECI) Model Code of Conduct (MCC) freeze dates (during which sanctions are statutorily halted).
- District Collectorate staffing levels, backlog of pending files, and transfer frequency of District Magistrates.

#### 4. Sample-Size Limitations
- Current downloaded files: $N = 0$ work-level records.
- If scraped via e-SAKSHI API: $N \approx 79,483$ sanctioned projects with paired dates, representing an ideal sample size for Gradient Boosted Trees (XGBoost, LightGBM, CatBoost) and Logistic Regression.

#### 5. Data Leakage Risks
- **Severe Lookahead Risk**: Features generated *after* recommendation (e.g. `Sanction Amount`, `Executing Agency`, `Payment Status`) must be **strictly excluded**.
- **Survival / Right-Censoring Bias**: Works that have been recommended but have *not yet been sanctioned* after 100+ days will be absent from the sanctioned pairs list unless pending works are explicitly scraped and modeled using survival analysis (e.g., Cox Proportional Hazards or Kaplan-Meier estimators).

#### 6. Feasibility Confidence: **MEDIUM** *(HIGH for Sanction SLA Breach if micro-level paired dates are scraped)*
- *Verdict*: High-value, legally grounded use case for SIH 2026. Predicting the 75-day sanction bottleneck is technically feasible once recommendation-to-sanction date pairs are ingested.

---

### Task 4: Expenditure & Fund Utilization Forecasting
*Forecast future annual or cumulative fund expenditure, central disbursements, and unspent balance trajectories.*

#### 1. Target Availability
- **In Downloaded Datasets**: **Fully Available, Clean, and Audited**.
  - **National Level** (`union_budget_mplads_1993_2025.csv`): Continuous 33-year time series (FY 1993-94 to FY 2025-26) containing:
    * `actual_expenditure_cr`: Central disbursements from Consolidated Fund of India.
    * `revised_estimate_cr`: Mid-year revised budgetary allocations.
    * `budget_estimate_cr`: Annual budget estimates presented in Parliament.
    * `be_vs_actual_variance_cr`: Fiscal forecast variance.
  - **State Level** (`parliament_qa_state_expenditure.csv` & `master_dim_states_constituencies.csv`):
    * `utilization_rate_pct`: Cumulative financial utilization percentage across all 36 States/UTs.
    * `unspent_balance_cr`: Total idle funds lying with district authorities.
    * `expenditure_cr` and `released_cr`: State financial totals.

#### 2. Candidate Features Available
- **Temporal & Policy Regimes**: Financial Year index, Scheme Entitlement per MP (₹0.05 Cr in 1993, ₹1 Cr in 1994, ₹2 Cr in 1998, ₹5 Cr in 2011 to Present).
- **Macro Fiscal Indicators**: Prior-year Budget Estimates, Prior-year Actuals, Historical Variance, Major Head `3475`.
- **Electoral Cycle Variables**: General Election Years indicator (1996, 1998, 1999, 2004, 2009, 2014, 2019, 2024).
- **State Structural Features**: Total Lok Sabha seats, General seats, SC-reserved seats, ST-reserved seats, Geographic Category (`State` vs `Union Territory`).
- **Policy Shocks**: COVID-19 scheme suspension dummy variable (FY 2020-21 & FY 2021-22), e-SAKSHI / CNA reform dummy variable (FY 2023-24 onward).

#### 3. Missing Critical Information
- High-frequency monthly constituency-level bank debits (locked inside the internal PFMS/SBI CNA intranet).
- Interest accumulation rates at commercial banks during the legacy era.

#### 4. Sample-Size Limitations
- National Time Series: $N = 33$ annual observations. This is a compact sample size; deep learning architectures (LSTMs, Transformers) are unsuitable and will overfit. Classical econometric and statistical time-series models (ARIMA, SARIMAX, Holt-Winters, Bayesian Structural Time Series, Ridge Regression) are optimal.
- State Cross-Section: $N = 36$ state entities. Well-suited for Ordinary Least Squares (OLS), Beta Regression (for utilization bounded in $[0, 1]$), and Random Forests.

#### 5. Data Leakage Risks
- **Temporal / Information Leakage**: Using `revised_estimate_cr` (settled in November/December) to forecast total fiscal year expenditure at the time of initial February budget presentation without acknowledging that RE is not available in February.
- **Chronological Split Mandate**: Model evaluation **must** use chronological train/test splits (e.g., Train: 1993–2018, Test: 2019–2025) rather than random k-fold cross-validation, which causes severe temporal leakage.

#### 6. Feasibility Confidence: **HIGH**
- *Verdict*: Highly feasible, robust, and mathematically grounded on existing downloaded data. Yields immediate baseline forecasts for national scheme outlays and state utilization benchmarks.

---

### Task 5: Work Proposal Status Prediction
*Predict the operational lifecycle stage of an MP's recommended proposal (e.g., Recommended $\rightarrow$ Sanctioned $\rightarrow$ Completed $\rightarrow$ Rejected).*

#### 1. Target Availability
- **In Downloaded Datasets**: **Unavailable at project level** (only national/state macro totals available).
- **In Discovered e-SAKSHI API**: `Work Status` column is present in e-SAKSHI modal tables (`poptable.js`). However, rejected proposals are not maintained as a distinct publicly searchable category.

#### 2. Candidate Features Available (Strictly at Recommendation Time)
- Work Description Text (`WORK`), Work Category / Sector, State, District (IDA), MP Name, House (LS/RS), Recommendation Month.

#### 3. Missing Critical Information
- Specific statutory grounds for rejection (e.g., proposal violates Schedule-I of Guidelines: commercial asset, religious building, non-community asset).
- Land title verification records.

#### 4. Sample-Size Limitations
- Current downloaded datasets: $N = 0$ work-level rows.
- e-SAKSHI API: $N \approx 107,266$ recommended works, but distribution is heavily truncated toward sanctioned/completed projects.

#### 5. Data Leakage Risks
- **Extreme Target Leakage**: If any attribute populated *after* recommendation is included (e.g. `Sanction Date`, `Sanction Amount`, `Executing Agency`, `Payment Status`, `Image`), the status is trivially known and the model becomes invalid.

#### 6. Feasibility Confidence: **LOW to MEDIUM**
- *Verdict*: Feasible only if microdata is scraped and feature engineering is strictly restricted to text embeddings of the work title and administrative metadata known at recommendation time.

---

### Task 6: Constituency-Level Analysis & Governance Benchmarking
*Cluster constituencies into developmental performance tiers, identify equitable allocation compliance, and detect expenditure anomalies.*

#### 1. Target Availability
- **In Downloaded Datasets**: **100% Available, Clean, and Normalized**.
  - `esakshi_constituencies.csv`: All 543 Lok Sabha seats mapped across 36 States/UTs.
  - `master_dim_states_constituencies.csv`: Integrates geographic hierarchies, seat counts, constitutional reservations (`General`: 417, `SC`: 82, `ST`: 44), statutory minimum SC/ST quotas (15.0% and 7.5%), cumulative central releases, expenditures, and unspent balances.
  - `esakshi_calamity_relief.csv`: Itemized MP disaster relief contributions.

#### 2. Candidate Features Available
- **Constitutional Reservation Class**: `General`, `SC`, `ST` (Constitutional seat category).
- **Administrative Geography**: State ID, State Name, Territorial Category (`State` vs `Union Territory`).
- **Fiscal Delivery Metrics**: State-level `utilization_rate_pct`, `sanction_rate_pct`, `completion_rate_pct`, `unspent_balance_cr`.
- **Seat Concentration Indices**: Total seats in state, SC seat density ratio, ST seat density ratio.
- **Statutory Threshold Benchmarks**: Mandatory SC allocation (15.0%) and ST allocation (7.5%).
- **Disaster Relief Allocation Profile**: MP willingness to allocate funds across national vs state disaster events.

#### 3. Missing Critical Information
- Local ward/panchayat demographic indices (poverty rate, literacy) mapped to parliamentary boundaries (can be joined from Census 2011 or NDAP if needed).

#### 4. Sample-Size Limitations
- $N = 543$ Parliamentary Constituencies. This provides a statistically ideal, complete-population sample size ($N = 543$) with **0% missing values**.
- $N = 36$ States and Union Territories.

#### 5. Data Leakage Risks
- **Zero Leakage Risk**: As an unsupervised / comparative benchmarking task (Clustering, PCA, Isolation Forests, Disparity Indexing), there is no target label leakage. Statutory constants are utilized as fixed evaluation thresholds rather than predictive inputs.

#### 6. Feasibility Confidence: **VERY HIGH**
- *Verdict*: **The most viable, actionable, and impactful task for SIH 2026.** Can be executed immediately using the clean relational tables already present in `data/processed/`.

---

## Strategic Recommendations for SIH 2026

To maximize technical merit, data integrity, and real-world governance impact, the SIH 2026 solution architecture should focus on:

1. **Immediate Execution Priority**:
   - **Task 6 (Constituency Equity & Disparity Indexing)**: Deploy clustering (K-Means / Hierarchical), PCA dimensionality reduction, and statutory SC/ST compliance auditing across all 543 constituencies.
   - **Task 4 (Expenditure & Outlay Forecasting)**: Train econometric time-series models (SARIMAX, Holt-Winters, ElasticNet) on the 33-year Union Budget series (`union_budget_mplads_1993_2025.csv`) and state utilization panel.

2. **Targeted Micro-Level Expansion Priority**:
   - **Task 3 (75-Day Statutory Sanction SLA Breach Prediction)**: Expand the ingestion pipeline to extract paired `Recommended date` and `Sanction Date` records from the e-SAKSHI modal tables to build an automated early-warning system for district administrative delays.

3. **Tasks to Deprioritize or Redefine**:
   - Avoid general **Cost Overrun Prediction** (Task 2) due to the complete lack of physical dimensions (length, area, material quantities).
   - Avoid standard **Binary Completion Classification** (Task 1) unless framed under right-censored survival analysis.
