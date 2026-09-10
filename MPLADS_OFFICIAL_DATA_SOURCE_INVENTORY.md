# Comprehensive Official MPLADS Data Source Inventory
**Project**: SIH 2026 – Member of Parliament Local Area Development Scheme (MPLADS) Data & Governance Analytics  
**Date**: September 2026  
**Status**: Research & Inventory Phase (Pre-Download Verification)  
**Governing Ministry**: Ministry of Statistics and Programme Implementation (MoSPI), Government of India  

---

## Executive Summary of the Data Landscape

The Member of Parliament Local Area Development Scheme (MPLADS) was introduced in December 1993 to enable Members of Parliament (MPs) to recommend developmental works of capital nature in their constituencies. Financially, the scheme currently provides **₹5 Crore per MP per annum** in two installments of ₹2.5 Crore each (with mandatory sub-allocations: at least **15% for Scheduled Caste (SC)** inhabited areas and **7.5% for Scheduled Tribe (ST)** areas).

In terms of data infrastructure, the Government of India operates across **two distinct historical eras**:
1. **The Legacy Era (1993 – March 31, 2023)**: Operated through decentralized district bank accounts and the legacy Work Monitoring System (WMS) hosted at `mplads.gov.in` / `mplads.nic.in`. Reporting was heavily reliant on physical files and periodic Utilization Certificates (UCs) sent by District Authorities to MoSPI.
2. **The e-SAKSHI Digital Era (April 1, 2023 – Present)**: MoSPI launched the revised fund-flow procedure adhering to Department of Expenditure (Ministry of Finance) Central Nodal Agency (CNA) guidelines. All operations transitioned to the **e-SAKSHI Portal** (`mplads.mospi.gov.in`), utilizing a Single Central Nodal Account with State Bank of India integrated with the Public Financial Management System (PFMS). This portal provides end-to-end digital tracking from MP recommendation to district sanction, contractor billing, and geo-tagged asset verification.

Below is the exhaustive, verified source inventory across all official Government of India portals.

---

## Source Inventory Table

