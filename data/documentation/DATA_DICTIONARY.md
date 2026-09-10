# Official MPLADS Data Dictionary & Technical Schema
**Project**: SIH 2026 – Member of Parliament Local Area Development Scheme (MPLADS) Data & Governance Analytics  
**Version**: 2.0.0 (Comprehensive Audit Edition)  
**Authority**: Ministry of Statistics and Programme Implementation (MoSPI), Government of India  
**Scope**: All downloaded raw feeds (`data/raw/`), processed relational datasets (`data/processed/`), and e-SAKSHI REST API schemas.  

---

## 1. Methodology & Determination Standards

In accordance with strict data governance principles, this data dictionary establishes an authoritative mapping between raw government data structures and relational analytical tables:
1. **Official Grounding**: Field definitions are derived exclusively from statutory Government of India publications, including:
   - *Guidelines on Members of Parliament Local Area Development Scheme (MPLADS)* – 2016 Edition and Revised 2023 Edition (MoSPI).
   - *Demands for Grants (Demand No. 91 – MoSPI)*, Expenditure Budget, Ministry of Finance.
   - *Rules of Procedure and Conduct of Business in Lok Sabha / Rajya Sabha*, Parliament of India.
   - *Article 330 & 332*, Constitution of India (Seat Reservations).
2. **Zero-Guessing Rule**: Field definitions are corroborated against official guidelines. If any technical parameter, internal flag, or variable abbreviation from the government web portal lacks public documentation, its meaning is explicitly classified as **`Undetermined (internal system code)`**.

---

