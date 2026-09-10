# Google Cloud and Microsoft Fabric platform options

**Purpose:** give the client a like-for-like choice for the Red & Yellow analytics project.  
**Status:** the Salesforce extract, warehouse model, Power BI report, dbt evidence and SEO crawl are implemented in this repository. The two cloud target architectures below are decision options; neither is presented as a completed production deployment.

## Shared requirements

Both options must support the same business outcomes:

- reconcile the operational Salesforce slice with warehouse history;
- ingest consented website and GA4 campaign data with source, medium, campaign and date keys;
- preserve catalogue fee status, including Enquire for price as null rather than zero;
- transform programme, offering, application, enrolment and weekly progress facts with tested lineage;
- rank course demand and withdrawal risk while keeping ML actions human-reviewed;
- publish Power BI-ready marts, data-quality exceptions, run history and replayable failures;
- separate synthetic demonstration data from live CRM records and protect personal identifiers.

## Option A - Google Cloud first

**Reference flow**

Website / GA4 -> native BigQuery export or GA4 Data API -> BigQuery raw -> Dataform tested models -> BigQuery marts -> Power BI or Looker

Salesforce and NiFi can land extracts in Cloud Storage or BigQuery. BigQuery is the natural centre when the client needs native GA4 raw-event tables, session paths and event-parameter analysis. Dataform provides versioned, tested and scheduled SQL transformations in BigQuery. Keep the current dbt model logic portable as standard SQL where practical.

**Strengths**

- closest fit to GA4 native raw-event export and Google campaign reporting;
- serverless warehouse and Dataform workflow for a Google-first data team;
- straightforward path to Looker if the client later prefers Google-native BI;
- useful when the existing identity, security and billing estate is already Google Cloud.

**Trade-offs**

- Power BI remains a cross-cloud consumer unless the client moves BI;
- Salesforce and Microsoft operational systems need cross-cloud identity and network controls;
- BigQuery scan/storage and Dataform workflow costs must be monitored by partition and query budget;
- Fabric-specific OneLake and Microsoft governance capabilities are not the centre of gravity.

## Option B - Microsoft Fabric first

**Reference flow**

Website / GA4 Data API -> NiFi -> OneLake bronze -> Fabric Warehouse/Lakehouse -> dbt or native SQL -> Power BI

If raw GA4 export is required, use GA4 -> BigQuery -> Fabric Data Factory BigQuery connector -> OneLake as a separate source contract. Salesforce extraction, OneLake bronze, Fabric transformations and Power BI then remain in one Microsoft analytics estate.

**Strengths**

- shortest path to the existing Power BI report and Microsoft identity/governance;
- OneLake gives one governed landing layer for Salesforce, website and GA4 feeds;
- Fabric Data Factory supports BigQuery as a source when Google raw events are required;
- good fit when the client already owns Microsoft capacity and operates Power BI.

**Trade-offs**

- Fabric capacity, Warehouse SQL compatibility and workload sizing need active governance;
- native GA4 raw-event export still introduces BigQuery and cross-cloud movement;
- the Data API route is simpler but returns curated reports rather than every raw event;
- dbt/Fabric SQL compatibility must be completed and rerun before claiming a production gold layer.

## Decision matrix

| Decision factor | Favour Google Cloud | Favour Microsoft Fabric |
|---|---|---|
| Raw GA4 event and session analysis | Native BigQuery export is the primary need. | BigQuery export is still acceptable, with Fabric as the governed downstream layer. |
| Existing BI | Looker or Google-native BI is preferred. | Power BI is the strategic reporting surface. |
| Existing identity and governance | Google Cloud IAM, billing and data team are established. | Microsoft Entra, Purview, Power BI and Fabric capacity are established. |
| Operating model | Google-first SQL/Dataform team. | Microsoft-first data engineering and Power BI team. |
| Cross-cloud tolerance | Minimise Azure/Microsoft dependencies. | Accept BigQuery only when raw GA4 capability justifies it. |
| Fastest route for this project | Rebuild the report layer around BigQuery marts. | Reuse the validated OneLake, dbt and Power BI design already shown here. |

## Recommended client decision process

1. Confirm whether raw GA4 event parameters and session paths are mandatory. If yes, budget for BigQuery in either option.
2. Confirm the strategic BI and identity estate. If Power BI and Microsoft governance are already standard, run a Fabric pilot first; if Google Cloud is the established analytics estate, run a BigQuery/Dataform pilot.
3. Run the same 30-day acceptance pack on both pilots: Salesforce reconciliation, GA4 row-count and date reconciliation, dbt/Dataform tests, course-risk output, Power BI refresh, cost guardrails and replayed failure.
4. Choose the platform with the lower total operating friction and equal evidence quality. Keep the source contracts and semantic model portable so the client is not locked into a single cloud.

## Boundary and evidence

The current project proves the Salesforce standard-object slice, OneLake bronze connectivity, DuckDB/dbt model, Power BI report, ML analysis and website SEO findings. It does not claim that Google Cloud or Fabric silver/gold production transformations are live. The client should select the target after the two pilot acceptance packs are compared.
