# MPLADS Phase 7 Risk & Anomaly Detection System
## Technical Architecture, Engine Specifications & Evaluation Guide

> **System Classification & Legal Disclaimer**  
> The Phase 7 Risk System is an automated, data-driven **risk/anomaly detection and administrative decision-support system**. It screens public works data to identify statistical cost outliers, potential scope duplication, timeline delays, financial/physical milestone discrepancies, and agency delivery friction.  
> **It does NOT make legal determinations or claim fraud, corruption, or wrongdoing with certainty.** All scores and findings represent triage indicators intended to direct human engineering audits and administrative reviews to where they are most needed.

---

## 1. System Architecture

The Phase 7 Risk System operates as a modular, 6-engine decision-support pipeline with central aggregation, atomic database persistence, and FastAPI REST endpoints.

```
                      ┌──────────────────────────────────────────────────────────┐
                      │              Input Project Record & Metadata             │
                      │  (projects, financials, progress, master dimensions)     │
                      └────────────────────────────┬─────────────────────────────┘
                                                   │
        ┌───────────────────┬──────────────────────┼──────────────────────┬───────────────────┐
        ▼                   ▼                      ▼                      ▼                   ▼
 ┌─────────────┐     ┌─────────────┐        ┌─────────────┐        ┌─────────────┐     ┌─────────────┐
 │  Engine 1   │     │  Engine 2   │        │  Engine 3   │        │  Engine 4   │     │  Engine 5   │
 │Cost Anomaly │     │  Duplicate  │        │    Delay    │        │  Progress   │     │   Agency    │
 │  Detection  │     │  Detection  │        │  Detection  │        │  Mismatch   │     │  Patterns   │
 └──────┬──────┘     └──────┬──────┘        └──────┬──────┘        └──────┬──────┘     └──────┬──────┘
        │                   │                      │                      │                   │
        │ [0–100, conf]     │ [0–100, conf]        │ [0–100, conf]        │ [0–100, conf]     │ [0–100, conf]
        └───────────────────┴──────────────────────┼──────────────────────┴───────────────────┘
                                                   │
                                                   ▼
                      ┌──────────────────────────────────────────────────────────┐
                      │                 Central Risk Aggregation                 │
                      │        Weighted Composite Score: S = Σ(w_i · s_i)        │
                      │         Configurable Dynamic Renormalization             │
                      │         Risk Tiers: LOW, MEDIUM, HIGH, CRITICAL          │
                      └────────────────────────────┬─────────────────────────────┘
                                                   │
                                                   ▼
                      ┌──────────────────────────────────────────────────────────┐
                      │           Engine 6 — Explained Risk Assessment           │
                      │      Ranked Factor Decomposition & Contribution Pts      │
                      │      Audit Evidence Extraction & Review Guidance         │
                      └────────────────────────────┬─────────────────────────────┘
                                                   │
                         ┌─────────────────────────┴─────────────────────────┐
                         ▼                                                   ▼
          ┌─────────────────────────────┐                     ┌─────────────────────────────┐
          │    PostgreSQL Persistence   │                     │      FastAPI Endpoints      │
          │   risk_scores, risk_factors │                     │  GET /projects/{id}/risk    │
          │  Idempotent Upsert & Log    │                     │  GET /high-risk, Analytics  │
          └─────────────────────────────┘                     └─────────────────────────────┘
```

### Execution Flow
1. **Context Initialization**: Pre-fetches corpus candidate descriptions and initializes in-memory embedding caches.
2. **Independent Engine Analysis**: Engines 1–5 process project attributes independently and output normalized scores $[0, 100]$, confidence ratings $[0.0, 1.0]$, and auditable evidence dictionaries.
3. **Central Aggregation**: The central service normalizes configured weights ($\sum w_i = 1.0$), handles missing or failed engines, computes the composite score, and assigns the risk tier.
4. **Explanation Generation (Engine 6)**: Synthesizes engine signals into ranked contributing factors and actionable, non-accusatory administrative recommendations.
5. **Atomic Persistence**: Upserts the composite score into `risk_scores` and individual engine metrics into `risk_factors` within an isolated database transaction.

