# Intentionally dirty data
## Three datasets
1. data/dirty_loadable: PRIMARY Salesforce seed. 253 records across 14 objects. Deliberately inconsistent labels, business duplicates, missing optional data, suspicious fees/durations, suspect but syntactically valid email values, and timeline/risk contradictions. External IDs are unique and foreign keys resolve.
2. data/dirty_raw: the same starting data with additional structural defects for a landing/quarantine exercise. It is NOT accepted by the structural validator and must not be loaded directly.
3. data/catalogue, data/demo and data/reference_clean: unchanged reference inputs. Use these only as evidence or an explicitly selected reference dataset. Screenshots remain untouched.

## What stays dirty during Salesforce import
Keep business duplicates with separate external IDs, misspelled custom statuses, inconsistent case, aliases, missing optional fields, date outliers, price outliers and contradictory progress evidence. Do not clean first: the user asked for dirty Salesforce data.
Salesforce may trim some text and org-specific duplicate/validation rules may reject records; a live preflight alone cannot guarantee preservation. Report target-specific normalisation/rejections rather than bypassing rules.

## Structural constraints
A lookup containing a nonexistent Salesforce ID cannot serve as a normal linked record. Invalid numeric/date values and conflicting unique external IDs likewise do not belong in the loadable tier.
Those cases are preserved in dirty_raw. The raw tier is a local staging/quarantine exercise, not a new Salesforce custom-object schema.

## Repeatability and evidence
RY-DIRTY-* external IDs isolate this exercise from reference imports and make reruns idempotent. KEY_MAP.csv connects base records to their reference keys; added business duplicates refer to originals in ISSUE_REGISTER.csv.
81 mutation events are documented: 66 in the loadable tier and 15 additional raw-tier defects. Counts are mutation events, not distinct faulty rows.
ISSUE_REGISTER.csv contains an evaluator answer key, baseline values, dirty values and expected handling. Do not give this to a blind detection exercise until assessment.
Unknowns already present in the screenshots are not injected errors and must not be fabricated.
All dirty changes are synthetic. They do not reflect the institution's actual internal data quality.

## Commands
    python tools/import_salesforce.py --include-demo
    python tools/test_importer.py
    python tools/test_dirty_data.py
The first command validates transport structure only. It must pass while semantic dirt remains.
For actual insertion, follow docs/IMPORT_GUIDE.md and include --include-demo to load the full exercise.