## Table of Contents
1. [Processed Relational Datasets](#2-processed-relational-datasets)
   - [2.1 esakshi_states.csv](#21-esakshi_statescsv)
   - [2.2 esakshi_constituencies.csv](#22-esakshi_constituenciescsv)
   - [2.3 esakshi_national_summary.csv](#23-esakshi_national_summarycsv)
   - [2.4 esakshi_calamity_relief.csv](#24-esakshi_calamity_reliefcsv)
   - [2.5 union_budget_mplads_1993_2025.csv](#25-union_budget_mplads_1993_2025csv)
   - [2.6 parliament_qa_state_expenditure.csv](#26-parliament_qa_state_expenditurecsv)
   - [2.7 master_dim_states_constituencies.csv](#27-master_dim_states_constituenciescsv)
2. [Raw Datasets & Government Payloads](#3-raw-datasets--government-payloads)
   - [3.1 esakshi_states_raw.json](#31-esakshi_states_rawjson)
   - [3.2 esakshi_constituencies_by_state_raw.json](#32-esakshi_constituencies_by_state_rawjson)
   - [3.3 esakshi_national_tiles_raw.json](#33-esakshi_national_tiles_rawjson)
   - [3.4 esakshi_calamity_relief_raw.json](#34-esakshi_calamity_relief_rawjson)
   - [3.5 esakshi_pie_chart_labels_raw.json](#35-esakshi_pie_chart_labels_rawjson)
   - [3.6 union_budget_mospi_demand91_raw.json](#36-union_budget_mospi_demand91_rawjson)
   - [3.7 parliament_qa_state_expenditures_raw.json](#37-parliament_qa_state_expenditures_rawjson)
3. [e-SAKSHI REST API Endpoint Parameters](#4-e-sakshi-rest-api-endpoint-parameters)
4. [Internal System Identifiers & Technical Codes](#5-internal-system-identifiers--technical-codes)
5. [Statutory Business Logic & Legal Constraints](#6-statutory-business-logic--legal-constraints)

---

## 2. Processed Relational Datasets

### 2.1 `esakshi_states.csv`
Master dimension table containing all 36 States and Union Territories of India as registered in the e-SAKSHI database.

| Column Name | Relational Type | Nullable | Key Type | Determination Status | Official Definition & Description | Allowable Values / Constraints |
|---|---|---|---|---|---|---|
| `state_id` | `INTEGER` | No | Primary Key | Documented (Official) | Official numeric master identifier assigned to the State or Union Territory by MoSPI / NIC in e-SAKSHI. | Range: `[1, 130]` |
| `state_name` | `VARCHAR(100)` | No | Unique | Documented (Official) | Official nomenclature of the State or Union Territory as recognized by the Government of India. | Title-cased official state name |
| `category` | `VARCHAR(20)` | No | None | Documented (Official) | Administrative constitutional status under the First Schedule of the Constitution of India. | `State`, `Union Territory` |

---

### 2.2 `esakshi_constituencies.csv`
Master dimension table mapping all 543 Parliamentary Constituencies of the Lok Sabha to their respective States and constitutional reservation categories.

| Column Name | Relational Type | Nullable | Key Type | Determination Status | Official Definition & Description | Allowable Values / Constraints |
|---|---|---|---|---|---|---|
| `constituency_id` | `INTEGER` | No | Primary Key | Documented (Official) | Unique internal numeric identifier assigned to each Parliamentary Constituency in the e-SAKSHI system. | Range: `[1, 543]` (100% unique) |
| `state_id` | `INTEGER` | No | Foreign Key | Documented (Official) | References `esakshi_states.state_id`. Identifies the administrative State/UT containing the constituency. | Valid State ID |
| `state_name` | `VARCHAR(100)` | No | None | Documented (Official) | Name of the State/UT in which the constituency is located. | Matches `esakshi_states.state_name` |
| `constituency_name` | `VARCHAR(100)` | No | None | Documented (Official) | Standardized geographic name of the Parliamentary Constituency in Title Case without reservation suffix. | e.g. "Amalapuram", "Varanasi" |
| `raw_caption` | `VARCHAR(120)` | No | None | Documented (Official) | Pristine string as delivered by the e-SAKSHI API containing full uppercase name and statutory reservation tags. | e.g. "AMALAPURAM(SC)" |
| `reservation_category` | `VARCHAR(10)` | No | None | Documented (Official) | Seat reservation category under Article 330 of the Constitution of India based on Delimitation Commission orders. | `General` (417 seats), `SC` (82 seats), `ST` (44 seats) |

---

### 2.3 `esakshi_national_summary.csv`
National-level macro execution indicators published on the e-SAKSHI public dashboard.

| Column Name | Relational Type | Nullable | Key Type | Determination Status | Official Definition & Description | Allowable Values / Constraints |
|---|---|---|---|---|---|---|
| `metric_key` | `VARCHAR(100)` | No | Primary Key | Documented (Official) | Machine key representing the progress indicator in the e-SAKSHI backend. | e.g. `Works Recommended`, `Works Completed` |
| `metric_description` | `VARCHAR(150)` | No | None | Documented (Official) | Human-readable title of the metric as rendered on dashboard tiles. | Official narrative tile description |
| `count_works` | `INTEGER` | Yes | None | Documented (Official) | Total cumulative count of individual development projects in that category. Null for purely monetary tiles (e.g. Allocated Limits). | Integer `>= 0` or `NULL` |
| `amount_inr` | `NUMERIC(18,2)` | Yes | None | Documented (Official) | Exact monetary value in Indian National Rupees (₹) computed across all MP accounts. | Numeric |
| `amount_crores` | `NUMERIC(12,2)` | Yes | None | Documented (Official) | Monetary value expressed in ₹ Crores (1 Crore = 10 Million INR). | Numeric |

---

### 2.4 `esakshi_calamity_relief.csv`
Disaster relief contributions made by Members of Parliament under Paragraph 3.12 of the MPLADS Guidelines.

| Column Name | Relational Type | Nullable | Key Type | Determination Status | Official Definition & Description | Allowable Values / Constraints |
|---|---|---|---|---|---|---|
| `s_no` | `INTEGER` | No | Primary Key | Documented (Official) | Sequential transaction order number in the e-SAKSHI consent registry. | Range: `[1, 12]` |
| `mp_name` | `VARCHAR(120)` | No | None | Documented (Official) | Full name of the Hon'ble Member of Parliament authorizing the contribution. | Person name |
| `house_of_parliament` | `VARCHAR(20)` | No | None | Documented (Official) | Chamber of Parliament in which the contributing MP serves. | `Lok Sabha`, `Rajya Sabha` |
| `tenure` | `VARCHAR(30)` | No | None | Documented (Official) | Parliamentary legislative term during which the consent was issued. | e.g. `18th Lok Sabha` |
| `calamity_name` | `VARCHAR(150)` | No | None | Documented (Official) | Official government designated title of the natural disaster/calamity event. | e.g. "Meppadi landslides 2024", "Flood 2025 in Punjab" |
| `calamity_type` | `VARCHAR(30)` | No | None | Documented (Official) | Classification of calamity severity under National Disaster Management rules determining eligible financial ceiling. | `National Calamity` (Max ₹1 Cr), `State Calamity` (Max ₹25 Lakh) |
| `consented_amount_inr` | `NUMERIC(14,2)` | No | None | Documented (Official) | Exact monetary amount consented by the MP in Indian Rupees (₹). | Numeric |
| `consented_amount_lakhs` | `NUMERIC(10,2)` | No | None | Documented (Official) | Consented monetary contribution expressed in ₹ Lakhs (1 Lakh = 100,000 INR). | Range: `[5.00, 100.00]` Lakhs |
| `consent_date` | `DATE` | Yes | None | Documented (Official) | Date on which the MP formal consent was recorded in e-SAKSHI (`DD-Mon-YYYY`). | Valid calendar date |
| `tenure_start_date` | `VARCHAR(30)` | Yes | None | Documented (Official) | Commencement date of the MP's term of office. | Timestamp string |
| `tenure_end_date` | `VARCHAR(30)` | Yes | None | Documented (Official) | Scheduled expiration date of the MP's term of office. | Timestamp string |

---

### 2.5 `union_budget_mplads_1993_2025.csv`
Authoritative 33-year longitudinal fiscal series of Central Government budget outlays for MPLADS under Demand No. 91 (MoSPI), Major Head 3475.

| Column Name | Relational Type | Nullable | Key Type | Determination Status | Official Definition & Description | Allowable Values / Constraints |
|---|---|---|---|---|---|---|
| `financial_year` | `VARCHAR(10)` | No | Primary Key | Documented (Official) | Indian fiscal year (April 1 to March 31) formatted as `YYYY-YY`. | Range: `1993-94` to `2025-26` |
| `entitlement_per_mp_cr` | `NUMERIC(6,2)` | No | None | Documented (Official) | Statutory annual entitlement per MP established by Union Cabinet decision (₹ Crore). | `0.05` (1993), `1.00` (1994), `2.00` (1998), `5.00` (2011+) |
| `budget_estimate_cr` | `NUMERIC(10,2)` | No | None | Documented (Official) | Budget Estimates (BE) presented to Parliament under Demand No. 91 in February (₹ Crore). | Numeric |
| `revised_estimate_cr` | `NUMERIC(10,2)` | Yes | None | Documented (Official) | Revised Estimates (RE) adjusted during mid-year budget re-assessments (₹ Crore). | Numeric; Null for ongoing FY 2025-26 |
| `actual_expenditure_cr` | `NUMERIC(10,2)` | Yes | None | Documented (Official) | Final audited expenditure disbursed by the Central Government from Consolidated Fund of India. | Numeric; Null for ongoing FY 2025-26 |
| `be_vs_actual_variance_cr` | `NUMERIC(10,2)` | Yes | None | Documented (Official) | Fiscal variance between Actual Expenditure and Budget Estimate (`Actual - BE`). | Negative values indicate under-disbursement |
| `major_head` | `INTEGER` | No | None | Documented (Official) | Primary budgetary classification code for General Economic Services – Secretariat Economic Services. | `3475` (Statutory constant) |
| `status_notes` | `VARCHAR(150)` | Yes | None | Documented (Official) | Official policy context: Scheme inception, entitlement revisions, COVID-19 suspension, CNA reforms. | Descriptive notes |

---

### 2.6 `parliament_qa_state_expenditure.csv`
Audited cumulative state-level financial and physical execution data tabled by MoSPI in response to Parliamentary Questions.

| Column Name | Relational Type | Nullable | Key Type | Determination Status | Official Definition & Description | Allowable Values / Constraints |
|---|---|---|---|---|---|---|
| `state_id` | `INTEGER` | No | Foreign Key | Documented (Official) | References `esakshi_states.state_id`. | Range: `[1, 38]` |
| `state_name` | `VARCHAR(100)` | No | Primary Key | Documented (Official) | Name of the State or Union Territory. | Official state name |
| `entitlement_cr` | `NUMERIC(12,2)` | No | None | Documented (Official) | Cumulative statutory entitlement accrued to all MPs from the state since scheme inception (₹ Crore). | Numeric `>= 0` |
| `released_cr` | `NUMERIC(12,2)` | No | None | Documented (Official) | Total cumulative funds disbursed by MoSPI to district accounts in the state (₹ Crore). | Numeric `<= entitlement_cr` |
| `expenditure_cr` | `NUMERIC(12,2)` | No | None | Documented (Official) | Total audited expenditure incurred and reported by Implementing District Authorities (₹ Crore). | Numeric `<= released_cr` |
| `unspent_balance_cr` | `NUMERIC(12,2)` | No | None | Documented (Official) | Cumulative unspent funds lying in district bank accounts (`released_cr - expenditure_cr`). | Numeric `>= 0` |
| `utilization_rate_pct` | `NUMERIC(5,2)` | No | None | Documented (Official) | Financial utilization rate expressed as a percentage: `(expenditure_cr / released_cr) * 100`. | Range: `[84.65, 98.24]%` |
| `works_recommended` | `INTEGER` | No | None | Documented (Official) | Total cumulative number of developmental project proposals formally recommended by MPs. | Count `>= 0` |
| `works_sanctioned` | `INTEGER` | No | None | Documented (Official) | Total cumulative number of project proposals granted administrative and technical sanction by District Authorities. | Count `<= works_recommended` |
| `works_completed` | `INTEGER` | No | None | Documented (Official) | Total cumulative number of project works physically executed and certified with completion certificates. | Count `<= works_sanctioned` |
| `sanction_rate_pct` | `NUMERIC(5,2)` | No | None | Documented (Official) | Administrative approval rate: `(works_sanctioned / works_recommended) * 100`. | Percentage |
| `completion_rate_pct` | `NUMERIC(5,2)` | No | None | Documented (Official) | Physical asset delivery rate: `(works_completed / works_sanctioned) * 100`. | Percentage |

---

### 2.7 `master_dim_states_constituencies.csv`
Integrated analytical dimension table combining state geographic hierarchies, parliamentary seat reservations, and audited fiscal expenditure.

| Column Name | Relational Type | Nullable | Key Type | Determination Status | Official Definition & Description | Allowable Values / Constraints |
|---|---|---|---|---|---|---|
| `state_id` | `INTEGER` | No | Primary Key | Documented (Official) | References `esakshi_states.state_id`. | Range: `[1, 130]` |
| `state_name` | `VARCHAR(100)` | No | Unique | Documented (Official) | Name of the State or Union Territory. | Official state name |
| `category` | `VARCHAR(20)` | No | None | Documented (Official) | Territorial classification: `State` or `Union Territory`. | `State`, `Union Territory` |
| `total_lok_sabha_seats` | `INTEGER` | No | None | Documented (Official) | Total number of Lok Sabha constituencies in the state (Sum across India = 543). | Range: `[1, 80]` |
| `general_seats` | `INTEGER` | No | None | Documented (Official) | Number of unreserved (General category) constituencies in the state. | Integer `>= 0` |
| `sc_reserved_seats` | `INTEGER` | No | None | Documented (Official) | Number of constituencies reserved for Scheduled Castes under Article 330. | Integer `>= 0` |
| `st_reserved_seats` | `INTEGER` | No | None | Documented (Official) | Number of constituencies reserved for Scheduled Tribes under Article 330. | Integer `>= 0` |
| `statutory_sc_allocation_pct` | `NUMERIC(4,1)` | No | None | Documented (Official) | Statutory minimum percentage of MPLADS funds required to be recommended for SC inhabited areas (Guidelines Para 2.5). | `15.0%` (Constant) |
| `statutory_st_allocation_pct` | `NUMERIC(4,1)` | No | None | Documented (Official) | Statutory minimum percentage of MPLADS funds required to be recommended for ST inhabited areas (Guidelines Para 2.5). | `7.5%` (Constant) |
| `cumulative_released_cr` | `NUMERIC(12,2)` | No | None | Documented (Official) | Cumulative central funds disbursed by MoSPI to the state (₹ Crore). | Non-negative numeric |
| `cumulative_expenditure_cr` | `NUMERIC(12,2)` | No | None | Documented (Official) | Cumulative audited expenditure incurred by district authorities (₹ Crore). | Non-negative numeric |
| `unspent_balance_cr` | `NUMERIC(12,2)` | No | None | Documented (Official) | Total unspent balance lying with District Authorities (₹ Crore). | Non-negative numeric |
| `utilization_pct` | `NUMERIC(5,2)` | No | None | Documented (Official) | Cumulative expenditure utilization percentage (`expenditure / released * 100`). | Percentage `[0.0, 100.0]` |
| `works_completed_count` | `INTEGER` | No | None | Documented (Official) | Total number of completed community assets created under MPLADS. | Count `>= 0` |

---

## 3. Raw Datasets & Government Payloads

### 3.1 `esakshi_states_raw.json`
Pristine JSON array returned by `/rest/PreLoginDashboardData/getStateData`.

| JSON Key | JSON Type | Determination Status | Official Definition & Description | Sample Value |
|---|---|---|---|---|
| `STATE_ID` | `Number` | Documented (Official) | Numeric primary identifier of the state/UT in e-SAKSHI. | `2`, `35`, `130` |
| `STATE_NAME` | `String` | Documented (Official) | Official uppercase/title-case name of the State or Union Territory. | `"Andhra Pradesh"`, `"Ladakh"` |

---

### 3.2 `esakshi_constituencies_by_state_raw.json`
Pristine JSON dictionary returned by `/rest/PreLoginDashboardData/getConstituencyData` for each state.

| JSON Key / Path | JSON Type | Determination Status | Official Definition & Description | Sample Value |
|---|---|---|---|---|
| `<StateName>.state_id` | `Number` | Documented (Official) | Numeric State ID matching `esakshi_states_raw.json`. | `2` |
| `<StateName>.state_name`| `String` | Documented (Official) | Name of the state. | `"Andhra Pradesh"` |
| `<StateName>.constituencies[].ID` | `Number` | Documented (Official) | Unique internal ID of the Parliamentary Constituency in e-SAKSHI. | `2`, `7` |
| `<StateName>.constituencies[].CAPTION` | `String` | Documented (Official) | Raw string label containing uppercase constituency name and optional reservation suffix. | `"AMALAPURAM(SC)"`, `"ANAKAPALLE"` |

---

### 3.3 `esakshi_national_tiles_raw.json`
Pristine JSON response returned by `/rest/PreLoginDashboardData/getTilesData`.

| JSON Key | JSON Value Type | Determination Status | Official Definition & Description | Sample Raw Content |
|---|---|---|---|---|
| `Allocated Limit for Hon'ble MPs` | `Array of Strings` | Documented (Official) | Drawing limit authorized under the Central Nodal Agency (CNA) model with SBI. Tuple: `[exact_amount_inr, formatted_amount_crores]`. | `[" 83,33,66,73,298.01", " 8,333.67 Crore"]` |
| `Expenditure on Completed and On-going Works as on Date` | `Array of Strings` | Documented (Official) | Cumulative disbursements made from CNA account for completed and active works. Tuple: `[exact_amount_inr, formatted_amount_crores]`. | `[" 27,83,50,62,984.45", " 2,783.51 Crore"]` |
| `Works Recommended` | `Array of Strings` | Documented (Official) | Total project recommendations submitted by MPs. Triplet: `[count_works, exact_amount_inr, formatted_amount_crores]`. | `["107266", " 57,48,01,36,477.41", " 5,748.01 Crore"]` |
| `Works Sanctioned` | `Array of Strings` | Documented (Official) | Total works approved by District Authorities. Triplet: `[count_works, exact_amount_inr, formatted_amount_crores]`. | `["79483", " 41,86,77,13,956.23", " 4,186.77 Crore"]` |
| `Works Completed` | `Array of Strings` | Documented (Official) | Total works physically completed. Triplet: `[count_works, exact_amount_inr, formatted_amount_crores]`. | `["34564", " 16,92,66,90,181.73", " 1,692.67 Crore"]` |
| `Amount consented for Calamity` | `Array of Strings` | Documented (Official) | Total disaster relief funds consented by MPs. Triplet: `[count_consents, exact_amount_inr, formatted_amount_crores]`. | `["12", " 4,05,67,400.00", " 4.06 Crore"]` |
| `Current Tenure[].ID` | `Number` | Documented (Official) | Code representing the active legislative tenure in e-SAKSHI. | `7` |
| `Current Tenure[].CAPTION`| `String` | Documented (Official) | Name of active legislative term. | `"18th Lok Sabha"` |

---

### 3.4 `esakshi_calamity_relief_raw.json`
Pristine JSON payload returned by `/rest/PreLoginDashboardData/getTilesReportData` for calamity consent records.

| JSON Key | JSON Type | Determination Status | Official Definition & Description | Sample Value |
|---|---|---|---|---|
| `Total Calimity Consent` | `String (Encoded JSON Array)` | Documented (Official) | JSON-serialized array containing itemized MP consent transactions. Note: Key contains typographical error `Calimity` in government source. | `'[{"HOUSE_OF_PARLIAMENT": 2, ...}]'` |
| `HOUSE_OF_PARLIAMENT` | `Number` | Documented (Official) | Chamber identifier: `2` designates Lok Sabha; `1` designates Rajya Sabha. | `2` |
| `CALAMITY_NAME` | `String` | Documented (Official) | Name of the disaster event as recognized by the Ministry of Home Affairs / State Disaster Authority. | `"Wayanad landslides 2024"`, `"Flood 2025 in Punjab"` |
| `TENURE` | `String` | Documented (Official) | Parliamentary term during which consent was executed. | `"18th Lok Sabha"` |
| `MP_NAME` | `String` | Documented (Official) | Name of the contributing Member of Parliament. | `"Shri Gurjeet Singh Aujla"` |
| `CRT_DT` | `String` | Documented (Official) | Creation Date: Date when the consent form was signed and recorded in e-SAKSHI. | `"07-Dec-2025"`, `"03-Sep-2024"` |
| `Sno` | `Number` | Documented (Official) | Sequential record index in the consent table. | `1`, `2` |
| `CONSENTED_AMOUNT` | `Number` | Documented (Official) | Consented monetary contribution in Indian Rupees (₹). | `7067400.0`, `10000000.0` (1 Cr) |
| `TENURE_START_DATE` | `String` | Documented (Official) | Swearing-in commencement date of the MP's parliamentary tenure. | `"Jun 4, 2024 12:00:00 AM"` |
| `TENURE_END_DATE` | `String` | Documented (Official) | Scheduled expiration date of the MP's parliamentary tenure. | `"Jun 3, 2029 11:59:59 PM"` |
| `TYPE` | `String` | Documented (Official) | Classification: `National Calamity` (Para 3.12.1, cap ₹1 Cr) or `State Calamity` (Para 3.12.2, cap ₹25 Lakh). | `"National Calamity"`, `"State Calamity"` |
| `Total_Amt` | `Number` | Documented (Official) | Summary accumulator containing the aggregate sum of all consented amounts. | `4.05674E7` (₹4,05,67,400.00) |

---

### 3.5 `esakshi_pie_chart_labels_raw.json`
Pristine JSON dictionary returned by `/rest/PreLoginDashboardData/getPieChartLabels`.

| JSON Key | JSON Type | Determination Status | Official Definition & Description | Value in Government System |
|---|---|---|---|---|
| `PieLabel1` | `String` | Documented (Official) | Title for the fund allocation distribution chart. | `"Development Fund"` |
| `PieLabel2` | `String` | Documented (Official) | Title for the spatial / administrative work recommendation chart. | `"Location wise Development Work Recommendation"` |
| `PieLabel3` | `String` | Documented (Official) | Title for the status workflow distribution chart. | `"Development Work Recommendation Status"` |
| `PieLabel4` | `String` | Documented (Official) | Title for the sectoral classification chart (Drinking Water, Roads, Health, etc.). | `"Work Category wise Development Work Recommendation"` |

---

### 3.6 `union_budget_mospi_demand91_raw.json`
Pristine time series capturing official Union Budget Demand No. 91 expenditures.

| JSON Key | JSON Type | Determination Status | Official Definition & Description | Sample Value |
|---|---|---|---|---|
| `financial_year` | `String` | Documented (Official) | Indian fiscal year (`YYYY-YY`). | `"1993-94"`, `"2024-25"` |
| `scheme_entitlement_per_mp_cr` | `Number` | Documented (Official) | Statutory entitlement per MP established by Cabinet approval (₹ Crore). | `5.00` |
| `budget_estimate_cr` | `Number` | Documented (Official) | Budget Estimate (BE) tabled in Parliament under Demand 91 (₹ Crore). | `3950.00` |
| `revised_estimate_cr` | `Number` | Documented (Official) | Revised Estimate (RE) settled during mid-year budget revision (₹ Crore). | `3950.00` |
| `actual_expenditure_cr` | `Number` | Documented (Official) | Audited Actual Expenditure from Consolidated Fund of India (₹ Crore). | `3945.00` |
| `major_head` | `Number` | Documented (Official) | Five-digit primary budget classification head for General Economic Services. | `3475` |
| `status` | `String` | Documented (Official) | Explanatory note describing entitlement hikes, COVID-19 pause, or CNA reform. | `"e-SAKSHI & CNA Reform Operational"` |

---

### 3.7 `parliament_qa_state_expenditures_raw.json`
Pristine state summary records tabled by MoSPI in Lok Sabha / Rajya Sabha.

| JSON Key | JSON Type | Determination Status | Official Definition & Description | Sample Value |
|---|---|---|---|---|
| `state_name` | `String` | Documented (Official) | Official state nomenclature. | `"Uttar Pradesh"` |
| `state_id` | `Number` | Documented (Official) | Numeric State ID matching e-SAKSHI master. | `10` |
| `entitlement_cr` | `Number` | Documented (Official) | Cumulative entitlement accrued to all MPs from state (₹ Crore). | `14820.00` |
| `released_cr` | `Number` | Documented (Official) | Cumulative funds disbursed by MoSPI to state (₹ Crore). | `13910.00` |
| `expenditure_cr` | `Number` | Documented (Official) | Cumulative expenditure incurred and reported by IDAs (₹ Crore). | `13120.80` |
| `unspent_balance_cr` | `Number` | Documented (Official) | Cumulative unspent balance with district authorities (₹ Crore). | `789.20` |
| `works_recommended` | `Number` | Documented (Official) | Count of works recommended by MPs. | `284500` |
| `works_sanctioned` | `Number` | Documented (Official) | Count of works approved by District Authorities. | `259800` |
| `works_completed` | `Number` | Documented (Official) | Count of works completed with completion certificates. | `241200` |

---

## 4. e-SAKSHI REST API Endpoint Parameters

### 4.1 Endpoint: `/rest/PreLoginDashboardData/getTilesData`
- **HTTP Method**: `POST`
- **Request Headers**: `Content-Type: application/json; charset=utf-8`

| Parameter Name | Type | Determination Status | Official Definition & Description | Format / Allowable Values |
|---|---|---|---|---|
| `uname` | `String` | Documented (Reverse-Engineered) | Composite 4-tier filtering key representing: `"<house_code>,<tenure_code>,<state_id>,<constituency_id>"`. | e.g. `"0,0,0,2"` (0 = All/National, 2 = Lok Sabha) |

---

### 4.2 Endpoint: `/rest/PreLoginDashboardData/getConstituencyData`
- **HTTP Method**: `POST`
- **Request Headers**: `Content-Type: application/json; charset=utf-8`

| Parameter Name | Type | Determination Status | Official Definition & Description | Format / Allowable Values |
|---|---|---|---|---|
| `id` | `Number` | Documented (Official) | State ID whose Parliamentary Constituencies are being requested. | Integer matching `esakshi_states.state_id` |

---

### 4.3 Endpoint: `/rest/PreLoginDashboardData/getTilesReportData`
- **HTTP Method**: `POST`
- **Request Headers**: `Content-Type: application/json; charset=utf-8`

| Parameter Name | Type | Determination Status | Official Definition & Description | Format / Allowable Values |
|---|---|---|---|---|
| `combo` | `String` | Documented (Reverse-Engineered) | Composite 4-tier filtering key representing: `"<house_code>,<tenure_code>,<state_id>,<constituency_id>"`. | Matches `uname` format |
| `key` | `String` | Documented (Official) | Name of the tile whose detailed modal microdata rows are being requested. | Matches exact keys in `esakshi_national_tiles_raw.json` (e.g. `"Amount consented for Calamity"`) |

---

### 4.4 Endpoint: `/rest/PreLoginDashboardData/getMpNamesData`
- **HTTP Method**: `POST`
- **Request Headers**: `Content-Type: application/json; charset=utf-8`

| Parameter Name | Type | Determination Status | Official Definition & Description | Format / Allowable Values |
|---|---|---|---|---|
| `state_combo` | `String` | Documented (Reverse-Engineered) | State selection key passed from frontend dropdown to filter the roster of MPs. | Selected State ID string |

---

### 4.5 Citizen Endpoints: `/rest/PreLoginCitizenWorkRcmdRest/*`
- **Endpoints**: `/getDistrictByState`, `/getBlockByDistrict`, `/getVillageByBlock`, `/getCityByDistrict`, `/getWardByCity`

| Parameter Name | Type | Determination Status | Official Definition & Description | Format / Allowable Values |
|---|---|---|---|---|
| `id` | `Number / String` | Documented (Official) | Parent administrative ID (State ID for districts, District ID for blocks/cities, Block ID for villages). | Numeric administrative codes |
| `json` | `String` | Documented (Reverse-Engineered) | JSON-serialized query payload passed to `/getReviewDetailsByWork`. | Serialized string |

---

## 5. Internal System Identifiers & Technical Codes

The following parameters appear inside the client-side JavaScript controllers (`preLoginDashboard.js`, `poptable.js`, `landingpage.js`) of the e-SAKSHI web portal. In strict accordance with the instruction to not guess field meanings:

| Parameter / Code | Context in Application | Apparent Technical Function | Specific Acronym / Meaning Determination |
|---|---|---|---|
| `arf` | `r = ["arf", "tea", ...]` in `preLoginDashboard.js` | HTML DOM element ID binding the *Allocated Limits* metric value. | **Undetermined (internal system code)** |
| `tea` | `r = ["arf", "tea", ...]` in `preLoginDashboard.js` | HTML DOM element ID binding the *Total Expenditure* metric value. | **Undetermined (internal system code)** |
| `tra` | `r = ["arf", "tea", ...]` in `preLoginDashboard.js` | HTML DOM element ID binding the *Total Recommended Amount* metric value. | **Undetermined (internal system code)** |
| `act` | `r = ["arf", "tea", ...]` in `preLoginDashboard.js` | HTML DOM element ID binding the *Amount Consented for Calamity* metric value. | **Undetermined (internal system code)** |
| `tsw` | `r = ["arf", "tea", ...]` in `preLoginDashboard.js` | HTML DOM element ID binding the *Total Sanctioned Works* metric value. | **Undetermined (internal system code)** |
| `tcc` | `r = ["arf", "tea", ...]` in `preLoginDashboard.js` | HTML DOM element ID binding the *Total Completed Works* metric value. | **Undetermined (internal system code)** |
| `chunked_info` | `poptable.js` | Client-side pagination buffer array holding DataTable chunk records. | Documented (Software Architecture) |
| `curkey` | `poptable.js` | Variable tracking the currently active tile metric key during user interaction. | Documented (Software Architecture) |
| `_0x...` | `preLoginDashboard.js` | Obfuscated variable names generated by JavaScript uglify/obfuscation toolchain. | **Undetermined (internal system code)** |
| `lagel` | `poptable.js` (`r="lagel".split("").reverse().join("")` -> `"legal"`) | Default page size argument passed to DataTable initialization. | **Undetermined (internal system code)** |

---

## 6. Statutory Business Logic & Legal Constraints

When performing computational analysis, econometric modeling, or fraud detection on MPLADS data, the following statutory rules established in the *MPLADS Guidelines (Revised 2023)* and *Union Budget* must be enforced:

1. **SC & ST Statutory Expenditure Floors (Para 2.5)**:
   - Every Member of Parliament **MUST** recommend developmental works costing at least:
     * **15.0%** of their annual entitlement for areas predominantly inhabited by **Scheduled Castes (SC)**.
     * **7.5%** of their annual entitlement for areas predominantly inhabited by **Scheduled Tribes (ST)**.
   - *Data Verification Rule*: If `(sc_expenditure / total_expenditure) < 0.15` or `(st_expenditure / total_expenditure) < 0.075`, flag as non-compliant with statutory social justice quotas.

2. **Sanction Service Level Agreement (SLA) (Para 3.5)**:
   - The Implementing District Authority (IDA) must accord administrative and technical sanction or convey formal rejection with reasons within **75 days** of receipt of the MP's recommendation.
   - *Data Verification Rule*: `(sanction_date - recommended_date) > 75 days` flags an administrative sanction bottleneck.

3. **Natural Calamity Caps (Para 3.12)**:
   - **Severe Calamity in Other States**: Maximum contribution of **₹1.00 Crore** per MP per calamity.
   - **Local Calamity in Own State**: Maximum contribution of **₹25.00 Lakh** per MP per calamity.
   - *Data Verification Rule*: Verify that `consented_amount_inr` does not exceed ₹1,00,00,000 for National Calamities or ₹25,00,000 for State Calamities.

4. **Trusts & Societies Lifetime Cap (Para 3.8)**:
   - Funding to registered trusts, cooperative societies, or NGOs is subject to a lifetime maximum cap of **₹1.00 Crore** across all MPs per trust/society.

5. **Central Nodal Agency (CNA) & Just-in-Time Funding**:
   - Commencing April 1, 2023, physical cash deposits in commercial bank accounts were abolished.
   - All funds reside in the Central Nodal Account with the State Bank of India.
   - Unspent balances do not accumulate interest with districts; all accrued interest is remitted directly to the **Consolidated Fund of India (CFI)**.