---

## 2. The Six Risk Engines

### Engine 1: Cost Anomaly Detection
- **Purpose**: Identifies projects with abnormal cost profiles compared to peers in the same sector, state, or district, while preventing legitimately large approved budgets from being penalized.
- **Inputs**:
  - `financials.expenditure_amount`, `sanctioned_amount`, `released_amount`, `cost_overrun_pct`
  - `projects.sector`, `sub_sector`, `district_name`, `state_id`, `current_status`
  - `project_features.cost_per_day`, `project_duration_days`
- **Statistical Methods**:
  - **Peer Group Hierarchy**: Narrowest available peer group with $\ge 3$ projects (`sector_and_district` $\to$ `sector_and_state` $\to$ `sector_nationwide`).
  - **Robust Statistics**:
    $$\text{Median } (M) = \text{median}(X)$$
    $$\text{IQR} = Q_3 - Q_1$$
    $$\text{MAD} = \text{median}(|x_i - M|)$$
    $$\text{Robust } Z = \frac{0.6745 \cdot (x - M)}{\max(\text{MAD}, 1.0)}$$
    $$\text{Cost Ratio } (R) = \frac{x}{M}$$
- **Scoring & Protections**:
  - **Normal** ($R \le 1.35, Z \le 1.5$): Score $0–25$.
  - **Elevated / Outlier** ($R > 1.35$): Score $30–100$.
  - **Legitimacy Dampener**: If expenditure is within official sanction ($x \le \text{sanctioned} \times 1.02$) and cost overrun $\le 0\%$, score is capped at $\le 50$ (MEDIUM).
  - **Overrun Escalator**: If expenditure exceeds sanction by $> 15\%$, risk score is escalated into HIGH/CRITICAL ($60–100$).
  - **Dual-Sided Anomaly**: Unusually cheap expenditures ($< 15\%$ of peer median) for active projects trigger low-cost token booking warnings ($30–45$).

---

### Engine 2: Duplicate Detection
- **Purpose**: Detects potential duplicate proposals, repeated funding of identical assets, or scope overlap.
- **Inputs**:
  - `projects.project_title`, `project_description`
  - `projects.district_name`, `block_name`, `state_id`
  - `projects.sector`, `sub_sector`
- **Formulas & NLP Methods**:
  - **Semantic Vectorization**: Dense representations generated via SentenceTransformers (`all-MiniLM-L6-v2`) with sublinear TF-IDF fallback for resource-constrained environments.
  - **Cosine Similarity**:
    $$\text{sim}_{\text{raw}}(u, v) = \frac{u \cdot v}{\|u\|_2 \|v\|_2}$$
  - **Contextual Multipliers**:
    $$\text{sim}_{\text{adjusted}} = \text{sim}_{\text{raw}} \times M_{\text{location}} \times M_{\text{sector}}$$
    - Same block/district: $M_{\text{location}} = 1.25\times$
    - Same state: $M_{\text{location}} = 1.00\times$
    - Different state: $M_{\text{location}} = 0.60\times$ (dampens boilerplate government phrasing)
- **Scoring**:
  - $\text{sim} < 0.60$: Score 0 (LOW).
  - $0.60 \le \text{sim} < 0.75$: Score $30–59$ (MEDIUM, possible duplicate).
  - $0.75 \le \text{sim} \le 1.00$: Score $60–100$ (HIGH/CRITICAL, strong duplicate).

---

### Engine 3: Project Delay Detection
- **Purpose**: Assesses schedule slippage, stalled execution, and delivery timeline risks.
- **Inputs**:
  - `projects.recommendation_date`, `sanction_date`, `work_order_date`
  - `projects.expected_completion_date`, `actual_completion_date`, `current_status`
  - Current evaluation timestamp ($T_{\text{as\_of}}$)
