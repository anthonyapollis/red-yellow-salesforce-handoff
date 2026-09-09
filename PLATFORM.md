# Red & Yellow — CRM Analytics Platform

Built against the **Data Analytics Engineer (CRM Integration)** role at Red & Yellow
Creative School of Business. The advert names six deliverables; this is the working
answer to all six.

| Advert requirement | Where it lives | State |
|---|---|---|
| Data catalogue (dbt or similar) | `dbt_redandyellow/` + `dbt docs generate` | ✅ built and tested |
| ERDs for internal systems incl. CRM | `erds/03_salesforce_canonical.mmd` | ✅ from the original handoff |
| ETL/ELT pipelines, preferably Apache NiFi | `nifi/build_flow.py` | ✅ built in a live NiFi |
| Salesforce CRM extract / transform / analyse | `salesforce/`, `tools/import_salesforce.py` | ✅ loaded into a live org, extracted back |
| Power BI dashboards | `powerbi/RedAndYellow.pbip` + `reporting/` | ✅ built, model and report generated |
| Data quality and accuracy | `models/quality/` + dbt tests | ✅ scored against ground truth |

Every number below is written by `reporting/update_platform_md.py`, read out of the
artefacts themselves. If a count here is wrong, the artefact is wrong — not the prose.

<!-- FACTS:BEGIN -->

| What | Built | Verified by |
|---|---|---|
| Medallion warehouse | 13 bronze, 13 silver, 8 gold, 2 quality | `dbt build` — 87/87 pass (51 data tests) |
| Generated data | 11,512,875 rows | ground-truth manifest at `warehouse/_truth/defects.json` |
| Power BI report | 6 pages, 72 visuals | every field reference checked against the model at build time |
| Semantic model | 24 tables, 52 measures, 23 relationships | loaded through a tabular session |
| Salesforce | 1,091 records across 4 objects | `verify_org_counts.py` reconciles the org against the loader |
| Ebook | 21-page PDF | contents text extracted back out of the finished PDF |
| Workbook | 10 sheets | sheet count read from the workbook |
| ML — lead to enrolment propensity | AUC 0.667, top-decile lift 2.17x | held-out split by time, base rate 5.2% |
| ML — withdrawal risk from weeks 1-4 | AUC 0.621, top-decile lift 1.67x | held-out split by time, base rate 12.5% |
<!-- FACTS:END -->

---

## Run it

```bash
python run_all.py
```

Roughly 12 minutes end to end. Needs no cloud credentials — it generates the data,
builds and tests the warehouse on DuckDB, writes the catalogue, the Excel workbook,
the ebook, and the Salesforce load.

```bash
python run_all.py --scale dev          # ~1M rows instead of 11.5M
python run_all.py --with-nifi --nifi-user <uuid> --nifi-password <pw>
```

## Navigating the NiFi instance

NiFi has one root per instance; a project is a top-level process group and its
stages are nested groups. To find anything by hand, use the **search box** in
the top toolbar - it matches process groups, processors, controller services,
parameters and labels, and every hit names the group it lives in. Double-click a
group to enter it; the breadcrumb bottom-left is the path back up.

`python nifi/show_tree.py --user <u> --password <p>` prints the whole hierarchy
with component counts; `nifi/FLOW_MAP.md` is the checked-in copy.

## Architecture

```
Salesforce CRM ──NiFi──▶ OneLake bronze ──▶ Fabric Lakehouse ──dbt──▶ marts ──▶ Power BI
   (thousands)                                  (11.5M rows)          tested       reports
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

<!-- DEFECTS:BEGIN -->

| Defect | Injected | Detected | Recall |
|---|---|---|---|
| Duplicate humans | 30,277 | 29,473 | **0.97** |
| Missing attendance | 76,341 | 76,341 | **1.00** |
| Duplicate campaign membership | 37,440 | 39,850 | **1.06** |
| Date inversions | 5,118 | 5,228 | **1.02** |
<!-- DEFECTS:END -->

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
dbt_redandyellow/   medallion warehouse: bronze / silver / gold / quality
nifi/               builds the Salesforce→OneLake flow via the NiFi REST API
fabric/             workspace/lakehouse provisioning + OneLake upload
salesforce/         cuts the CRM slice; force-app metadata from the handoff
reporting/          Excel workbook + ebook builders
powerbi/            PBIP - semantic model (TMDL) + generated report
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