| Source ID | Portal / System Name | Governing Body | Official URL(s) | Primary Formats | Years Covered | Geographic Granularity | API / Download Availability |
|---|---|---|---|---|---|---|---|
| **SRC-01** | **e-SAKSHI Portal (Public Dashboard & Work Tracker)** | MoSPI / NIC | `https://mplads.mospi.gov.in/`<br>`/digigov/dashboard.html` | JSON, Excel (`.xlsx`), Geo-tagged Images (JPEG/PNG), HTML | 2023–Present (17th LS late & 18th LS) | National down to Geo-tagged Work Site (Lat/Long) | De-obfuscated REST APIs, DataTables Excel export, Web view |
| **SRC-02** | **e-SAKSHI Citizen Engagement & Review Interface** | MoSPI / NIC | `https://mplads.mospi.gov.in/`<br>`/landingpage.html` | JSON, HTML, Attachment streams | 2023–Present | State, District, Block, Ward/Village, Work ID | Citizen REST APIs (OTP authenticated for reviews) |
| **SRC-03** | **Legacy MPLADS Portal & MIS Dashboard** | MoSPI / NIC | `https://www.mplads.gov.in/`<br>`/MPLADS/Dashboard/` | ASPX HTML, CSV, Excel, PDF | 1993–March 2023 (10th to 17th LS) | National, State/UT, Constituency, District | ASPX table exports, web scraping (ViewState required) |
| **SRC-04** | **Open Government Data (OGD) Platform India** | NIC / MeitY / MoSPI | `https://data.gov.in/`<br>`https://api.data.gov.in/` | CSV, XLS, XML, JSON | Periodic (14th, 15th, 16th, select 17th LS) | State/UT, District, Constituency | Direct CSV download, OGD REST API (API key required) |
| **SRC-05** | **MoSPI Corporate Portal & Statistical Archives** | MoSPI (MPLADS Div) | `https://www.mospi.gov.in/`<br>`https://www.mospi.gov.in/mplads` | PDF, HTML tables | 1993–Present (FY 2024–25) | National, State/UT, District aggregates | Direct PDF downloads (Annual Reports, Guidelines, Circulars) |
| **SRC-06** | **Digital Sansad – Lok Sabha Q&A Records** | Lok Sabha Secretariat | `https://sansad.in/ls`<br>`https://eparlib.nic.in` | PDF Annexures, HTML text | 1993–Present (10th to 18th LS) | Constituency, MP, District, State | PDF document downloads, Parliamentary search engine |
| **SRC-07** | **Digital Sansad – Rajya Sabha Q&A Records** | Rajya Sabha Secretariat | `https://sansad.in/rs` | PDF Annexures, HTML text | 1993–Present | State-level, Nominated MPs (National), Nodal District | PDF document downloads, Parliamentary search engine |
| **SRC-08** | **Parliamentary Committee on MPLADS Reports** | Lok Sabha & Rajya Sabha | `https://sansad.in/ls` & `https://sansad.in/rs` | PDF Reports | 10th Lok Sabha to Present | Pan-India, Sample districts | Direct PDF downloads |
| **SRC-09** | **DISHA Portal (District Development Coordination)** | MoRD / NIC | `https://disha.gov.in/` | Interactive GIS, GeoJSON, CSV | 2016–Present | District, Constituency, Block | Interactive map/chart views; CSV exports (some roles restricted) |
| **SRC-10** | **Public Financial Management System (PFMS)** | CGA, Min of Finance | `https://pfms.nic.in/` | Financial Reports, HTML, Excel | 2021–Present (CNA mandated) | National CNA account to Vendor/Beneficiary | Public scheme outlay views; transaction ledger is SSO restricted |
| **SRC-11** | **Union Budget Portal (Expenditure Budget)** | Min of Finance | `https://www.indiabudget.gov.in/` | PDF, Excel (`.xls`, `.xlsx`) | 1993–Present (FY 2025–26) | National (Major Heads 3475, 4552, 2552) | Direct Excel and PDF downloads |
| **SRC-12** | **Comptroller & Auditor General (CAG) Audit Reports** | CAG of India | `https://cag.gov.in/` | PDF Reports | 1998, 2001, 2010–11, periodic audits | National, State, Sample Districts | Direct PDF chapter downloads |
| **SRC-13** | **Development Monitoring & Evaluation Office (DMEO)** | NITI Aayog | `https://dmeo.gov.in/` | PDF Reports, Indicator Matrices | 2015–Present | National, State samples | Direct PDF downloads |
| **SRC-14** | **National Data & Analytics Platform (NDAP)** | NITI Aayog | `https://ndap.niti.gov.in/` | Harmonized CSV, Excel, JSON API | Select historical time series | Standardized District and State hierarchies | Direct CSV/Excel download, NDAP REST API |

---

## Detailed Source Inventory Profiles

---

### SRC-01: e-SAKSHI Portal (Public Dashboard & Work Tracker)
* **Governing Body**: Ministry of Statistics and Programme Implementation (MoSPI) in collaboration with NIC.
* **Official URLs**:
  - Main Portal: `https://mplads.mospi.gov.in/`
  - Public Dashboard: `https://mplads.mospi.gov.in/digigov/dashboard.html`
  - Client Application Assets: `https://mplads.mospi.gov.in/libs/simplegrid/preLoginDashboard.js`, `loksaba.js`, `rajyasaba.js`, `poptable.js`, `graph.js`
* **Data Formats**:
  - JSON (REST API responses)
  - Microsoft Excel (`.xlsx`) via client-side DataTables export (`buttons.html5.min.js`)
  - Image binaries (Geo-tagged photos of assets in JPEG/PNG via `/rest/PreLoginDashboardData/stream`)
* **Years Covered**: April 1, 2023 to Present (post-reform period: end of 17th Lok Sabha & ongoing 18th Lok Sabha).
* **Geographic Coverage**:
  - National level
  - State / Union Territory level
  - Parliamentary Constituency (543 Lok Sabha seats)
  - State-representation for 245 Rajya Sabha members
  - Implementing District Authority (IDA / District Collectorate)
  - Block, Urban Local Body (ULB) / Ward, Gram Panchayat
  - Exact Geo-tagged project site coordinates