- **Formulas & Timeline Calculations**:
  - **Planned Duration**: $D_{\text{planned}} = T_{\text{expected}} - T_{\text{work\_order}}$ (or $T_{\text{sanction}}$)
  - **Elapsed Duration**: $D_{\text{actual}} = \min(T_{\text{actual}}, T_{\text{as\_of}}) - T_{\text{work\_order}}$
  - **Overdue Days**:
    $$\text{Days}_{\text{overdue}} = \max(0, T_{\text{as\_of}} - T_{\text{expected}})$$
  - **Slippage Ratio**:
    $$\text{Slippage} = \frac{D_{\text{actual}} - D_{\text{planned}}}{D_{\text{planned}}} \times 100\%$$
- **Scoring**:
  - Ongoing project with $T_{\text{as\_of}} \le T_{\text{expected}}$: Score 0 (on schedule).
  - Overdue ongoing project: Bounded exponential/linear curve from score 30 (1 day overdue) to 100 ($\ge 365$ days overdue or $> 100\%$ slippage).
  - Stalled projects without progress updates: Scaled according to days dormant.

---

### Engine 4: Financial & Physical Progress Mismatch
- **Purpose**: Detects discrepancies between financial disbursements and verified on-site milestone progress.
- **Inputs**:
  - `progress.financial_progress_pct`, `progress.physical_progress_pct`, `progress.current_stage`
  - `financials.expenditure_amount`, `released_amount`, `sanctioned_amount`
- **Formulas**:
  - **Financial Progress** ($FP$):
    $$FP = \begin{cases} \text{progress.financial\_progress\_pct}, & \text{if present} \\ \frac{\text{expenditure}}{\text{released}} \times 100\%, & \text{fallback} \end{cases}$$
  - **Physical Progress** ($PP$): $\text{progress.physical\_progress\_pct}$
  - **Progress Gap**:
    $$\Delta = FP - PP$$
- **Bidirectional Scoring**:
  - $|\Delta| \le 10\%$: Score 0 (within acceptable operating tolerance).
  - **Financial Leading** ($\Delta > 10\%$): Score scales from 30 to 100 as gap widens to $50\%+$. Indicates potential premature drawdowns or milestone reporting delays.
  - **Physical Leading** ($\Delta < -15\%$): Score scales from 25 to 70. Indicates delayed contractor billing or pending disbursement reconciliations.

---

### Engine 5: Agency Historical Patterns
- **Purpose**: Evaluates historical portfolio track records of the executing entity across past projects.
- **Inputs**:
  - `projects.implementing_agency` (fallback to `executing_agency`, `department`, `contractor`)
  - Historical database portfolio of all projects assigned to that entity
- **Formulas & Statistics**:
  - $\text{Delay Rate} = \frac{\text{delayed projects}}{\text{scheduled projects}}$
  - $\text{Cost Anomaly Rate} = \frac{\text{cost outlier projects}}{\text{evaluated projects}}$
  - $\text{Mismatch Rate} = \frac{\text{progress gap projects}}{\text{progress evaluated projects}}$
  - $\text{Historical Risk Score} = 0.40 \cdot (\text{Delay Rate}) + 0.35 \cdot (\text{Mismatch Rate}) + 0.25 \cdot (\text{Cost Anomaly Rate})$
- **Small Sample Size Protection**:
  - If $\text{portfolio size} < 3$ projects, agency score is clamped to **0** with confidence **0.15**, ensuring new or rarely utilized agencies are never unfairly penalized.

---

### Engine 6: Explained Risk Engine
- **Purpose**: Synthesizes the outputs of Engines 1–5 and the central composite score into human-understandable, audit-ready explanations without inventing data.
- **Inputs**: Outputs of Engines 1–5, central composite score, assigned risk tier, effective weights.
- **Methodology**:
  - **Factor Ranking**: Sorts all 5 engines by points contributed to the overall score:
    $$\text{Contribution}_i = \text{Score}_i \times \text{Weight}_i$$
  - **Evidence Synthesis**: Cites concrete numbers from the engine evidence dictionaries (e.g., "527 days overdue", "+22.5% progress gap").
  - **Actionable Recommendations**: Generates tailored review items mapped directly to elevated risk drivers (e.g., site inspection, MB book reconciliation, BOQ engineering estimate).
  - **Strict Language Policy**: Strictly avoids inflammatory words like "fraud", "corruption", or "manipulation", adhering to objective administrative auditing standards.

