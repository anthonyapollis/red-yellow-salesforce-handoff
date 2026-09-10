# Analytics integration

## Current delivery status — 10 September 2026

The platform uses Salesforce-shaped operational data and catalogue data through Apache NiFi, OneLake, dbt and Power BI. The programme catalogue and public prices are sourced from Red & Yellow’s public site; people, campaign performance and academic outcomes are synthetic demonstration data.

### Verified paths

- Salesforce operational slice: loaded and extracted through the REST API with external IDs, `SystemModstamp`, source timestamps and deletion flags retained.
- Fabric bronze: the `raw_salesforce` schema contains all 13 landed tables. It includes 1,500,000 leads, 1,138,726 contacts, 2,533,440 campaign members, 706,010 opportunities, 494,352 applications, 168,157 enrolments and 2,101,053 student-progress rows.
- Fabric connectivity: the Warehouse accepts Azure CLI authentication through ODBC Driver 17; the generated dbt Fabric profile and a bronze model both pass.
- Power BI: the report has executive, campaign, admissions, quality, CRM and predictive pages, with a seventh Marketing Analytics page defined in the generator for the next safe rebuild.

### Current limitation

DuckDB is the validated transformation runtime. Fabric bronze is loaded, but Fabric silver and gold still contain DuckDB-specific SQL that requires adapter-dispatched T-SQL replacements before `dbt build --target fabric` can finish. Do not treat a Fabric gold table as deployed until the build completes and its tests pass.

### Data movement and controls

Use paginated REST/Bulk extracts plus CDC or replication APIs where supported; a `SystemModstamp` filter alone does not prove complete replication. Commit destination writes before a checkpoint, retain `source_system`, `source_id`, source-modification time, load time and deletion state, and reconcile totals after each backfill. In production, student progress may stay in an LMS and join CRM only in the analytics layer.