* **Fields Available**:
  - **Financial Metrics**: Allocated Limits (₹), Sanctioned Amount (₹), Released Limits, Expended Amount (₹), Payment Status (Pending, Paid, Failed), Expenditure Date, Calamity Relief Consent Date and Consented Amount (₹).
  - **Physical Works**: Work Unique ID, Work Title / Description, Work Category / Sector (e.g., Drinking water, Education, Roads, Health, Sanitation), Recommendation Date by MP, Sanction Date by District Authority, Work Status (Recommended, Sanctioned, In Progress, Completed, Rejected), Executing Agency Name.
  - **Elected Representative Metadata**: Hon'ble MP Name, House (Lok Sabha / Rajya Sabha), Tenure, Representation Type (Elected / Nominated), Home / Nodal District.
  - **Asset Verification**: Geo-tagged photographs of works before, during, and after execution, Attachment IDs, Physical completion certificates.
* **API / Download Availability**:
  - **Direct Client REST Endpoints** (Reverse-engineered from application scripts):
    * `POST /rest/PreLoginDashboardData/getTilesData`: Macro metrics (Allocated limits, works count, expenditure). Payload format: `{"uname": "<house_code>,<tenure_code>,<state_code>,<constituency_code>"}`.
    * `POST /rest/PreLoginDashboardData/getTotalTilesData`: Pan-India aggregated metrics.
    * `POST /rest/PreLoginDashboardData/getTilesReportData`: Detailed tabular listings backing the modal popups.
    * `POST /rest/PreLoginDashboardData/getStateData`: State-wise summary data.
    * `POST /rest/PreLoginDashboardData/getConstituencyData`: Constituency-level drilldown.
    * `POST /rest/PreLoginDashboardData/getMpNamesData`: Member of Parliament roster mapping.
    * `POST /rest/PreLoginDashboardData/getMpAndConstCombo`: Cascading dropdown pairings.
    * `POST /rest/PreLoginDashboardData/getTenureData`: Tenure definitions (17th LS, 18th LS, RS tenures).
    * `POST /rest/PreLoginDashboardData/getgraphdata` & `getPieChartLabels`: Sectoral distribution data.
    * `POST /rest/PreLoginDashboardData/getAttachIdsbyFlag`: Photo and document reference IDs.
    * `GET /rest/PreLoginDashboardData/stream`: Direct binary streaming of asset photographs.
  - **Download Buttons**: Built-in Excel HTML5 export (`excelHtml5`) and Print buttons rendered on modal DataTables (`#tablepag`).
* **Limitations & Data Gaps**:
  - **No Pre-2023 Digital History**: Financial and physical data prior to April 1, 2023 was executed through physical ledgers and district bank accounts; it is not migrated to the e-SAKSHI database.
  - **No Public API Documentation**: Endpoints are internal AJAX calls powering the frontend rather than an officially documented developer API.
  - **Latency & Timeouts**: Government NIC servers frequently encounter request timeouts during peak hours or heavy JSON queries.
  - **Absence of Bulk Tar/Zip Dump**: No single-click complete database dump is provided for research analytics.

---

### SRC-02: e-SAKSHI Citizen Engagement & Review Interface
* **Governing Body**: MoSPI / NIC.
* **Official URLs**:
  - Citizen Landing: `https://mplads.mospi.gov.in/landingpage.html`
  - JavaScript Controller: `https://mplads.mospi.gov.in/libs/simplegrid/landingpage.js`
* **Data Formats**: JSON, HTML, Form-data.
* **Years Covered**: 2023–Present.
* **Geographic Coverage**: Administrative hierarchy: State -> District -> Block / City -> Village / Ward.
* **Fields Available**:
  - Work Review Details: Citizen review ratings (1 to 5 stars), qualitative feedback on asset quality, issue reporting on completed works.
  - Geographic master codes: State codes, District codes, Block codes, Village census codes, City/Ward codes.
  - Completed works catalog per MP: Title, category, completion date, location description.
