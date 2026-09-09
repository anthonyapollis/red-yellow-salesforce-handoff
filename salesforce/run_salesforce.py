#!/usr/bin/env python3
"""Runs the whole Salesforce sequence: auth check, deploy, then import.

The steps are ordered because they depend on each other - the org has none of
the RY objects, so the import cannot run until the metadata lands, and the
metadata cannot deploy until a token resolves.

Every stage is read-only or validating until --apply is passed. Without it this
script authenticates, validates the metadata against the org and validates the
data offline, and writes nothing.

    python run_salesforce.py                 # check + validate only
    python run_salesforce.py --apply         # deploy metadata, then import data

Credentials come from the environment - see SETUP.md. Nothing is read from or
written to this repository.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PY = sys.executable
PLAN = "data/crm_load/import_plan.json"


def step(n, total, title):
    print(f"\n{'=' * 72}\n[{n}/{total}] {title}\n{'=' * 72}")


def run(cmd, allow_fail=False):
    r = subprocess.run(cmd, cwd=REPO)
    if r.returncode != 0 and not allow_fail:
        sys.exit(f"\nStopped: {' '.join(str(c) for c in cmd)}")
    return r.returncode


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="Actually deploy the metadata and import the data")
    ap.add_argument("--opportunity-stage", default="Qualification",
                    help="A StageName that already exists in the target org")
    args = ap.parse_args()

    total = 6

    step(1, total, "Authenticate")
    run([PY, "salesforce/sf_auth.py"])

    step(2, total, "Check the org can host the model")
    # Exits non-zero on a NO-GO, which stops the run before anything is attempted.
    run([PY, "salesforce/check_org.py"])

    # Resolve the host here so --expected-host cannot drift from the token.
    sys.path.insert(0, str(HERE))
    from sf_auth import resolve
    url, _ = resolve()
    host = urlparse(url).hostname
    print(f"\n  resolved host: {host}")

    step(3, total, "Validate the data offline (no org contact)")
    run([PY, "tools/import_salesforce.py", "--plan", PLAN, "--include-demo"])

    step(4, total, "Validate the metadata against the org (no changes)")
    run([PY, "salesforce/deploy_metadata.py", "--check-only"])

    if not args.apply:
        print(f"\n{'=' * 72}")
        print("Validation complete. Nothing was changed in the org.")
        print("\nTo deploy and import:")
        print(f"  python salesforce/run_salesforce.py --apply "
              f"--opportunity-stage \"<a real StageName>\"")
        print("\nBetween the deploy and the import you must assign the")
        print("RY_Demo_Import permission set to your user, or the import fails")
        print("with INSUFFICIENT_ACCESS on the first record.")
        return

    step(5, total, "Deploy the metadata")
    run([PY, "salesforce/deploy_metadata.py"])
    print("\n  Assign the RY_Demo_Import permission set now:")
    print("  Setup > Permission Sets > RY Demo Import > Manage Assignments")
    try:
        input("\n  Press Enter once the permission set is assigned...")
    except EOFError:
        print("  (non-interactive: continuing - assign it first if the import fails)")

    step(6, total, "Import the data")
    run([PY, "tools/import_salesforce.py", "--plan", PLAN, "--include-demo",
         "--apply", "--expected-host", host,
         "--opportunity-stage", args.opportunity_stage])

    print(f"\n{'=' * 72}")
    print("Done. Results are in run_results/import_log.json and id_map.json.")
    print("Re-running is safe - every object upserts on RY_External_ID__c.")


if __name__ == "__main__":
    main()
