# GA4 to Fabric extension

## Status

**Built but unverified.** `nifi/build_ga4_flow.py` scaffolds the GA4 Data API to OneLake bronze route, but no GA4 credential, successful extract, source table, or metric exists yet. No current report result should be read as GA4-derived.

## Recommended route

```text
GA4 property
  -> scheduled GA4 Data API extract or BigQuery export
  -> OneLake Files/bronze/ga4/event_date=YYYY-MM-DD/
  -> Fabric staging + dbt conformance
  -> gold marketing-attribution mart
  -> Power BI campaign reach, traffic and assisted-conversion views
```

Use the GA4 Data API for aggregated daily campaign, source/medium, landing-page and key-event measures. The current GA4 Data API name for the count of configured key events is `keyEvents`. Use a BigQuery export only when event-level analysis is required and the organisation has approved the privacy, retention and cost implications.

## Authentication boundary

Google service accounts obtain access tokens by signing a JWT assertion; a private key is not an OAuth client secret. The NiFi builder therefore expects a short-lived `ga4.access.token` from a secure token broker using an official Google authentication library. Do not store a service-account private key in the NiFi flow or repository.

## Controls before delivery

- Land immutable daily partitions and retain source extraction timestamps.
- Reconcile daily GA4 totals against the source property before publishing gold models.
- Join on campaign, source/medium and date at first; do not join GA client or user identifiers into Salesforce.
- Treat consent mode, retention and regional privacy obligations as source-system controls, not downstream cleanup.
- Add freshness, accepted-value and campaign-key coverage tests before Power BI consumes the mart.

## Relationship to the current platform

The verified flow is Salesforce -> NiFi -> OneLake bronze -> Fabric / dbt -> Power BI. The GA4 NiFi builder is a separate parallel acquisition route and must produce reconciled bronze data, a tested source model and a successful end-to-end run before it can influence campaign reporting.
