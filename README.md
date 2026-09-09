# Red & Yellow - intentionally dirty Salesforce handoff
The primary dataset is deliberately dirty, as requested. Claude should read START_HERE_CLAUDE.md and preserve the intended defects during Salesforce insertion.

- data/dirty_loadable/: 253 structurally valid but semantically dirty records, including business duplicates, inconsistent formatting, missing values, price/date outliers and status errors.
- data/dirty_raw/: additional invalid dates/numbers, orphan keys, malformed email values and conflicting IDs for quarantine/cleanup exercises.
- data/quality/: issue register and reference key mapping; evaluator answer key.
- data/catalogue/ and data/demo/: original reference inputs; not the default import.
- erds/: all earlier ERDs, canonical Salesforce schema, pipeline and overview.
- salesforce/: metadata and default dirty import plan.
- sources/: all 17 original screenshots, unchanged.
- downloads/: complete updated ZIP in GitHub (not nested inside the ZIP itself).

There are 66 loadable mutation events and 15 additional raw-tier mutation events, all deliberately injected. They are not evidence of real problems in Red & Yellow's systems.

    python tools/import_salesforce.py --include-demo
    python tools/test_importer.py
    python tools/test_dirty_data.py

Local structural checks pass for dirty_loadable and intentionally fail for dirty_raw. No live Salesforce import has been performed. Org-specific rules may reject some intended duplicates; report those without silently cleaning or disabling rules.

## Large synthetic data

A 12.6-million-row synthetic dirty dataset is published as a GitHub Release asset, not in normal Git history. See docs/SCALE_DATA_GUIDE.md.