---

## 3. Scoring Methodology, Weights & Thresholds

### Central Composite Formula
The overall project risk score is computed as:
$$\text{Overall Score} = \sum_{i=1}^{5} w_i \cdot s_i$$
where $s_i \in [0, 100]$ is the score from engine $i$, and $w_i$ is the normalized weight.

### Default Weights
| Engine | Default Weight | Key Rationale |
|---|:---:|---|
| **Cost Anomaly** | 20% | Detects financial budget deviations |
| **Duplicate Detection** | 20% | Screens for proposal overlaps |
| **Delay Detection** | 20% | Monitors project delivery pace |
| **Progress Mismatch** | 20% | Flags disbursement vs milestone gaps |
| **Agency Pattern** | 20% | Considers historical execution track record |

### Dynamic Renormalization
If any engine is unavailable (e.g. missing historical portfolio or corrupted text vectorizer), the system can dynamically renormalize weights across available engines:
$$w_j' = \frac{w_j}{\sum_{k \in \text{Available}} w_k}$$
This ensures the final score remains strictly bounded in $[0, 100]$ without artificially depressing risk ratings.

### Risk Tier Thresholds
```
 0                    30                   60                   80                 100
 ├────────────────────┼────────────────────┼────────────────────┼──────────────────┤
 │      LOW RISK      │    MEDIUM RISK     │     HIGH RISK      │  CRITICAL RISK   │
 │   Routine Track    │ Operational Review │ Field Verification │ Immediate Audit  │
 └────────────────────┴────────────────────┴────────────────────┴──────────────────┘
```
- **LOW (0–29.9)**: Normal operations; all metrics within acceptable tolerances.
- **MEDIUM (30.0–59.9)**: Moderate variance; routine operational review advised.
- **HIGH (60.0–79.9)**: Significant anomalies; prioritizes physical site or financial verification.
- **CRITICAL (80.0–100.0)**: Severe multi-dimensional irregularities; requires immediate senior administrative audit.

---

## 4. Database Schema

The Phase 7 system integrates directly with PostgreSQL, updating two dedicated tables:

### `risk_scores` Table
| Column | Type | Constraints | Description |
|---|---|---|---|
| `risk_score_id` | `INTEGER` | PRIMARY KEY, SERIAL | Auto-incrementing identifier |
| `project_id` | `VARCHAR(50)` | UNIQUE, NOT NULL, FK $\to$ `projects` | Target project reference |
| `overall_score` | `NUMERIC(5,2)` | NOT NULL, CHECK $(0 \le s \le 100)$ | Composite risk score |
| `risk_level` | `VARCHAR(20)` | NOT NULL | Risk tier (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) |
| `confidence` | `NUMERIC(3,2)` | DEFAULT 1.00 | Aggregate confidence rating |
| `created_at` | `TIMESTAMPTZ` | DEFAULT `NOW()` | Initial calculation timestamp |
| `updated_at` | `TIMESTAMPTZ` | DEFAULT `NOW()` | Recalculation timestamp |

### `risk_factors` Table
| Column | Type | Constraints | Description |
|---|---|---|---|
| `factor_id` | `INTEGER` | PRIMARY KEY, SERIAL | Auto-incrementing identifier |
| `project_id` | `VARCHAR(50)` | NOT NULL, FK $\to$ `projects` | Target project reference |
| `engine_name` | `VARCHAR(50)` | NOT NULL | Engine identifier (`cost_anomaly`, etc.) |
| `score` | `NUMERIC(5,2)` | NOT NULL | Individual engine risk score |
| `risk_level` | `VARCHAR(20)` | NOT NULL | Engine-specific risk tier |
| `reason` | `TEXT` | NOT NULL | Detailed explanatory narrative |
| `confidence` | `NUMERIC(3,2)` | NOT NULL | Engine confidence rating |
| `details` | `JSONB` | NOT NULL | Raw metrics, evidence, and audit metadata |
| `created_at` | `TIMESTAMPTZ` | DEFAULT `NOW()` | Timestamp |

