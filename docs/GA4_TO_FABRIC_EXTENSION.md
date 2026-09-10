# GA4 to Fabric extension

## Status

**Proposed, not implemented.** The platform contains no GA4 credential, API connector, source table, or metric. No current report result should be read as GA4-derived.

## Recommended route

```text
GA4 property
  -> scheduled GA4 Data API extract or BigQuery export
  -> OneLake Files/bronze/ga4/event_date=YYYY-MM-DD/
  -> Fabric staging + dbt conformance
  -> gold marketing-attribution mart
  -> Power BI campaign reach, traffic and assisted-conversion views
```

Use the GA4 Data API for aggregated daily campaign, source/medium, landing-page and conversion measures. Use a BigQuery export only when event-level analysis is required and the organisation has approved the privacy, retention and cost implications.

## Controls before delivery

- Land immutable daily partitions and retain source extraction timestamps.
- Reconcile daily GA4 totals against the source property before publishing gold models.
- Join on campaign, source/medium and date at first; do not join GA client or user identifiers into Salesforce.
- Treat consent mode, retention and regional privacy obligations as source-system controls, not downstream cleanup.
- Add freshness, accepted-value and campaign-key coverage tests before Power BI consumes the mart.

## Relationship to the current platform

The implemented flow is Salesforce -> NiFi -> OneLake bronze -> Fabric / dbt -> Power BI. GA4 would become a separate, parallel marketing source that meets the same bronze and conformance standards before it can influence campaign reporting.