* **API / Download Availability**:
  - REST Endpoints:
    * `POST /rest/PreLoginCitizenWorkRcmdRest/getComboStateData`
    * `POST /rest/PreLoginCitizenWorkRcmdRest/getDistrictByState`
    * `POST /rest/PreLoginCitizenWorkRcmdRest/getBlockByDistrict`
    * `POST /rest/PreLoginCitizenWorkRcmdRest/getVillageByBlock`
    * `POST /rest/PreLoginCitizenWorkRcmdRest/getCityByDistrict`
    * `POST /rest/PreLoginCitizenWorkRcmdRest/getWardByCity`
    * `POST /rest/PreLoginCitizenWorkRcmdRest/getMpByDistrictAndState`
    * `POST /rest/PreLoginCitizenWorkRcmdRest/getAllCompletedWorkByMP`
    * `POST /rest/PreLoginCitizenWorkRcmdRest/getReviewDetailsByWork`
    * `POST /rest/PreLoginCitizenWorkRcmdRest/getWorkReviewDataByCtzn`
* **Limitations & Data Gaps**:
  - Submitting citizen feedback requires OTP authentication via Indian mobile numbers (`/generateOTPForCitizenLogin` and `/verifyOTPForCitizenLogin`).
  - Read-only viewing of completed works is possible, but citizen feedback scores are partially redacted to prevent defamation.

---

### SRC-03: Legacy MPLADS Portal & MIS Dashboard (1993–2023 Archive)
* **Governing Body**: Ministry of Statistics and Programme Implementation (MoSPI) & National Informatics Centre.
* **Official URLs**:
  - Legacy Portal Base: `https://www.mplads.gov.in/`
  - Legacy GIS Dashboard: `https://www.mplads.gov.in/MPLADS/Dashboard/DashBoard.aspx`
  - Work Monitoring System (WMS) Root: `https://www.mplads.gov.in/MPLADS/`
  - NIC Mirror: `https://mplads.nic.in/`
* **Data Formats**: ASP.NET (ASPX) generated HTML tables, CSV / Excel exports via server-side postback, static PDF reports.
* **Years Covered**: Inception in December 1993 through March 31, 2023 (Covering the 10th, 11th, 12th, 13th, 14th, 15th, 16th, and early 17th Lok Sabha).
* **Geographic Coverage**: National, State/UT, Parliamentary Constituency, District, MP level.
* **Fields Available**:
  - **Financial Metrics**: Entitlement (₹ Crore), Funds Released by Central Government, Expenditure Reported by District Authorities, Unspent Balance with Districts, Percentage Utilization, Interest Accrued.
  - **Priority Sector Reports**: Funds committed and spent under mandatory provisions (Minimum 15% for Scheduled Caste inhabited areas, Minimum 7.5% for Scheduled Tribe inhabited areas).
  - **Physical Works Summary**: Number of works recommended by MP, Number of works sanctioned by District Authority, Number of works completed, Number of works pending / canceled, Cost of completed works.
* **API / Download Availability**:
  - No REST API.
  - Relies on ASP.NET WebForms (`__VIEWSTATE`, `__EVENTVALIDATION`, `__VIEWSTATEGENERATOR`) postbacks.
  - Periodic static downloads for "Fund Release Statements" and "Cumulative Utilization Reports".
* **Limitations & Data Gaps**:
  - **Server Inaccessibility**: Since the launch of e-SAKSHI on April 1, 2023, the legacy portal servers frequently time out, experience SSL errors, or are temporarily unreachable.
  - **Data Reconciliation Gap**: There is a well-documented divergence between central releases and district expenditure due to delays in submitting physical Utilization Certificates (UCs) and Audit Certificates (ACs).
  - **No Project-Level Microdata in Public Domain**: Most reports are aggregated at the constituency or district level; individual work order numbers and contractor details are absent from the public tier.

---

### SRC-04: Open Government Data (OGD) Platform India (data.gov.in)
* **Governing Body**: National Informatics Centre (NIC), Ministry of Electronics and Information Technology (MeitY), with MoSPI as data contributor.
* **Official URLs**:
  - Portal: `https://data.gov.in/`
  - API Gateway: `https://api.data.gov.in/`
  - Ministry Catalog: Search under `Ministry of Statistics and Programme Implementation`
