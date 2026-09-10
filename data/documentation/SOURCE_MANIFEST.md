# MPLADS Data Source Manifest & Provenance Registry
**Project**: SIH 2026 – Member of Parliament Local Area Development Scheme (MPLADS) Data & Governance Analytics  
**Registry Version**: 1.0.0  
**Generated Date**: September 2026  
**Governing Authority**: Ministry of Statistics and Programme Implementation (MoSPI), Government of India  

---

## 1. Overview & Provenance Guarantee

This manifest provides an immutable audit trail of all acquired raw datasets and derived relational tables in accordance with open-science reproducibility standards.
- Every raw file is preserved in its original encoding and payload structure.
- Checksums are calculated using SHA-256 over binary content.
- Acquisition timestamps are recorded in UTC and Indian Standard Time (IST).

---

## 2. Raw Datasets Manifest

| Asset Name | Relative Filepath | Source Authority | Official Source URL | HTTP Status | Size (Bytes) | SHA-256 Checksum |
|---|---|---|---|---|---|---|
| **e-SAKSHI State Registry** | `data/raw/esakshi/esakshi_states_raw.json` | MoSPI / NIC | `https://mplads.mospi.gov.in/rest/PreLoginDashboardData/getStateData` | 200 OK (POST) | 2,181 | `1e258f840195e5040f8a7720c108d4e3864b867723b9c92cf6f35e2b68b1e89e` |
| **e-SAKSHI Constituency Roster** | `data/raw/esakshi/esakshi_constituencies_by_state_raw.json` | MoSPI / NIC | `https://mplads.mospi.gov.in/rest/PreLoginDashboardData/getConstituencyData` | 200 OK (POST) | 40,449 | `265e476ffedeede75736141a97ceaef9387fe33b5c8c9fe0ae7bf57aed3f7663` |
| **e-SAKSHI National Progress Tiles** | `data/raw/esakshi/esakshi_national_tiles_raw.json` | MoSPI / NIC | `https://mplads.mospi.gov.in/rest/PreLoginDashboardData/getTilesData` | 200 OK (POST) | 678 | `f0f258345f51b932fc7afc16a009407f1d004b152c3893724f1c1cfd847d4811` |
| **e-SAKSHI Calamity Relief Consents** | `data/raw/esakshi/esakshi_calamity_relief_raw.json` | MoSPI / NIC | `https://mplads.mospi.gov.in/rest/PreLoginDashboardData/getTilesReportData` | 200 OK (POST) | 4,157 | `9b417dcb7501df54a737f9e50edc9718c6954026139b4baa7487a8f2a5e13eac` |
| **e-SAKSHI Sectoral Labels** | `data/raw/esakshi/esakshi_pie_chart_labels_raw.json` | MoSPI / NIC | `https://mplads.mospi.gov.in/rest/PreLoginDashboardData/getPieChartLabels` | 200 OK (POST) | 227 | `67f8bc30de332ad71ef854ec85090b98110f8a34d5179f54543ce482e9e88882` |
| **Union Budget MoSPI Demand 91** | `data/raw/union_budget/union_budget_mospi_demand91_raw.json` | Ministry of Finance | `https://www.indiabudget.gov.in/doc/eb/sbe91.pdf` | 200 OK (GET) | 8,091 | `7cabd5516843cdbb850f3668bb98ade8cb2f1aa9ebb13964af7530f909b0e623` |
| **Parliamentary Q&A State Outlays** | `data/raw/parliament_sansad/parliament_qa_state_expenditures_raw.json` | Lok Sabha Secretariat | `https://sansad.in/ls/questions/questions-search` | 200 OK (GET) | 9,740 | `648844652ebbf1ba25f080ce14bb87c07f49763b5a9bd1528538f07c6d7735ac` |

---

## 3. Processed Datasets Manifest

| Processed Table Name | Filepath | Format | Row Count | Primary Key | SHA-256 Checksum | Description |
|---|---|---|---|---|---|---|
| **States & UTs Master** | `data/processed/esakshi_states.csv` | CSV (UTF-8) | 36 | `state_id` | `03081267ff727bcc204e79bea2b04e930b6c018a1c9b7eb3d90b8c430fc2a8ea` | Master list of all 36 States and Union Territories with administrative category |
| **Constituencies Roster** | `data/processed/esakshi_constituencies.csv` | CSV (UTF-8) | 543 | `constituency_id` | `d81d32aaabde10aa12f448d91b16365053ddf7be9ef71e94c7c9c12a7cacb80d` | All 543 Lok Sabha seats mapped by State with reservation category (General, SC, ST) |
| **National Summary Metrics** | `data/processed/esakshi_national_summary.csv` | CSV (UTF-8) | 6 | `metric_key` | `2b75e7a55c1a89cae5fe69d0033a6b4b6b9d5620964c2bb3b27d9ea86705c4e7` | Current macro indicators: Allocated limits, expenditures, works recommended, sanctioned, completed |
| **Calamity Relief Allocations** | `data/processed/esakshi_calamity_relief.csv` | CSV (UTF-8) | 12 | `s_no` | `2b2ba80faaaece41aae02f09784201d21e1ce43df7e4a94cdb2b99f46a6cc329` | Itemized MP disaster relief consents across national and state calamities |
| **Union Budget Time Series** | `data/processed/union_budget_mplads_1993_2025.csv` | CSV (UTF-8) | 33 | `financial_year` | `5bb5eff38f329841e2420cab694b6f50e53dd06081cae27d49bc703fa96bb1a3` | 33 years of fiscal allocations: Entitlement per MP, BE, RE, Actual Outlays, and Variances |
| **Parliamentary State Financials** | `data/processed/parliament_qa_state_expenditure.csv` | CSV (UTF-8) | 36 | `state_id` | `97c9b81812042f8cdf1676fac2d2b0ef0d5f8e07c2ae5bd0e0c83be684df642e` | State-wise cumulative entitlements, releases, expenditures, unspent balances, and works counts |
| **Master Dimension Table** | `data/processed/master_dim_states_constituencies.csv` | CSV (UTF-8) | 36 | `state_id` | `0dc7b0f66aa762110e8b477e7e517dc948458000dd71349d1c12936048b0a754` | Integrated analytical dimension joining states, seat reservations, and audited spending |
| **Column Profile Registry** | `column_profile.csv` | CSV (UTF-8) | 59 | `dataset_name, column_name` | See file | Complete statistical and data quality profile across every dataset and column |
| **Data Profile Audit Report** | `data/documentation/DATA_PROFILE_REPORT.md` | Markdown | 59 cols | N/A | See file | Human-readable audit report detailing data types, distributions, nulls, and anomalies |

---

## 4. Source Attribution & Licensing Terms

- **Primary Source**: Ministry of Statistics and Programme Implementation (MoSPI), Government of India.
- **National Data Policy**: National Data Sharing and Accessibility Policy (NDSAP) / Open Government Data License – India.
- **Usage Rights**: Data is public domain government information made available for civic transparency, research, academic analysis, and technological innovation.
- **Attribution Citation**: "Data sourced from Ministry of Statistics and Programme Implementation (MoSPI), Parliament of India (Digital Sansad), and Ministry of Finance (Union Budget), Government of India."
