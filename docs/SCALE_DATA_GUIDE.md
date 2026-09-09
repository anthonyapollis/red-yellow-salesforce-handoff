# Large synthetic dirty dataset

The GitHub Release asset is a synthetic scale-testing dataset. It is intentionally separated from normal Git history.

It contains 12,574,360 rows:

- 2,000,000 customer contacts
- 1,000,000 leads
- 3,000,000 campaign memberships
- 500,000 opportunities
- 1,500,000 programme enquiries
- 400,000 applications
- 300,000 students
- 350,000 enrolments
- 3,500,000 weekly student-progress records

The catalogue itself stays small: 85 programme records, 91 offerings, and 2,184 generated intakes. The additional intakes are fabricated for scale testing and are not catalogue facts.

Every data value is synthetic. The dataset deliberately includes business duplicates under different external IDs, blank emails and phones, casing and whitespace variations, channel and country aliases, misspelled statuses, outlier values, contradictory risk evidence, placeholder marks, and suspicious dates. It does not represent Red & Yellow’s actual size or data quality.

The download contains compressed UTF-8 CSV files in 100,000-row shards, manifest.json with counts/checksums, validation.json, and small preview files. Validate it locally without Salesforce access:

    python tools/validate_scale_data.py --dataset path/to/extracted/scale

Regenerate the same dataset locally:

    python tools/generate_scale_data.py --output path/to/scale --scale 1 --shard-rows 100000

This is not compatible with the small REST seed importer. Use Bulk API 2.0 after target-org storage, API, automation, and duplicate-rule checks. Load parent objects before children. The CSV *_Key columns are transport references, not Salesforce fields; resolve them through parent IDs or external-ID relationship headers. Keep each final API upload near 100 MB.

No Salesforce data has been created by this package.
