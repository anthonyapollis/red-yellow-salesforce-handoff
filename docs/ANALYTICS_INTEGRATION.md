# Analytics integration
Salesforce and student systems -> NiFi -> raw database -> dbt transformations/tests/docs -> reporting tables -> Power BI.
Use initial paginated REST/Bulk extracts and CDC or Replication API for supported objects to detect updates/deletes. Commit destination writes before checkpoints; reconcile/backfill expired history. A simple SystemModstamp filter is not a complete reliable replication strategy.
Retain source system, source ID, source modification time, load time and deletion status.
In an actual institution, student progress may stay in the LMS and only join CRM in analytics. This scaffold does not assert all entities exist in Salesforce.
No executable NiFi flow/dbt project/database-specific DDL is supplied: the database and real source schemas are unknown.
