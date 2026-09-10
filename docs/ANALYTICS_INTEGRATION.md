# Analytics integration

## Current delivery status — 10 September 2026

The platform uses Salesforce-shaped operational data and catalogue data through Apache NiFi, OneLake, dbt and Power BI. The programme catalogue and public prices are sourced from Red & Yellow’s public site; people, campaign performance and academic outcomes are synthetic demonstration data.

### Verified Salesforce write-back

The target Base Edition org contains the operational CRM slice that belongs in Salesforce: 25 Accounts, 408 Contacts, 408 Leads and 250 Opportunities (1,091 records tagged with RY_External_ID__c). salesforce/verify_org_counts.py queried the org and matched every tagged count to run_results/import_log.json. The supplied data-types reference is applied: operational CRM records live in Salesforce; raw GA4/clickstream, detailed history and ML training data remain in the warehouse.

### Which population each count describes

The smaller counts sometimes called the "missing sample data" are the staged CRM sample pack in `data/crm_load/`, not records currently present in Salesforce:

| Staged object | Rows | Current location |
|---|---:|---|
| Campaign | 48 | `data/crm_load/Campaign.csv` |
| CampaignMember | 74 | `data/crm_load/CampaignMember.csv` |
| RY_Application__c | 162 | `data/crm_load/RY_Application__c.csv` |
| RY_Enrolment__c | 84 | `data/crm_load/RY_Enrolment__c.csv` |
| RY_Programme_Enquiry__c | 192 | `data/crm_load/RY_Programme_Enquiry__c.csv` |
| RY_Student__c | 81 | `data/crm_load/RY_Student__c.csv` |
| RY_Student_Progress__c | 192 | `data/crm_load/RY_Student_Progress__c.csv` |

The full synthetic analytics population is separate. It is stored locally under `warehouse/raw/`, loaded to `WH_RedAndYellow.raw_salesforce` in Fabric, and transformed in `warehouse/redandyellow.duckdb` for the ebook, Excel workbook and Power BI model. The Fabric bronze run therefore reports much larger counts (for example 2,533,440 campaign members and 494,352 applications); those are analytical source rows, not the 48/74/162-row Salesforce demonstration pack.

### Verified paths

- Salesforce operational slice: loaded and extracted through the REST API with external IDs, `SystemModstamp`, source timestamps and deletion flags retained.
- Fabric bronze: the `raw_salesforce` schema contains all 13 landed tables. It includes 1,500,000 leads, 1,138,726 contacts, 2,533,440 campaign members, 706,010 opportunities, 494,352 applications, 168,157 enrolments and 2,101,053 student-progress rows.
- Fabric connectivity: the Warehouse accepts Azure CLI authentication through ODBC Driver 17; the generated dbt Fabric profile and a bronze model both pass.
- Power BI: the report has executive, campaign, admissions, quality, CRM and predictive pages, with Marketing Analytics and Recommendations & Solutions pages. The action page links each signal to an owner, intervention and success measure.

### Current limitation

DuckDB is the validated transformation runtime. Fabric bronze is loaded, but Fabric silver and gold still contain DuckDB-specific SQL that requires adapter-dispatched T-SQL replacements before `dbt build --target fabric` can finish. Do not treat a Fabric gold table as deployed until the build completes and its tests pass.

### Data movement and controls

Use paginated REST/Bulk extracts plus CDC or replication APIs where supported; a `SystemModstamp` filter alone does not prove complete replication. Commit destination writes before a checkpoint, retain `source_system`, `source_id`, source-modification time, load time and deletion state, and reconcile totals after each backfill. In production, student progress may stay in an LMS and join CRM only in the analytics layer.