---

## 5. API Endpoints

The risk pipeline is exposed via FastAPI endpoints:

| Method | Endpoint | Description | Query / Body Params |
|---|---|---|---|
| `GET` | `/projects/{id}/risk` | Detailed project risk breakdown and explanation | `recalculate=false` |
| `GET` | `/projects/{id}/risk/factors` | Individual risk factor evidence list | None |
| `POST` | `/projects/{id}/risk/recalculate` | Forces real-time recalculation of all 6 engines | `persist=true` |
| `GET` | `/high-risk` | Triage list of elevated-risk projects | `threshold=60`, `limit=50`, `state_id`, `district` |
| `GET` | `/analytics/risk-distribution` | Portfolio risk tier breakdown and summary statistics | `state_id`, `sector` |
| `GET` | `/analytics/engine/{engine_name}` | Engine-specific distribution and outlier summary | `engine_name` |
| `GET` | `/agencies/{agency_id}/risk-pattern` | Agency-level historical portfolio metrics | None |

---

## 6. Configuration Management

Configuration is centralized in `RiskEngineConfig` and `backend/app/config.py`:

```python
from app.schemas.risk_engine import RiskEngineConfig

config = RiskEngineConfig(
    weights={
        "cost_anomaly": 0.20,
        "duplicate_detection": 0.20,
        "delay_detection": 0.20,
        "progress_mismatch": 0.20,
        "agency_pattern": 0.20,
    },
    thresholds={
        "low": (0.0, 30.0),
        "medium": (30.0, 60.0),
        "high": (60.0, 80.0),
        "critical": (80.0, 100.0),
    },
    missing_engine_strategy="renormalize_weights",  # Options: zero_score, renormalize_weights
    min_agency_projects=3,
    min_peer_group_size=3,
    progress_mismatch_tolerance=10.0,
)
```

---

## 7. Handling Missing Data & Engine Failures

- **Missing Financials**: If a project has no expenditure recorded, `CostAnomalyEngine` outputs score 0 with low confidence (0.20) rather than raising an unhandled exception.
- **Missing Timeline Dates**: If dates are null, `DelayDetectionEngine` returns score 0 and flags `invalid_timeline: True`.
- **Short Descriptions**: If text has $< 3$ words, `DuplicateDetectionEngine` assigns score 0 and marks classification as `INSUFFICIENT_TEXT`.
- **Small Agency Sample**: If an agency has $< 3$ historical projects, `AgencyPatternEngine` returns score 0 with confidence 0.15.
- **Engine Failure Containment**: If any single engine encounters an unexpected runtime error, the central pipeline catches it, logs the trace, records the engine in `unavailable_engines`, and dynamically renormalizes remaining engines so the pipeline never crashes.

---

## 8. Live 10-Step Demonstration Flow

A dedicated demonstration script is provided:
```bash
python3 scripts/demo_risk_analysis.py --project MPLADS-2024-0011
```

### Demonstration Steps Walkthrough