* **Data Formats**: CSV, XLS / XLSX, XML, JSON.
* **Years Covered**: Episodic snapshots covering 2004–2019 (14th, 15th, and 16th Lok Sabhas) and select tables for the 17th Lok Sabha.
* **Geographic Coverage**: State/UT, District, and Parliamentary Constituency level.
* **Fields Available**:
  - State/UT Name, Constituency Code / Name, MP Name, Lok Sabha Session / Tenure.
  - Government Releases (₹ Lakhs / Crores), Expenditure Incurred (₹ Lakhs / Crores), Unspent Balance.
  - Works Recommended (Count), Works Sanctioned (Count), Works Completed (Count).
* **API / Download Availability**:
  - Direct one-click download for CSV and Excel files.
  - Machine-readable OGD REST API requiring registration for a developer API key (`api-key=YOUR_KEY`).
* **Limitations & Data Gaps**:
  - **Lack of Real-Time Updates**: Datasets on data.gov.in are periodic static dumps, not live-streamed or automated from e-SAKSHI.
  - **Search Discoverability**: Querying "MPLADS" directly on the search bar often yields limited catalog entries because datasets are nested under general MoSPI administrative publication categories.
  - **No Micro-Level Works**: Datasets contain aggregated tabular rows rather than individual work-site records.

---

### SRC-05: MoSPI Official Corporate Portal & Statistical Publications
* **Governing Body**: MoSPI, Government of India.
* **Official URLs**:
  - Main Portal: `https://www.mospi.gov.in/`
  - Dedicated MPLADS Division Page: `https://www.mospi.gov.in/mplads`
  - Official Guidelines PDF: `https://www.mplads.gov.in/MPLADS/UploadedFiles/MPLADSGuidelines2023_English_.pdf`
* **Data Formats**: PDF (Annual Reports, Guidelines, Circulars, Office Memorandums), HTML tables.
* **Years Covered**: 1993 to Present (FY 2024–25).
* **Geographic Coverage**: National, State/UT, District.
* **Fields Available**:
  - **Regulatory Guidelines**: MPLADS Guidelines 2016, Revised Guidelines 2023 (establishing the Central Nodal Agency model, web-portal workflows, interest repatriation to Consolidated Fund of India).
  - **Policy Directives**: Lists of permissible vs. non-permissible works, calamity relief caps (up to ₹1 Crore for severe natural calamities in other states, ₹25 Lakh for local calamities), trusts/societies funding rules (lifetime cap of ₹1 Crore per trust/society).
  - **Annual Progress Chapters**: Dedicated chapter in the MoSPI Annual Report detailing scheme outlays, releases, expenditure percentages, state-wise rankings, and administrative overheads.
* **API / Download Availability**:
  - Direct PDF downloads. No REST API.
* **Limitations & Data Gaps**:
  - Data is published as unstructured text and static tabular annexures inside multi-hundred-page PDF reports.
  - Requires OCR or programmatic PDF table extraction (e.g., via `pdfplumber` or `Camelot`) to convert into structured time-series datasets.

---

### SRC-06: Digital Sansad – Lok Sabha Question & Answer System
* **Governing Body**: Lok Sabha Secretariat, Parliament of India.
* **Official URLs**:
  - Digital Sansad Portal: `https://sansad.in/ls`
  - Questions Search: `https://sansad.in/ls/questions/questions-search`
  - Parliamentary Digital Library: `https://eparlib.nic.in/`
* **Data Formats**: PDF Annexures, HTML Question & Answer texts.
* **Years Covered**: 1993 to Present (10th Lok Sabha through 18th Lok Sabha).
* **Geographic Coverage**: All 543 Lok Sabha Constituencies, State-wise, MP-wise.
* **Fields Available**:
  - Minister of State for Statistics and Programme Implementation written replies.
  - Annexure Tables containing authoritative parliamentary statements on:
    * MP-wise funds entitled, released, expenditure reported, and unspent balances.
    * Works recommended, sanctioned, pending sanction (>75 days delay), and completed.
    * Special inquiries: Unspent funds lapsed during COVID-19 suspension (FY 2020–21 and FY 2021–22), implementation of 2023 revised guidelines, and district-level bottlenecks.
* **API / Download Availability**:
  - Searchable by Session, Ministry (MoSPI), Question Type (Starred/Unstarred), and MP Name.
  - Individual PDF downloads of question texts and data annexures.
  - No public REST API; requires web scraping or batch PDF retrieval.
