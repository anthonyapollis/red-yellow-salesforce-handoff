# Red & Yellow - Salesforce ERDs and data handoff
Prepared from the job description and 17 user screenshots (8 September 2026). This is a proposed model, not an internal company export.

## Contents
- START_HERE_CLAUDE.md: Claude handoff.
- erds/: canonical Salesforce ERD, two archived ERDs, analytics pipeline, SVG overview and HTML viewer.
- data/catalogue/: 89 observed listings, 83 conservative programme identities, 89 offerings and 47 dated intakes.
- data/demo/: 22 fictional marketing, CRM, admissions and student records.
- data/legacy/: first fictional example and earlier example-ID mappings, excluded from imports.
- salesforce/: Salesforce DX metadata, 8 custom objects, extensions to 6 standard objects, schema, field dictionary, permission set and import plan.
- tools/import_salesforce.py: standard-library Python importer, offline validation by default; --apply enables writes.
- tools/test_importer.py: focused local tests.
- sources/: screenshot provenance and source images.
- docs/: assumptions, business rules, import guide and references.
- docs/DBT_EVIDENCE.md: reproducible dbt run evidence, delivery-mode check and target limitations.
- validation/: local checks and manifest.

## Start
Give Claude this ZIP and ask it to follow START_HERE_CLAUDE.md in your intended Salesforce org.
After extracting, validate with:
    python tools/import_salesforce.py --include-demo
    python tools/test_importer.py
Read docs/IMPORT_GUIDE.md for deployment and write commands.

## Status
Salesforce Base Edition org verified and modified through the REST API. The reduced standard-object slice contains 25 Accounts, 408 Contacts, 408 Leads and 250 Opportunities (1,091 tagged records), reconciled against run_results/import_log.json. Custom-object deployment remains blocked by the edition entitlement.
Screenshot figures are displayed catalogue observations, not independently verified current prices or accreditation conclusions. Unknown values remain blank.
