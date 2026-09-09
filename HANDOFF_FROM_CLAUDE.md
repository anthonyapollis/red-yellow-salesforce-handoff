# Handoff: what Claude built on top of the Codex package

Branch `analytics-platform`. The original handoff supplied the modelling half —
ERDs, Salesforce object metadata, an import plan and an importer. This adds the
three deliverables the job advert is actually named after (ETL, a tested
warehouse, reporting), gets data into a real Salesforce org, and extracts it
back out through the API.

---

## What changed in the original files

`tools/import_salesforce.py` had three defects that stopped it working against a
live org. All three are fixed in place, minimally:

1. **It required `SF_INSTANCE_URL` + `SF_ACCESS_TOKEN`.** It now falls back to
   `salesforce/sf_auth.py`, an OAuth client-credentials grant, so it shares auth
   with everything else here. Still nothing stored in the repo.
2. **It sent the external ID in the upsert body.** Salesforce rejects that with
   `INVALID_FIELD: "should not be specified in the sobject data"` when the same
   field is the key in the URL. This would have failed on any org. One line:
   `body.pop(p["external_id"], None)`.
3. **It had no way to run a different plan.** Added `--plan`, so the generated
   CRM slice can be loaded without overwriting `salesforce/import_plan.json`.

Also added `Sforce-Duplicate-Rule-Header: allowSave=true`. Salesforce's
`Standard_Lead_Duplicate_Rule` blocks leads that fuzzy-match existing contacts
at 100% confidence — which this dataset triggers legitimately, because converted
leads and their contacts are both loaded. The rule reports `allowSave: true`, so
the documented header lets the record save while the rule still records the
match. Deleting the rule would have hidden a real signal.

## Findings that constrain the design

**The trial org is `Base Edition` (Starter Suite) and permits zero custom
objects.** All 8 RY objects were rejected with "reached maximum number of custom
objects" while only 2 custom objects existed (both system `Knowledge__ka/kav`)
and 10.6 GB of storage was free. It is an edition entitlement, not a quota.
`salesforce/check_org.py` now reports this in one API call and returns
GO / PARTIAL / NO-GO.

**Fields deployed without field-level security are present but invisible.**
`describe()` omits them and the upsert then fails claiming the external ID is
not unique — because the API cannot see the field it is keying on. The
permission set is trimmed to the deployed fields and assigned over REST.

**The Metadata API suffix for a permission set is `.permissionset`,** not
`.permissionSet`. The wrong casing reports the file as missing from the zip.

**`testLevel: NoTestRun` is rejected by production orgs,** and a trial counts as
production. Omitted; the package contains no Apex.

## What was actually loaded

Base Edition allows the 18 custom fields on standard objects, so the load is
Account, Contact, Lead and Opportunity — 1,074 records, upserted on
`RY_External_ID__c`. `Campaign` is not createable on this edition, so campaigns
and campaign members are excluded. `salesforce/verify_org_counts.py` reconciles
what the loader claims against what the org holds.

The education entities — programmes, offerings, intakes, applications, students,
enrolments, progress — stay in the warehouse. That split is deliberate and
matches the advert: Salesforce is the operational CRM, the warehouse holds the
volume, the history and the quality work.

## New: the extraction the role is about

`salesforce/extract_to_warehouse.py` pulls those objects back out via SOQL over
REST into `warehouse/salesforce_raw/`:

- pagination via `nextRecordsUrl`, so the 2,000-record page limit is handled
- incremental on `SystemModstamp` with a persisted watermark — first run full,
  second run returns zero rows
- deletion capture via `queryAll`
- source system / source id / source update time / extraction time on every row

## The rest of the platform

| | |
|---|---|
| `generator/` | 11.5M rows, 2.6M people, anchored to the real 83/89/47 catalogue. Defects injected at recorded rates into a ground-truth manifest so detection is scored as recall, not asserted |
| `dbt_redandyellow/` | 13 staging, 8 mart, 2 quality models; 51 data tests, all passing. Cleansing macros dispatch per adapter so the same models run on DuckDB and Fabric |
| `nifi/` | Builds the Salesforce→OneLake flow against a live NiFi over its REST API, introspecting real property descriptors rather than guessing keys |
| `fabric/` | Workspace and lakehouse provisioning plus OneLake upload |
| `powerbi/` | PBIP semantic model: 24 tables, 52 measures, 23 relationships, 6 pages, 72 visuals |
| `reporting/` | Excel workbook and the data-story ebook, both built from live queries |

`python run_all.py` rebuilds everything local in about 15 minutes.

## Three modelling decisions worth keeping

**De-duplication needs two match keys.** Email alone gives 0.52 recall — someone
re-submitting a web form repeats their email, someone phoning in has none, and
those two records can never share one key. Name-based keying gave 682k false
duplicates against 29k real ones, because "Thabo Nkosi" recurs legitimately
thousands of times in a realistic SA name distribution. Anchoring on email and
on phone-plus-surname independently, then propagating once, gives 0.97.

**Campaign spend is aggregated to campaign grain before it meets enrolments.**
Join it to a fact table first and every campaign's cost is multiplied by its
downstream row count. A dbt test compares the two totals and fails the build.

**"Enquire for price" stays null.** Zero is a price; substituting it would drag
every average fee down and make the unpriced courses look free. A dbt test
enforces it.

## Open items

- Fabric upload has not run — `az login` needs completing on the tenant.
- The Power BI report's 72 visuals are unverified in Desktop; the semantic model
  is verified by loading it through a tabular session and checking all 65 field
  references against the model.
- An earlier CRM slice was sampled with `ORDER BY created_date DESC`, which
  surfaced injected duplicates rather than the population (29.4% null-email
  against a warehouse rate of 4.37%). Sampling now uses a hash of the key.
  `salesforce/cleanup_stale.py` removes the first batch; it reports by default
  and deletes only with `--apply`.


## Power BI source of truth

Run python powerbi/build_report.py while Power BI Desktop is closed. It writes the generated report.json and a version 1.0 definition.pbir, then checks every visual projection against the TMDL semantic model. Power BI Desktop upgrades the project to PBIR 4.0 when it saves; that upgrade is a presentation copy, not a second source of truth. Re-run the generator before opening Desktop to see regenerated pages. Any future hand-authored PBIR 4.0 work needs its own v4 generator rather than a manual edit alongside report.json.