* **Limitations & Data Gaps**:
  - Data frequency is tied to parliamentary sitting schedules (Budget, Monsoon, Winter sessions).
  - Table schemas vary significantly between questions depending on the specific wording of the MP's inquiry.

---

### SRC-07: Digital Sansad – Rajya Sabha Question & Answer System
* **Governing Body**: Rajya Sabha Secretariat, Parliament of India.
* **Official URLs**:
  - Rajya Sabha Portal: `https://sansad.in/rs`
  - Questions Search: `https://sansad.in/rs/questions/questions-search`
* **Data Formats**: PDF Annexures, HTML text.
* **Years Covered**: 1993 to Present.
* **Geographic Coverage**: State-wise representation, Nominated MPs (nationwide choices), Nodal District level.
* **Fields Available**:
  - Rajya Sabha Member fund allocations, releases, and expenditures.
  - Nodal district expenditure tracking for Rajya Sabha MPs (who can select any district in their State of election).
  - Multi-state work recommendations by Nominated Rajya Sabha members.
* **API / Download Availability**:
  - Searchable web repository with direct PDF downloads.
* **Limitations & Data Gaps**:
  - Rajya Sabha data is harder to aggregate geographically because an RS MP represents an entire State, meaning works may be dispersed across dozens of districts without a single fixed constituency boundary.

---

### SRC-08: Parliamentary Committees on MPLADS (Lok Sabha & Rajya Sabha)
* **Governing Body**: Committee on MPLADS (Lok Sabha) & Committee on MPLADS (Rajya Sabha).
* **Official URLs**:
  - Lok Sabha Committees: `https://sansad.in/ls` (Committees section)
  - Rajya Sabha Committees: `https://sansad.in/rs` (Committees section)
* **Data Formats**: PDF Reports (Numbered Reports and Action Taken Reports - ATRs).
* **Years Covered**: 10th Lok Sabha to Present.
* **Geographic Coverage**: Pan-India systemic reviews and selected district site inspections.
* **Fields Available**:
  - Parliamentary reviews of MoSPI scheme implementation.
  - Case studies on district administration non-compliance, arbitrary rejections of MP recommendations, delays in executing sanctioned works, and contractor cartelization.
  - Action Taken Notes (ATNs) showing formal MoSPI policy adjustments in response to committee observations.
* **API / Download Availability**:
  - Direct PDF downloads of published committee reports.
* **Limitations & Data Gaps**:
  - Qualitative and oversight oriented; contains qualitative evaluations rather than raw quantitative datasets.

---

### SRC-09: DISHA Portal (District Development Coordination and Monitoring Committee)
* **Governing Body**: Ministry of Rural Development (MoRD) in technical partnership with NIC.
* **Official URLs**:
  - Main Portal: `https://disha.gov.in/`
* **Data Formats**: Interactive GIS maps, HTML5 dashboard widgets, GeoJSON layers, CSV exports.
* **Years Covered**: ~2016 to Present.
* **Geographic Coverage**: District, Parliamentary Constituency, Block level across India.
* **Fields Available**:
  - Progress indicators of MPLADS integrated alongside 43+ central flagship schemes (PMGSY, PMAY, MGNREGA, Jal Jeevan Mission, etc.).
  - Cross-scheme geospatial mapping: visual inspection of infrastructure overlap between MPLADS assets and rural development schemes.
  - DISHA Committee meeting calendar, attendance by MPs, and action points logged.
* **API / Download Availability**:
  - Visual dashboard accessible online.
  - Detailed district administrative datasets require government credentials (NIC SSO); public view provides macro dashboards.
* **Limitations & Data Gaps**:
  - Focuses on multi-scheme convergence rather than isolated MPLADS accounting.
  - Granular work-level transaction data is routed back to e-SAKSHI.

---

### SRC-10: Public Financial Management System (PFMS) – Central Nodal Agency
* **Governing Body**: Controller General of Accounts (CGA), Department of Expenditure, Ministry of Finance.
* **Official URLs**:
  - Main Portal: `https://pfms.nic.in/`
