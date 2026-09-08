# Red & Yellow — CRM Analytics Platform

Built against the **Data Analytics Engineer (CRM Integration)** role at Red & Yellow
Creative School of Business. The advert names six deliverables; this is the working
answer to all six.

| Advert requirement | Where it lives | State |
|---|---|---|
| Data catalogue (dbt or similar) | `dbt_redandyellow/` + `dbt docs generate` | ✅ built, 74/74 green |
| ERDs for internal systems incl. CRM | `erds/03_salesforce_canonical.mmd` | ✅ from the original handoff |
| ETL/ELT pipelines, preferably Apache NiFi | `nifi/build_flow.py` | ✅ built in a live NiFi |
| Salesforce CRM extract / transform / analyse | `salesforce/`, `tools/import_salesforce.py` | ✅ load built, org not authed |
| Power BI dashboards | `reporting/` marts + workbook | ✅ marts + Excel; PBIX pending |
| Data quality and accuracy | `models/quality/`, 51 dbt tests | ✅ scored against ground truth |

---

## Run it

```bash
python run_all.py
```

Roughly 12 minutes end to end. Needs no cloud credentials — it generates the data,
builds and tests the warehouse on DuckDB, writes the catalogue, the Excel workbook,
the ebook, and the Salesforce load.

```bash
python run_all.py --scale dev          # ~1M rows instead of 9.4M
python run_all.py --with-nifi --nifi-user <uuid> --nifi-password <pw>
```

## Architecture

```
Salesforce CRM ──NiFi──▶ OneLake bronze ──▶ Fabric Lakehouse ──dbt──▶ marts ──▶ Power BI
   (thousands)                                  (9.4M rows)          tested       reports
```

**Salesforce holds thousands; the warehouse holds millions.** Salesforce charges
storage per record at ~2 KB, so a Developer org holds about 10,000 records in
total. Loading nine million rows into the CRM is not a scaling problem to solve —
it is not possible. The CRM gets a referentially complete operational slice; the
warehouse gets the volume, the history and the quality work.

## What is real and what is not

**Real:** the programme catalogue — 83 programmes, 89 offerings, 47 dated intakes
and their advertised fees, transcribed from the public Red & Yellow site on
2026-09-08 (see `docs/DATA_NOTES.md`).

**Synthetic:** every person, campaign, application, enrolment and progress record.
Names are drawn from a South African distribution. Nothing here is an export from
Red & Yellow's systems.

## Data quality is measured, not asserted

Defects are injected at known rates and written to a ground-truth manifest at
`warehouse/_truth/defects.json`. The pipeline's detection is scored against it.

| Defect | Injected | Detected | Recall |
|---|---|---|---|
| Duplicate humans | 28,856 | 28,052 | **0.97** |
| Missing attendance | 41,872 | 41,872 | 1.00 |
| Duplicate campaign membership | 37,440 | 39,931 | 1.07 |
| Date inversions | 3,863 | 2,912 | 0.75 |

The remaining 3% of duplicates are records where both email and phone were dropped
at source — genuinely unmatchable.

### Three decisions worth defending

**De-duplication needs two keys.** Keying on email alone gives 0.52 recall, because
someone re-submitting a web form repeats their email while someone phoning in leaves
none — and those two records can never share a single key. Keying on name collapses
thousands of legitimate `Thabo Nkosi`s together (that version reported 682k
duplicates against 29k real ones). The working model anchors on email and on
phone-plus-surname independently, then propagates once.

**Campaign spend is aggregated before it is joined.** Join spend to a fact table
first and every campaign's cost is multiplied by its downstream row count. A dbt
test compares total spend in the fact against the dimension and fails the build if
they diverge.

**"Enquire for price" stays null.** Zero is a price. Substituting it would drag every
average fee downward and make the unpriced courses look free. A dbt test enforces it.

## Layout

```
generator/          data generator + dbt project scaffold
dbt_redandyellow/   13 staging, 8 mart, 2 quality models; 51 tests
nifi/               builds the Salesforce→OneLake flow via the NiFi REST API
fabric/             workspace/lakehouse provisioning + OneLake upload
salesforce/         cuts the CRM slice; force-app metadata from the handoff
reporting/          Excel workbook + ebook builders
warehouse/          generated data + DuckDB (gitignored)
```

## Credentialed stages

Not run by `run_all.py`, by design:

```bash
python fabric/deploy_fabric.py --check      # auth + capacity, writes nothing
python fabric/deploy_fabric.py              # provision + upload bronze

python tools/import_salesforce.py --preflight
python tools/import_salesforce.py --apply \
  --expected-host <org>.my.salesforce.com \
  --opportunity-stage "<a real StageName in that org>"
```

The NiFi flow's parameter context ships with empty sensitive parameters
(`sf.client.id`, `sf.client.secret`, `fabric.sp.*`). Processors stay invalid until
those are supplied — which is the intended state for a repo.

## Constraints carried from the original handoff

- Never write `IsConverted` or `ConvertedContactId`.
- Never import `data/legacy/` or `catalogue_observations.csv` as Salesforce objects.
- No emails, campaigns or outbound journeys.
- Do not merge qualification identities or override existing org validation rules.
- Map to existing Education Cloud / EDA objects where the target org already has them.

## Cost

A Fabric trial capacity does not warn or stop on its own. Delete the workspace when
the project is done. The whole platform rebuilds locally on DuckDB in ~12 minutes,
so losing the Fabric workspace costs nothing irreplaceable.
