# Fabric run status — 10 September 2026

## Verified

`fabric/load_warehouse.py` loaded the full raw data set into `WH_RedAndYellow.raw_salesforce` with Azure CLI authentication and ODBC Driver 17. All 13 source tables completed successfully:

| Table | Rows |
|---|---:|
| lead | 1,500,000 |
| contact | 1,138,726 |
| campaign_member | 2,533,440 |
| opportunity | 706,010 |
| application | 494,352 |
| student | 156,573 |
| enrolment | 168,157 |
| student_progress | 2,101,053 |
| programme_enquiry | 626,299 |
| campaign | 480 |
| programme | 83 |
| programme_offering | 89 |
| intake | 47 |

`dbt debug --target fabric` passes. The generated `raw_salesforce` sources resolve and `br_campaign` materialized as a Fabric bronze view.

## Not yet complete

The full Fabric dbt build exposed DuckDB-only SQL in silver and gold. The documented blockers are `date_diff`, `strftime`, `USING` joins, boolean shorthand, and other expressions that need T-SQL adapter dispatch. Bronze is real; Fabric silver, gold and quality outputs must not yet be described as deployed.

## Safe run order after the dialect repair

1. Run `python generator/scaffold_dbt.py`.
2. Set `FABRIC_SERVER` to the Warehouse SQL endpoint.
3. Run `dbt debug --profiles-dir . --target fabric` from `dbt_redandyellow`.
4. Run `dbt build --profiles-dir . --target fabric --no-populate-cache`.
5. Record model/test results and compare raw-table row counts before refreshing Power BI.
