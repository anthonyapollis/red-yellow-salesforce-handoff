# Import guide
Inspect and authenticate the intended org first. Map to existing education objects if appropriate.

## Metadata
From salesforce/, with Salesforce CLI and an authenticated alias:
    sf project deploy start --source-dir force-app --target-org YOUR_ORG_ALIAS --dry-run --wait 10
    sf project deploy start --source-dir force-app --target-org YOUR_ORG_ALIAS --wait 10
If still running, retrieve the deployment's final result before import.
    sf org assign permset --name RY_Demo_Import --target-org YOUR_ORG_ALIAS
Assignment targets the alias's user. Standard-object CRUD, API access and campaign/Marketing User permissions are prerequisites, not granted by this set.
API version is 66.0; adapt if necessary. No layouts, tabs, flows, triggers or profiles are provided.

## Offline checks (package root)
    python tools/import_salesforce.py --include-demo
    python tools/test_importer.py

## Authentication
Set SF_INSTANCE_URL (HTTPS origin) and SF_ACCESS_TOKEN in the importing process environment through the user's established secret/authentication mechanism. Never include credentials in the ZIP or chat.
The helper uses REST API v66.0, configurable through --api-version. It does not issue/refresh OAuth tokens; reauthenticate on expiry.

## Read-only preflight
    python tools/import_salesforce.py --preflight
For the fictional seed:
    python tools/import_salesforce.py --preflight --include-demo --opportunity-stage "ACTUAL_ORG_STAGE"
Choose a real active StageName; the same supplied value applies to all demo opportunities. RY_Sample_Stage__c preserves distinct fictional business stages. Adapt per-row stage mapping if needed.
Lead.Status and CampaignMember.Status use org defaults. No converted-lead system fields are written.

## Actual writes
Catalogue only:
    python tools/import_salesforce.py --apply --expected-host YOUR_EXACT_SALESFORCE_HOST
Including fictional CRM/student records:
    python tools/import_salesforce.py --apply --include-demo --expected-host YOUR_EXACT_SALESFORCE_HOST --opportunity-stage "ACTUAL_ORG_STAGE"
Expected host must match SF_INSTANCE_URL. --apply is the write switch. This package specifies no target org.

## Behaviour
- Dependency-ordered upsert by RY_External_ID__c.
- *_Key columns resolve to real parent IDs; they are not Salesforce fields.
- Unknown blank values are omitted, not used to clear existing fields.
- Existing immutable fields must match or the load stops.
- No deletes, lead conversions, emails or campaign activation commands.
- Transient HTTP failures retry. Writes are not one atomic transaction: successes remain. Inspect run_results/import_log.json, fix the error and rerun with unchanged external IDs.
- Record-ID mappings and logs contain no access token.
- Preflight checks metadata. Validation rules, flows, duplicate rules and record-type picklist restrictions can still reject records.
- This is a seed importer, not a production CDC/NiFi service.

Claude can instead use an available Salesforce connector or Data Loader. Follow import_plan.json and resolve parent IDs/relationship mappings correctly.
Do not load data/all_records.json in addition to the CSVs: it repeats those same records.
Verify scoped counts, relationships and business rules after import. The current Base Edition org has been verified live with salesforce/verify_org_counts.py; rerun that check for any different target org.