```text
====================================================================================
       MPLADS PHASE 7 RISK & ANOMALY DETECTION SYSTEM — LIVE DEMONSTRATION
====================================================================================
  * System Role: Data-Driven Decision-Support & Irregularity Screening
  * Non-Fraud Disclaimer: Identifies statistical anomalies and operational friction;
                          does NOT make definitive determinations of wrongdoing.
====================================================================================

[STEP 1] Selecting Project for Analysis: 'MPLADS-2024-0011'
------------------------------------------------------------------------------------
  Project Title      : Inter-village All-Weather Bituminous Road
  Sector / Sub-Sector: Roads & Bridges / Roads & Bridges
  Location           : Bapatla District, State ID: 2
  Implementing Agency: District Rural Development Agency (DRDA)
  Current Status     : In Progress
  Sanctioned Amount  : ₹4,800,000.00 | Actual Expenditure: ₹2,100,000.00
  Physical Milestone : 65.0% (Structure)

[STEP 2] Running Multi-Engine Risk Analysis Pipeline...
------------------------------------------------------------------------------------
  Evaluating project concurrently through Engines 1–5, Aggregation, and Engine 6...
  Analysis successfully completed and persisted to PostgreSQL.

[STEP 3] Engine 1 — Cost Anomaly Detection
------------------------------------------------------------------------------------
  Score              : 44.0 / 100 (MEDIUM)
  Evaluated Cost     : ₹2,100,000.00 (Peer Median: ₹1,290,000.00)
  Cost Deviation     : +62.8% (Robust Z-Score: 6.07)
  Legitimacy Check   : LEGITIMATE_HIGH_BUDGET (Within approved ₹4.8M sanction)

[STEP 4] Engine 2 — Duplicate Project Detection
------------------------------------------------------------------------------------
  Score              : 0.0 / 100 (LOW)
  Raw Similarity     : 47.6% (Highest match with MPLADS-2024-0017 in different state)
  Classification     : NONE (No duplicate identified)

[STEP 5] Engine 3 — Project Delay Detection
------------------------------------------------------------------------------------
  Score              : 100.0 / 100 (CRITICAL)
  Execution Status   : ONGOING_OVERDUE
  Overdue Duration   : 527 days beyond planned completion date (2025-03-31)
  Schedule Slippage  : +217.8% overrun against planned duration

[STEP 6] Engine 4 — Financial & Physical Progress Mismatch
------------------------------------------------------------------------------------
  Score              : 63.0 / 100 (HIGH)
  Financial Progress : 87.5% | Physical Progress: 65.0%
  Progress Gap       : +22.5 percentage points (financial_leading)

[STEP 7] Engine 5 — Agency Pattern Detection
------------------------------------------------------------------------------------
  Score              : 54.0 / 100 (MEDIUM)
  Agency Analyzed    : District Rural Development Agency (DRDA)
  Portfolio Size     : 20 historical projects (60.0% delay rate, 40.0% mismatch rate)

[STEP 8] Central Risk Aggregation (Overall Score & Tier)
------------------------------------------------------------------------------------
  Overall Score      : 52.20 / 100
  Assigned Risk Tier : MEDIUM
  Component Contribution Formula (Equal 20% Default Weights):
    * Cost Anomaly Detection      : Score  44.0 × 0.20 =  8.8 pts
    * Duplicate Project Detection : Score   0.0 × 0.20 =  0.0 pts
    * Project Delay Detection     : Score 100.0 × 0.20 = 20.0 pts
    * Progress Mismatch Detection : Score  63.0 × 0.20 = 12.6 pts
    * Agency Pattern Analysis     : Score  54.0 × 0.20 = 10.8 pts
    -----------------------------------------------------------------
    * Total Composite Score                                = 52.2 pts

[STEP 9] Engine 6 — Explained Risk Assessment
------------------------------------------------------------------------------------
  Executive Summary:
    "Project exhibits medium overall risk (score 52.2/100, tier: MEDIUM) with notable
     contributions from Delay Detection (20.0 pts) and Progress Mismatch (12.6 pts)."

  Ranked Contributing Factors:
    1. delay_detection        | Score: 100.0 | Contribution: 20.0 pts
    2. progress_mismatch      | Score:  63.0 | Contribution: 12.6 pts
    3. agency_pattern         | Score:  54.0 | Contribution: 10.8 pts
    4. cost_anomaly           | Score:  44.0 | Contribution:  8.8 pts
    5. duplicate_detection    | Score:   0.0 | Contribution:  0.0 pts

  Recommended Administrative Review Areas:
    [1] Review contractor milestone schedules and site progress logs (527 days overdue).
    [2] Cross-reference physical measurement book (MB) recordings with disbursements.
    [3] Examine active project workload and staffing capacity of DRDA.
    [4] Conduct an independent BOQ review against the standard schedule of rates.

[STEP 10] Database Persistence Verification (PostgreSQL)
------------------------------------------------------------------------------------
  Table: risk_scores (project_id='MPLADS-2024-0011', overall_score=52.20, level='Moderate')
  Table: risk_factors (6 records persisted with scores, confidence, and JSON details)
====================================================================================
```

