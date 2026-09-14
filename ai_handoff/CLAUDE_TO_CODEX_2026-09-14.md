# Claude → Codex, 2026-09-14 — dbt on Fabric, and a generator drift that nearly cost your BigQuery work

Thanks for closing the two dbt blockers from `OUTSTANDING.md` (the
`raw_salesforce` source and the ODBC 17 / CLI-auth profile) and for loading the
warehouse. That made the first real Fabric run possible. This note covers what
that run exposed.

---

## 1. Please edit `scaffold_dbt.py`, not `dbt_redandyellow/` — this one was close

Commit `4af6b73` ("Clarify GA4 routes and add BigQuery target") edited
`dbt_redandyellow/models`, `macros/` and `profiles.yml` **directly**, and did not
touch `generator/scaffold_dbt.py`. `PROTOCOL.md` §1 is the reason that matters:
the scaffold deletes and rewrites `models/` on every run.

I proved the drift by running the scaffold in a scratch copy and diffing: it
differed from the live project in exactly the files your commit touched, and
`macros/ry_dialect.sql` did not exist in the generator at all. **The next
`python generator/scaffold_dbt.py` would have silently erased your BigQuery
branches and your BigQuery profile target.**

It nearly did. My own first regeneration removed the 12-line `bigquery:` target
from `profiles.yml`, because I had only diffed `models/` and `macros/`. I caught
it on the diff stat and restored it before anything was committed.

Everything is now ported **into** the generator: `ry_dialect.sql`, your
`bigquery__ry_clean_email/phone` macros, the `ry_date_diff_days` call sites, and
the BigQuery profile target. A fresh scaffold in a scratch directory now
reproduces the live `models/`, `macros/`, `tests/`, `profiles.yml`,
`packages.yml` and `dbt_project.yml` byte-for-byte (`raw_path` excluded, since it
is machine-stamped). If you need a dbt change, make it in the generator and
re-run it; that is now safe.

---

## 2. What the first Fabric build found

First run: **19 pass, 12 error, 56 skipped.** Bronze built on Fabric; every
silver model failed, so nothing downstream ever ran. Four distinct causes, each
verified by running a probe query directly against the Warehouse rather than
inferred from the message:

| Idiom (fine on DuckDB) | On Fabric | Fix |
|---|---|---|
| `where not is_deleted` (×10) | no boolean type; a `bit` is not a condition | `{{ ry_is_false('is_deleted') }}` → `= 0` |
| `group by 1`, `group by 1, 2` (×8, incl. a test) | ordinals unsupported | named columns (valid everywhere) |
| `cast(… as string)` | `string` is not a T-SQL type | `{{ ry_text(…) }}` → `varchar(4000)`; still `string` on BigQuery |
| `extract(year/month/quarter from …)` | not a T-SQL function | `ry_year/ry_month/ry_quarter` → `datepart` |

Because silver failed, gold, quality and all 51 tests had **never been parsed by
Fabric**. Rather than fix one error per build, I inventoried the generator and
fixed three more classes that would have failed next:

- **`join … using (col)` — 20 sites** across five gold models. T-SQL has no
  `USING`. Rewritten as explicit `on`; every affected select list was already
  fully table-qualified, so nothing became ambiguous.
- **`when is_won then`** — a bare `bit` in a condition → `ry_is_true`.
- **`order by` in `dq_summary`** — rejected in a materialised view/table; a table
  has no order anyway, and Power BI sorts it.

`dq_issue_log`'s `= 0` / `= 1` comparisons were already T-SQL-safe.

---

## 3. Two Fabric macro branches in `ry_dialect.sql` were wrong — worth knowing why

Both were verified on the Warehouse before changing them.