* **Data Formats**: Financial ledger tables, HTML, Excel exports.
* **Years Covered**: 2021 to Present (Mandatory CNA procedure operational from April 1, 2023).
* **Geographic Coverage**: Central Nodal Agency (SBI CNA Account) -> Sub-Agencies (Implementing District Authorities) -> Vendor / Beneficiary accounts.
* **Fields Available**:
  - Central Sector Scheme Code for MPLADS.
  - Just-in-Time (JIT) electronic fund transfers, Drawing Limits allocated to District Collectors, electronic payment vouchers (e-payments), and real-time interest accrued and remitted back to the Consolidated Fund of India (CFI).
* **API / Download Availability**:
  - Restricted internal government network. Public interface provides scheme outlay totals and CNA scheme lists.
* **Limitations & Data Gaps**:
  - Transaction-level vouchers and vendor bank accounts are strictly protected under government authentication and data privacy rules.

---

### SRC-11: Union Budget Portal (Ministry of Finance)
* **Governing Body**: Budget Division, Department of Economic Affairs, Ministry of Finance.
* **Official URLs**:
  - Union Budget Portal: `https://www.indiabudget.gov.in/`
  - Expenditure Budget (Demand No. 91 - MoSPI): Accessible under annual budget publications.
* **Data Formats**: PDF, Microsoft Excel (`.xls`, `.xlsx`).
* **Years Covered**: Inception (FY 1993–94) to Present (FY 2025–26).
* **Geographic Coverage**: National Level.
* **Fields Available**:
  - Demand No. 91: Ministry of Statistics and Programme Implementation.
  - Financial Outlays across three primary budget heads:
    * Major Head 3475: General Economic Services – Scheme for Members of Parliament Local Area Development.
    * Major Head 2552: North Eastern Areas.
    * Major Head 4552: Capital Outlay on North Eastern Areas.
  - Figures provided: Budget Estimates (BE), Revised Estimates (RE), and Actual Expenditure (Actuals).
* **API / Download Availability**:
  - Direct download of Excel spreadsheets and PDF budget documents.
* **Limitations & Data Gaps**:
  - Macro-level fiscal data only; no sub-national, constituency, or project-level breakdown.

---

### SRC-12: Comptroller and Auditor General (CAG) of India Audit Reports
* **Governing Body**: Supreme Audit Institution of India (CAG).
* **Official URLs**:
  - Portal: `https://cag.gov.in/`
  - Audit Reports Repository: `https://cag.gov.in/en/audit-reports`
* **Data Formats**: PDF reports.
* **Years Covered**:
  - Landmark Performance Audit Report No. 31 of 2010–11 (Covering FY 2004–05 to 2008–09).
  - Previous Performance Audits: Report of 1998, Report of 2001.
  - Periodic Union Civil & State Compliance Audit Reports (isolated chapters).
* **Geographic Coverage**: Pan-India across audited sample districts and states.
* **Fields Available**:
  - Rigorous forensic audit findings: Idle unspent funds in commercial bank accounts, unauthorized diversion of funds for administrative expenditures or private institutions, execution of works without administrative/technical sanction, non-maintenance of Asset Registers, and non-furnishing of Utilization Certificates.
* **API / Download Availability**:
  - Free public download of full PDF reports and executive summaries.
* **Limitations & Data Gaps**:
  - Audits are based on statistical sample testing rather than continuous real-time monitoring of all works.

---

### SRC-13: Development Monitoring and Evaluation Office (DMEO) – NITI Aayog
* **Governing Body**: NITI Aayog, Government of India.
* **Official URLs**:
  - Portal: `https://dmeo.gov.in/`
  - Evaluation Studies: `https://dmeo.gov.in/reports-evaluations`
* **Data Formats**: PDF Evaluation Reports, Indicator Matrices.
* **Years Covered**: 2015 to Present (Evaluation Study of MPLADS conducted ~2020/2021).
* **Geographic Coverage**: Sample states, districts, and parliamentary constituencies.
* **Fields Available**:
  - Output-Outcome Monitoring Framework (OOMF) performance matrices:
    * Output Indicators: Number of recommended works sanctioned, average time taken for sanction (target vs. actual), funds released to IDAs.
    * Outcome Indicators: Percentage of assets found operational during physical ground verification, community satisfaction scores, and socio-economic asset utility in SC/ST areas.
