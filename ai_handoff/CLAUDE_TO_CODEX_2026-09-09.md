# Claude → Codex, 2026-09-09

Anthony has asked you to review quality on the report, Power BI, ebook and
Excel. This is the honest state: what is built and verified, what is weak, and
what I would look at first if I were you. Branch `analytics-platform`.

Everything is reproducible: `python run_all.py` rebuilds the local half in about
15 minutes. Nothing below needs my session to be alive.

---

## 1. What is built and verified

| Thing | State | How it was verified |
|---|---|---|
| Data generator | 11.5M rows, 2.6M people | Row counts + ground-truth defect manifest |
| Medallion warehouse | 13 bronze / 13 silver / 8 gold / 2 quality | `dbt build` — **87/87 pass** |
| dbt catalogue | `dbt docs generate` | catalog.json + manifest.json present |
| NiFi flow | Live, project + 2 stage groups, ports | Read back from the NiFi REST API |
| Salesforce | 1,091 records upserted, 4 objects | `verify_org_counts.py` reconciles org vs loader |
| SF → warehouse extract | 4 tables, incremental, deletions captured | Second run returns 0 rows; live counts match |
| Fabric | `WS_RedAndYellow`, lakehouse, 242 MB bronze | OneLake listed back, not trusted from the upload |
| ML | 2 models | AUC 0.667 / 0.621, lift 2.17x / 1.67x |
| Ebook | 21-page PDF, populated TOC | Text extracted back out of the finished PDF |
| Excel | 10 sheets | Sheet count read from the workbook |
| Power BI | 24 tables, 23 relationships, 6 pages, 72 visuals | Model loaded via tabular ConnectFolder; 93 field refs checked |

---

## 2. Where the quality actually is weak

Be sceptical of these. I am.

### 2.1 The Power BI report is generated, never design-reviewed

Every visual is placed by coordinates in `powerbi/build_report.py`. I have opened
it in Desktop exactly once and Anthony has sent screenshots twice. Known or
suspected problems:

- **Cards clipped.** Anthony's screenshots showed the category label repeating
  under the value ("Applications" twice) and the value cut off. The theme now
  sets `categoryLabels.show=false` and a 28pt callout, but I have not seen the
  result rendered.
- **Layout is untested at other zoom levels.** Positions are absolute against a
  1280x720 canvas.
- **"At-risk rate by programme" was flat** across every programme. That was a
  data problem, since fixed — but check the chart is now informative rather than
  just no longer flat.
- Titles, spacing and grouping have had no editorial pass.

### 2.2 Desktop silently upgrades the report format, and that ate five rebuilds

This is the trap worth knowing about. Opening the `.pbip` and saving makes
Desktop:

1. write `definition/pages/<section>/visuals/<visual>.json` (PBIR 4.0),
2. set `definition.pbir` to `"version": "4.0"`,
3. **delete `report.json`**, and
4. carry `StaticResources/` away with it — so the registered theme vanishes and
   everything renders in Power BI's default blue.

I regenerated `report.json` five times without noticing that nothing read it any
more. `build_report.py` now deletes `definition/`, `.pbi/` and `.platform`,
re-asserts `definition.pbir` at version 1.0, and re-writes the theme every run.

**This is fragile.** The moment Anthony saves in Desktop it upgrades again. The
durable fix is to generate the PBIR 4.0 folder format natively instead of
legacy `report.json`. I did not do that. If you take one thing from this
handoff, take that.

### 2.3 The ebook figures are rendered output, not UI screenshots

Anthony asked specifically for real NiFi and Fabric screenshots. What is in
there now are terminal-styled renders of live API output — genuine evidence, but
not what he asked for. I could not capture the real thing: Claude-in-Chrome is
not connected, browsers can only be granted read-only screen access, and Windows
will not let a background process bring a window forward.

`build_ebook.py` already embeds anything dropped into `ebook/screenshots/`,
captioned from the filename (`01_NiFi_flow_canvas.png` → "NiFi flow canvas").
If you can capture them, that gap closes with one rebuild.

### 2.4 The ML is honest but the data is mine

The models score AUC 0.667 and 0.621 — believable, not impressive, which is
correct for human decisions with this much unexplained variance. But the
structure they learn is structure **I injected** into the generator. It
demonstrates method: time-based splits, decision-time features only, scored
against a base rate, lift as the operational metric. It is not a finding about
Red & Yellow, and the ebook says so.

Worth checking: whether the latent-propensity design leaks. `_propensity` flows
lead → contact → opportunity → application, and `_engagement` drives both
attendance and withdrawal. I drop those columns before writing the raw tables,
but satisfy yourself the features genuinely precede the outcome.

### 2.5 Half the stack has never run where it is supposed to

- **dbt runs on DuckDB.** The `fabric` target in `profiles.yml` has never been
  executed. The adapter-dispatched cleansing macros have Fabric branches that
  have never been run against Fabric.
- **Fabric holds bronze only.** No silver, no gold, no Delta tables, no
  notebook run. The medallion is real in dbt and only bronze-deep in OneLake.
- **Salesforce is Base Edition**, which permits zero custom objects, so only
  Account / Contact / Lead / Opportunity are loaded. The education entities live
  in the warehouse alone. `check_org.py` reports GO/PARTIAL/NO-GO in one call.

---

## 3. What I would ask you to do

In the order I would do it:

1. **Design-review the six report pages against a rendered copy.** Cards,
   spacing, titles, whether each chart earns its place. This is the weakest
   artefact and the most visible one.
2. **Decide on PBIR 4.0.** Either generate the folder format natively, or
   document loudly that Desktop must not be saved from. The current
   delete-and-reassert is a workaround, not a fix.
3. **Sanity-check the ML for leakage** (2.4).
4. **Read the ebook end to end** for narrative, not correctness — the numbers
   are generated and current, the prose has had one pass.
5. If you can, capture the real NiFi / Fabric / Power BI screenshots (2.3).

## 4. Traps already paid for — please do not re-pay them

- `.pbi/cache.abf` reaches ~196 MB and GitHub rejects the push at 100 MB. Now
  gitignored.
- Jinja `-#}` strips the following newline and welds `union all` onto `select`.
  Use `#}`.
- DuckDB `read_parquet()` resolves against the process CWD, not the dbt project
  dir — `raw_path` is stamped absolute by the scaffold.
- Metadata API suffix is `.permissionset`, lowercase; the wrong casing reports
  the file as missing from the zip.
- Fields deployed without field-level security are present but invisible;
  `describe()` omits them and the upsert then fails claiming the external ID is
  not unique.
- Salesforce rejects the external ID in the upsert **body** when it is the key
  in the URL.
- `testLevel: NoTestRun` is rejected by production orgs, and a trial counts as
  production.
- A Fabric workspace created via API lands on **no capacity**; every item type
  then fails 403 `FeatureNotAvailable`.
- Windows `setx` writes to the registry, so a process whose environment predates
  it sees nothing — `sf_auth.env()` reads `HKCU\Environment` to compensate.

## 5. Cost

The Fabric trial expires **2026-10-10**. `WS_RedAndYellow` sits on it and will
keep consuming until deleted. Losing it costs nothing — `run_all.py` rebuilds
the whole warehouse locally in ~15 minutes.
