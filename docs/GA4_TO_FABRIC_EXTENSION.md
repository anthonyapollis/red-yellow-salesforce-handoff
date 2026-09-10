# GA4 to Fabric extension

## Status

**Built but unverified.** nifi/build_ga4_flow.py scaffolds the GA4 Data API to OneLake bronze route, but no GA4 credential, successful extract, source table, or metric exists yet. No current report result should be read as GA4-derived.

## The BigQuery question
Official references: [GA4 Data API](https://developers.google.com/analytics/devguides/reporting/data/v1) and [GA4 BigQuery Export](https://support.google.com/analytics/answer/9823238).


GA4 has two valid export patterns:

1. **Data API route - BigQuery is not required.** The GA4 Data API runReport endpoint returns a table of requested dimensions and metrics. It is the right fit for scheduled campaign, source/medium, landing-page and key-event summaries. NiFi can call the API and write the response directly to OneLake bronze.
2. **Native BigQuery export - BigQuery is required for this route.** GA4 writes richer event-level tables such as events_YYYYMMDD (and optional intraday tables) into a linked BigQuery dataset. This is the right fit when event parameters, session paths or raw event-level analysis are required. The BigQuery dataset can then be replicated to OneLake or queried in Google Cloud.

The choice is about data grain: use the Data API for aggregated reporting without BigQuery; use native BigQuery export for raw event analysis. Both routes can feed the same dated bronze contract and downstream campaign mart.

## Recommended route

                         -> GA4 Data API (aggregated reports) ---------+
GA4 property             |                                             v
                         -> native BigQuery export (raw events) -> OneLake Files/bronze/ga4/event_date=YYYY-MM-DD/
                                                                     -> Fabric staging + dbt conformance
                                                                     -> gold marketing-attribution mart
                                                                     -> Power BI campaign reach, traffic and assisted-conversion views

Use the GA4 Data API for aggregated daily campaign, source/medium, landing-page and key-event measures. The current GA4 Data API name for the count of configured key events is keyEvents. Use a BigQuery export when event-level analysis is required and the organisation has approved the privacy, retention and cost implications.

## BigQuery-compatible dbt target

dbt_redandyellow/profiles.yml includes a bigquery target that uses OAuth / Application Default Credentials and no repository secret. The model graph uses adapter-dispatched date, regex and phone-cleaning SQL so the same business models can compile on DuckDB, Fabric and BigQuery.

From dbt_redandyellow:

    python -m pip install dbt-bigquery
    gcloud auth application-default login
    export BIGQUERY_PROJECT=your-gcp-project
    export BIGQUERY_DATASET=ry_analytics
    export BIGQUERY_LOCATION=africa-south1
    dbt debug --profiles-dir . --target bigquery
    dbt build --profiles-dir . --target bigquery

The target expects Salesforce-shaped source tables in BIGQUERY_DATASET.raw_salesforce. Load those tables first, or add BigQuery external tables over the landed files. No cloud run was claimed in this repository because no project, dataset or credential was supplied.

## Authentication boundary

Google service accounts obtain access tokens by signing a JWT assertion; a private key is not an OAuth client secret. The NiFi builder therefore expects a short-lived ga4.access.token from a secure token broker using an official Google authentication library. Do not store a service-account private key in the NiFi flow or repository.

## Controls before delivery

- Land immutable daily partitions and retain source extraction timestamps.
- Reconcile daily GA4 totals against the source property before publishing gold models.
- Join on campaign, source/medium and date at first; do not join GA client or user identifiers into Salesforce.
- Treat consent mode, retention and regional privacy obligations as source-system controls, not downstream cleanup.
- Add freshness, accepted-value and campaign-key coverage tests before Power BI consumes the mart.

## Relationship to the current platform

The verified flow is Salesforce -> NiFi -> OneLake bronze -> Fabric / dbt -> Power BI. The GA4 NiFi builder is a separate parallel acquisition route and must produce reconciled bronze data, a tested source model and a successful end-to-end run before it can influence campaign reporting.
