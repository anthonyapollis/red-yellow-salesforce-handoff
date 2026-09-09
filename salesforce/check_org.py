#!/usr/bin/env python3
"""Checks whether an org can actually host this model, before deploying to it.

Written after a Base Edition trial accepted the credentials, authenticated
cleanly, and only then rejected all 8 custom objects at deploy time with
"reached maximum number of custom objects". The edition was the problem, and it
was knowable in one API call. This makes that call.

    python check_org.py

Verdict is GO if the org can hold the full model, PARTIAL if only the custom
fields on standard objects will deploy, and NO-GO otherwise.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sf_auth import resolve  # noqa: E402

API = "62.0"

# Editions known to permit no custom objects at all.
NO_CUSTOM_OBJECTS = {"Base Edition", "Essentials Edition", "Starter Edition"}

NEEDED_OBJECTS = 8
NEEDED_FIELDS = 65
# Salesforce bills roughly 2 KB per record; the default CRM slice is ~2,000.
NEEDED_STORAGE_MB = 5


def main():
    url, tok = resolve()

    def get(path):
        req = urllib.request.Request(url + path, headers={"Authorization": f"Bearer {tok}"})
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.load(r)

    def soql(q):
        return get("/services/data/v" + API + "/query?q=" + urllib.parse.quote(q))

    print(f"org: {url}\n")

    org = soql("SELECT Id, OrganizationType, InstanceName, IsSandbox, "
               "TrialExpirationDate FROM Organization")["records"][0]
    edition = org.get("OrganizationType")
    print(f"  edition            {edition}")
    print(f"  instance           {org.get('InstanceName')}")
    print(f"  sandbox            {org.get('IsSandbox')}")
    print(f"  trial expires      {org.get('TrialExpirationDate') or 'not a trial'}")

    limits = get("/services/data/v" + API + "/limits")
    storage = limits.get("DataStorageMB", {})
    print(f"  data storage       {storage.get('Remaining')} MB free "
          f"of {storage.get('Max')} MB")

    sobjects = get("/services/data/v" + API + "/sobjects")["sobjects"]
    custom = [s["name"] for s in sobjects if s.get("custom")]
    print(f"  custom objects     {len(custom)} present")

    # Does the model already exist here?
    existing = [c for c in custom if c.startswith("RY_")]
    if existing:
        print(f"  RY objects present {len(existing)} - model already deployed here")

    print()
    problems, warnings = [], []

    if edition in NO_CUSTOM_OBJECTS:
        problems.append(
            f"{edition} permits no custom objects. The 8 RY objects cannot deploy. "
            "This is an edition entitlement - no permission or setting changes it.")

    free = storage.get("Remaining")
    if isinstance(free, (int, float)) and free < NEEDED_STORAGE_MB:
        problems.append(f"only {free} MB of data storage free; the CRM slice needs "
                        f"about {NEEDED_STORAGE_MB} MB")

    if org.get("TrialExpirationDate"):
        warnings.append("this is a trial org - it will expire. A free Developer "
                        "Edition org does not.")

    if problems:
        print("VERDICT: NO-GO for the full model")
        for p in problems:
            print(f"  - {p}")
        print("\n  A reduced load is still possible:")
        print("    python salesforce/deploy_metadata.py --check-only --standard-only")
        print("  which deploys only the custom fields on standard objects.")
        print("\n  For the full model, use a free Developer Edition org:")
        print("    https://developer.salesforce.com/signup")
        sys.exit(2)

    print("VERDICT: GO")
    print(f"  {NEEDED_OBJECTS} custom objects and {NEEDED_FIELDS} fields should deploy.")
    for w in warnings:
        print(f"  note: {w}")
    print("\n  Next: python salesforce/run_salesforce.py")


if __name__ == "__main__":
    try:
        main()
    except HTTPError as e:
        raise SystemExit(f"org query failed: HTTP {e.code}\n"
                         f"{e.read().decode(errors='replace')[:400]}")
