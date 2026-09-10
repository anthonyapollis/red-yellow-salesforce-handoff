# GA4, DV360 and Campaign Manager 360 to BigQuery and Microsoft Fabric

**Purpose:** show the client the easiest supported ways to move website and advertising data into the same analytics platform.  
**Status:** implementation guide and demonstration design. Credentials and production connectors are not included.

## The short answer

There are three practical patterns:

1. Easy curated API route: GA4 Data API + DV360/Bid Manager API + Campaign Manager 360 Reports API -> NiFi or a scheduled cloud job -> OneLake or BigQuery -> tested marts -> Power BI.
2. Google-native raw route: GA4 native BigQuery export + DV360 and Campaign Manager 360 transfer/report files -> BigQuery raw -> Dataform/dbt -> Power BI, Looker or Fabric.
3. Fabric-first route: use the APIs for curated metrics, or land BigQuery data through Fabric Data Factory's Google BigQuery connector -> OneLake -> Fabric Warehouse/Lakehouse -> dbt/native SQL -> Power BI.

GA4 does not need BigQuery when the Data API is sufficient. GA4 native raw-event export does require a BigQuery link. DV360 and Campaign Manager 360 do not have one universal direct-to-Fabric connector: use their reporting APIs or an entitled Google Marketing Platform transfer, then land the result in BigQuery/Cloud Storage or through an API job.

## Pattern 1: easiest daily scorecard

Use when: the client needs campaign, source/medium, landing-page, spend, clicks, impressions and conversion KPIs, not every raw event.

GA4 Data API -> NiFi/Cloud Run -> OneLake bronze -> Fabric Warehouse/dbt -> Power BI

DV360 Bid Manager API -> same landing contract

Campaign Manager 360 Reports API -> same landing contract

For each source, store:

- source system and report name;
- extraction run ID and extraction timestamp;
- reporting date and source timezone;
- campaign, advertiser, insertion order, line item and creative keys where available;
- spend, impressions, clicks, sessions, conversions and revenue;
- API page token/report file ID and source status;
- reject count and replay location.

The API job should request a fixed date window, write an immutable dated file, validate the schema, and only then publish the partition. Use a watermark for the last successful date and do not overwrite a successful partition without a run ID.

## Pattern 2: Google-native raw-event analysis

Use when: the client needs event parameters, session paths, user acquisition and raw attribution analysis.

GA4 native export -> BigQuery events_YYYYMMDD -> Dataform/dbt -> BigQuery marts

DV360 can be queried through the Bid Manager API for report outputs. Campaign Manager 360 reports can be created and run through the Reports API. If the Google Marketing Platform account has transfer entitlement, use the available transfer/export mechanism for the required log-level files, then land them in BigQuery or Cloud Storage.

Keep source grains separate:

- GA4 event grain: one event row;
- DV360 report grain: the selected query dimensions and metrics;
- CM360 report grain: the selected report dimensions and metrics;
- CRM grain: one operational object record;
- conversion grain: one attributed conversion event.

Do not join these tables on a person-level identifier by default. Use consented campaign/source/medium/date keys and a documented attribution window.

## Pattern 3: Fabric-first implementation

API jobs or BigQuery -> Fabric Data Factory -> OneLake bronze -> Fabric Warehouse/Lakehouse -> dbt/native SQL -> Power BI

The Fabric BigQuery connector is the simplest bridge when raw Google data already exists in BigQuery. The API route is simpler when only a small curated scorecard is needed. In both cases, land immutable bronze partitions, conform dates and campaign keys once, and reconcile source totals before Power BI refresh.

## Demonstration sequence

1. Create a test GA4 property or use an approved property with a non-production date range.
2. Run a GA4 Data API report for date, sessionSourceMedium, sessionCampaignName, landingPage and sessions.
3. Create a DV360 Bid Manager query for campaign/line-item dimensions and spend, impressions, clicks and conversions.
4. Create a CM360 standard or Floodlight report for campaign, placement and conversion metrics.
5. Save each response as a dated CSV/JSON file with a run manifest.
6. Load the files to BigQuery or OneLake bronze.
7. Run schema, row-count, duplicate-key and date-reconciliation tests.
8. Build a common campaign performance mart and compare the same day and campaign totals in Power BI.
9. Re-run the same date window to prove idempotency and confirm no duplicate rows.
10. Park a deliberately failed file to prove alerting and replay.

## Choosing the route

| Need | Best starting route |
|---|---|
| Fastest proof of concept | Pattern 1, curated APIs |
| Raw GA4 event parameters | Pattern 2, native BigQuery export |
| Existing Power BI and Microsoft governance | Pattern 3, Fabric-first |
| Existing Google Cloud data team | Pattern 2, BigQuery/Dataform-first |
| Lowest data volume and simplest operations | Pattern 1 |
| Cross-channel log-level attribution | BigQuery landing, then choose Fabric or Google marts |

## Controls that must be demonstrated

- OAuth/service-account secrets stored outside source control;
- least-privilege access to GA4, DV360, CM360, BigQuery and Fabric;
- consent and retention rules for analytics identifiers;
- source timezone and currency captured on every report;
- no silent zero for missing fees or unavailable metrics;
- row-count, sum-of-spend, date-window and duplicate reconciliation;
- retry, quarantine and replay for failed extracts;
- model version, feature cutoff and human review for student-risk outputs.

## Official references

- GA4 BigQuery Export: https://support.google.com/analytics/answer/9358801
- GA4 Data API: https://developers.google.com/analytics/devguides/reporting/data/v1
- DV360 API: https://developers.google.com/display-video/api
- DV360 Bid Manager reports: https://developers.google.com/bid-manager/guides/build-reports/create-query
- Campaign Manager 360 Reports API: https://developers.google.com/doubleclick-advertisers/guides/create_reports
- Campaign Manager 360 run reports: https://developers.google.com/doubleclick-advertisers/guides/run_reports
- Fabric BigQuery connector: https://learn.microsoft.com/en-us/fabric/data-factory/connector-google-bigquery-overview
- Google Cloud Dataform: https://docs.cloud.google.com/dataform/docs/overview

This guide describes supported patterns and a demonstration plan. It does not claim that GA4, DV360 or Campaign Manager 360 credentials are configured in the current project.
