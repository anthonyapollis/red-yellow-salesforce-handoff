# Getting data into Salesforce

The org (`business-data-62022`) is empty and has none of the RY objects, so the
order matters: **credentials → deploy metadata → assign permissions → import data.**
Skipping straight to the import fails on the first record, because
`RY_External_ID__c` does not exist yet on any object.

Nothing below runs without credentials, and nothing writes to the org until the
`--apply` step. The Salesforce CLI is *not* required — everything here is plain
Python against the REST and Metadata APIs.

---

## 1. Create an External Client App (once)

This is the only part that has to be done by hand in the browser.

**Setup → App Manager → New External Client App**

- Name: `RY Analytics Integration`
- Contact email: your address
- **API (Enable OAuth Settings)** → tick **Enable OAuth**
- Callback URL: `http://localhost:1717/OauthRedirect` (unused by this flow, but required)
- Scopes: `Manage user data via APIs (api)`, `Perform requests at any time (refresh_token, offline_access)`
- **Flow Enablement** → tick **Enable Client Credentials Flow**
- Save, then open the app → **Policies → Edit** → set **Run As** to your user

The Run As user is the step people miss. Without it the token request returns
`invalid_grant`, and the error does not say why.

Then **Settings → Consumer Key and Secret** to reveal both values.

## 2. Put the credentials in your environment

```powershell
setx SF_CLIENT_ID     "<consumer key>"
setx SF_CLIENT_SECRET "<consumer secret>"
setx SF_LOGIN_URL     "https://business-data-62022.my.salesforce.com"
```

`setx` writes user environment variables, so **open a new terminal afterwards** —
the current one will not see them.

The same two values also fill the NiFi parameter context
(`sf.client.id`, `sf.client.secret`), so this setup serves the pipeline as well
as the importer. One app, both systems.

Verify:

```bash
python salesforce/sf_auth.py
```

That prints the connected user and does nothing else.

## 3. Deploy the metadata

8 custom objects, 65 custom fields across 14 objects, and the `RY_Demo_Import`
permission set. Validate first — this changes nothing:

```bash
python salesforce/deploy_metadata.py --check-only
```

Then deploy:

```bash
python salesforce/deploy_metadata.py
```

The script converts `force-app` from SFDX source format to Metadata API format
(merging the per-field files into one `.object` each), zips it, deploys and
polls until finished. It reports component-level failures individually.

## 4. Assign the permission set

**Setup → Permission Sets → RY Demo Import → Manage Assignments → Add Assignment**

Without this the objects exist but your user cannot write to them, and the
import fails with `INSUFFICIENT_ACCESS` on the first record.

## 5. Import the data

Offline validation — no org contact at all:

```bash
python tools/import_salesforce.py --plan data/crm_load/import_plan.json --include-demo
```

Read-only org preflight — reads metadata, writes nothing:

```bash
python tools/import_salesforce.py --plan data/crm_load/import_plan.json --include-demo --preflight
```

Then the actual load:

```bash
python tools/import_salesforce.py --plan data/crm_load/import_plan.json --include-demo --apply --expected-host business-data-62022.my.salesforce.com --opportunity-stage "Qualification"
```

`--opportunity-stage` must be a **StageName that already exists in your org's
sales process**. The fictional stages stay in `RY_Sample_Stage__c`; the standard
`StageName` gets this one value, because writing a stage the org does not define
is rejected. Check **Setup → Opportunity → Fields → Stage** for a valid value.

`--expected-host` must match `SF_INSTANCE_URL` exactly. It exists so a token for
one org cannot be pointed at another by accident.

## What gets loaded

~1,850 records across 14 objects, referentially complete — the three catalogue
objects first, so every `Intake_Key` on an Opportunity resolves.

Volume deliberately stays small: Salesforce charges storage per record at ~2 KB,
and a Developer org holds roughly 10,000 records in total. The warehouse holds
the 9.4M rows. Raise it with `--budget` on `prepare_crm_load.py` only against an
org you know has the storage.

## If it stops partway

The importer upserts on `RY_External_ID__c`, so **re-running is safe** — records
already written are updated, not duplicated. It writes `run_results/import_log.json`
as it goes and `id_map.partial.json` if it stops, so you can see exactly how far
it got. There is no automatic rollback; fix the cause and re-run.

## Constraints this load respects

- Never writes `IsConverted` or `ConvertedContactId`.
- Never imports `data/legacy/` or `catalogue_observations.csv`.
- Sends no email, launches no campaign, enables no outbound journey.
- Emails are written cleaned — Salesforce rejects malformed addresses outright.
  Name casing, whitespace, phone-format drift and blanks are written as-is,
  because that is what a real CRM holds.