* **API / Download Availability**:
  - Downloadable PDF documents.
* **Limitations & Data Gaps**:
  - Periodic evaluation reports rather than a streaming or dynamic transaction registry.

---

### SRC-14: National Data & Analytics Platform (NDAP) – NITI Aayog
* **Governing Body**: NITI Aayog.
* **Official URLs**:
  - Portal: `https://ndap.niti.gov.in/`
* **Data Formats**: Standardized CSV, Excel, Machine-readable API.
* **Years Covered**: Select historical series aligned with decadal census and district boundaries.
* **Geographic Coverage**: Standardized District and State hierarchies.
* **Fields Available**:
  - Harmonized administrative datasets containing district-level scheme metrics merged with socio-economic indicators (Census 2011 boundaries, NFHS, SECC).
* **API / Download Availability**:
  - Direct CSV/Excel download and standardized query API upon user registration.
* **Limitations & Data Gaps**:
  - Relies on periodic data ingestion from MoSPI; does not reflect live day-to-day transactions from the e-SAKSHI portal.

---

## Technical Data Matrix & Field Comparison

| Data Dimension | e-SAKSHI Portal (SRC-01) | Legacy WMS Portal (SRC-03) | data.gov.in (SRC-04) | Digital Sansad Q&A (SRC-06) | Union Budget (SRC-11) |
|---|---|---|---|---|---|
| **Temporal Granularity** | Real-time / Daily | Monthly / Quarterly | Periodic static dump | Session-wise (3x/year) | Annual (BE, RE, Actuals) |
| **Lowest Spatial Level** | Geo-tagged Work Site (Lat/Long) | District / Constituency | Constituency / District | MP / Constituency | National |
| **Individual Work Descriptions** | Yes (Full title & scope) | Limited / Incomplete | No (Aggregates only) | Select sample annexures | No |
| **Asset Photographs** | Yes (Pre/During/Post) | No | No | No | No |
| **Financial Accounting** | JIT Drawing Limits (CNA/PFMS) | Cash releases to District A/C | Cumulative releases/exp | Cumulative releases/exp | Fiscal Head allocations |
| **Vendor / Contractor Data** | Partially (Sanctioned agency) | No | No | No | No |
| **Citizen Verification** | Yes (Review & Rating) | No | No | No | No |
| **Machine-Readability** | JSON REST & Excel export | HTML / ASPX tables | CSV, XLS, JSON API | PDF (Unstructured text) | Excel (`.xlsx`), PDF |

---

## Recommended Strategy for SIH 2026 Project Pipeline

To construct a robust, production-grade MPLADS analytics platform for SIH 2026, the data ingestion pipeline should follow a **tiered multi-source strategy**:

1. **Tier 1 (Real-Time & Micro-Level Ingestion)**:
   - Target **SRC-01 (e-SAKSHI REST Endpoints)**: Script an automated ETL pipeline against `/rest/PreLoginDashboardData/*` to capture real-time state, constituency, MP, and work-level records including geo-tagged image IDs.
   - Utilize `/rest/PreLoginCitizenWorkRcmdRest/*` to map the administrative hierarchy (State -> District -> Block -> Village/Ward).

2. **Tier 2 (Historical Baseline 1993–2023 Ingestion)**:
   - Extract historical benchmarks from **SRC-06 (Parliamentary Q&A Annexures)** and verified public data archives (e.g. Dataful/OpenCity aggregations of legacy MoSPI records) to bridge the 1993–2023 pre-eSAKSHI data gap.
   - Cross-check total cumulative allocations and expenditures against **SRC-11 (Union Budget Actuals)**.

3. **Tier 3 (Governance, Compliance & Accountability Indexing)**:
   - Ingest compliance parameters based on **SRC-05 (2023 Guidelines)** and **SRC-12 (CAG audit checklists)**:
     * Check if 15% SC and 7.5% ST statutory targets are met per MP.
     * Flag works taking longer than the mandated 75 days for district administrative sanction.
     * Detect unspent balance hoarding and fund-flow bottlenecks.
     * Validate physical asset delivery using geo-tagged coordinates and imagery.

---
*Inventory compiled and verified against official Government of India endpoints.*