---

## 9. Deliverables & Audit Summary

### Files Created
- [`scripts/demo_risk_analysis.py`](file:///Users/vinxy/SIH%202026/scripts/demo_risk_analysis.py): 10-step demonstration CLI runner.
- [`docs/PHASE_7_RISK_SYSTEM_DOCUMENTATION.md`](file:///Users/vinxy/SIH%202026/docs/PHASE_7_RISK_SYSTEM_DOCUMENTATION.md): Complete system technical and evaluation documentation.
- [`backend/tests/test_complete_phase7_audit.py`](file:///Users/vinxy/SIH%202026/backend/tests/test_complete_phase7_audit.py): Comprehensive 36-test audit suite covering all 15 dimensions and 4 representative tiers.
- [`backend/app/services/risk/batch_risk_service.py`](file:///Users/vinxy/SIH%202026/backend/app/services/risk/batch_risk_service.py): Batch processing service with caching and fault isolation.
- [`data/scripts/calculate_batch_risk.py`](file:///Users/vinxy/SIH%202026/data/scripts/calculate_batch_risk.py): Batch risk CLI runner.

### Files Modified
- [`backend/app/services/risk_engine.py`](file:///Users/vinxy/SIH%202026/backend/app/services/risk_engine.py): Fixed dynamic threshold evaluation and foreign key validation.
- [`backend/app/services/risk/cost_anomaly_engine.py`](file:///Users/vinxy/SIH%202026/backend/app/services/risk/cost_anomaly_engine.py): Fixed cost overrun escalation logic.
- [`backend/app/services/risk/agency_pattern_engine.py`](file:///Users/vinxy/SIH%202026/backend/app/services/risk/agency_pattern_engine.py): Fixed dual-cache population.
- [`backend/app/services/risk/duplicate_detection_engine.py`](file:///Users/vinxy/SIH%202026/backend/app/services/risk/duplicate_detection_engine.py): Silenced stdout logging during weight loading.
- [`backend/app/services/__init__.py`](file:///Users/vinxy/SIH%202026/backend/app/services/__init__.py): Added robust import fallback for `PYTHONPATH`.

### Database Changes
- Reused existing `risk_scores` and `risk_factors` tables without destructive migrations.
- Persisted batch risk scores and detailed factors for all projects in the database.

### Dependencies
- Python 3.14 / 3.11+
- `fastapi`, `uvicorn`, `pydantic`
- `sqlalchemy`, `psycopg2-binary`
- `sentence-transformers`, `scikit-learn`, `numpy`
- `pytest`, `pytest-asyncio`

### Test Results
- **333 / 333 tests passing (100%)** in 16.54s.

### Known Limitations
1. **Historical Depth**: Emerging agencies with $< 3$ projects receive neutral risk scores (0) until sufficient portfolio data accumulates.
2. **Text Richness**: Brief or formulaic project titles (e.g., "Install Handpump") limit semantic disambiguation without geo-coordinates.
3. **External Real-World Delay Causes**: The delay engine flags calendar slippage objectively but cannot automatically deduce external factors (e.g., monsoon floods, court litigation) without manual log notes.

### Commands to Run the System
1. **Run 10-Step Live Demo**:
   ```bash
   python3 scripts/demo_risk_analysis.py --project MPLADS-2024-0011
   ```
2. **Run Batch Risk Calculation**:
   ```bash
   python3 data/scripts/calculate_batch_risk.py --all
   ```
3. **Start FastAPI Backend**:
   ```bash
   python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
   ```
4. **Execute Complete Test Suite**:
   ```bash
   pytest --ignore=backend/tests/test_live_server.py backend/tests/
   ```