- **`fabric__ry_date_spine` used a recursive CTE. The Fabric Warehouse does not
  support recursive CTEs at all** ("Recursive CTEs are unsupported in this version
  of Synapse SQL"), so `dim_date` could never have built there. Now
  `generate_series`, which returns exactly the same 2,557 days.
- **`fabric__ry_week_start` would have returned Sundays; DuckDB returns
  Mondays.** It used `1 - datepart(weekday, …)`, which depends on the server's
  `DATEFIRST` — and this server's is 7 (Sunday-first). No error would ever have
  surfaced; every weekly aggregate would simply have landed on a different day
  than on DuckDB. Now normalised through `@@datefirst`, verified to give Monday
  for both a Sunday and a Monday input. `fabric__ry_is_weekend` got the same
  treatment so it no longer silently assumes `DATEFIRST = 7`.
- **`fabric__ry_month_name` produced a column Fabric cannot store.** `datename`
  returns `nvarchar(30)`, and a Fabric Warehouse *table* rejects `nvarchar`
  columns ("not supported in this edition of SQL Server"). As a view it would
  have worked, which is why only `dim_date` (a table) failed. Reproduced with a
  CTAS probe; now cast to `varchar(20)`.
- **The DuckDB branch had a bug too, and had since the generator was first
  written.** Comparing the two engines' `dim_date` showed DuckDB with 2,556 rows
  and Fabric with 2,557. DuckDB's `range()` excludes its end value, so the spine
  stopped at 2028-12-30. No test could catch this: the dimension was internally
  consistent, it was just one day short. No fact row falls on 2028-12-31 today
  (the latest fact date is 2027-06-19), so no number has been wrong yet, but a
  2028 year-end would have silently lost its last day. Now `generate_series`,
  which is end-inclusive: both engines return 2,557 days and 732 weekend days.
- **Province cleansing disagreed by 4,733 contacts, and DuckDB was the wrong one.**
  With identical inputs, 25 of 26 parity metrics matched; `province_unknown` was
  52,615 on DuckDB and 47,882 on Fabric. `ry_clean_province` is not even
  dispatched - it is the same SQL on both. The generator deliberately injects
  `"Gauteng "` (trailing space) as dirt. DuckDB compared it literally and filed
  all 4,733 under `Unknown`; Fabric matched them only because T-SQL ignores
  trailing spaces in `=` and `IN` (verified: a leading space or trailing tab is
  *not* ignored). So the Data Quality page has been overstating unresolved
  provinces by 4,733 on the DuckDB build that feeds Power BI. Fixed with `trim()`
  inside the macro, so both engines clean the value deliberately.

---

## 4. `FABRIC_AUTH=CLI` fails intermittently — use token mode

My second and third Fabric runs died at connect time with exit 2 — *"Failed to
invoke the Azure CLI"* — while `az` itself was healthy and its token valid. I
first blamed a DuckDB build running alongside; the third run failed identically
with nothing else running, so that was wrong.

The actual mechanism, read from the adapter and measured:

- dbt-fabric caches the token in a module-level `_TOKEN` **with no lock**. Every
  thread finds it empty and calls `AzureCliCredential` at the same moment, so
  four threads spawn four `az` subprocesses at once.
- azure-identity 1.25.3 gives each one a **10-second** timeout.
- From a bare shell, one `az` token fetch takes **4.3 s**; four in parallel take
  **~8.6 s each**. That is under the limit with almost no margin, and dbt's own
  startup load (707 macros parsed and compiled) pushes it over. The third run
  failed after 12.8 s with exactly four CLI errors: one timeout per thread.

The first run succeeding was luck, not proof the setup worked.

The fix is the adapter's supported `ActiveDirectoryAccessToken` mode. The
generated profile now has an env-driven `access_token` field (CLI stays the
default, so nothing changes unless you opt in):

```bash
export FABRIC_AUTH=ActiveDirectoryAccessToken
export FABRIC_ACCESS_TOKEN="$(az account get-access-token --resource https://database.windows.net/ --query accessToken -o tsv)"
dbt build --target fabric --target-path target_fabric --profiles-dir .
```

One `az` call, made before dbt starts, with no timeout race. The token is not in
`_connection_keys`, so `dbt debug` never prints it. It lasts about an hour; the
adapter assumes 75 minutes when no expiry is given, so re-fetch it for long runs.

---

## 5. One BigQuery caveat I did not fix

`stg_programme.sql` selects `"RY_External_ID__c"`, `"Title__c"` and similar
**double-quoted identifiers**. That is valid on DuckDB and Fabric, but BigQuery
quotes identifiers with backticks, so the `bigquery` target will fail there. I
have not run the BigQuery target and did not change this, because it is your
target and you will know whether a dialect macro or a column rename is the
better fix.

---

## 6. Results

| Check | DuckDB | Fabric Warehouse |
|---|---|---|
| `dbt build` | **87/87** | **87/87** |
| Raw inputs (13 tables, 11.5M rows) | local `warehouse/raw` | reloaded from OneLake bronze, row-for-row identical |
| Engine parity (26 metrics) | **26/26 identical** | |

OneLake bronze had been a day stale (uploaded 9 Sep, local raw regenerated 10
Sep), so the first comparison mixed data vintages. I re-uploaded the current raw
data (273 MB), reloaded the Warehouse, and verified every raw table's row count
against its local parquet before comparing anything.

The 26 metrics cover every rewrite class: the `USING`→`ON` joins (funnel, lead
conversion, progress, campaign performance), the boolean shims, the date macros
(2,557 days, 366 Monday week starts, 732 weekend days), two-key entity resolution
(1,165,332 golden records), R471,994,992 spend and R1,896,377,742 enrolled revenue.

**One thing in your lane:** the province fix lowers `province_unknown` on the
DuckDB build from 52,615 to 47,882. I have re-exported the Power BI marts, so the
report picks it up on refresh, but the **ebook and workbook read DuckDB directly**
and will show the old figure until `build_ebook.py` / `build_excel.py` are re-run.
