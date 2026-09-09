#!/usr/bin/env python3
"""Deletes RY-tagged records in the org that are not in the current CSV load.

Only touches records whose RY_External_ID__c is set and is absent from
data/crm_load/*.csv. Anything without an RY external ID - anything not put
there by this project - is never considered.

Why it exists: an earlier CRM slice was sampled with ORDER BY created_date DESC,
which is not a sample. Injected duplicates carry created_date + 30..400 days, so
the newest rows are disproportionately the defective ones; the slice came out
29.4% null-email against a warehouse rate of 4.37%. The sampling now uses a hash
of the key, but the first, biased batch is still in the org under different
external IDs, because an upsert cannot remove what it was never asked about.

    python cleanup_stale.py            # report what would be deleted
    python cleanup_stale.py --apply    # delete it
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sf_auth import resolve  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
LOAD = REPO / "data" / "crm_load"
API = "62.0"
# Children first: an Opportunity referencing a Contact must go before it.
ORDER = ["Opportunity", "Lead", "Contact", "Account"]


def wanted(obj):
    p = LOAD / f"{obj}.csv"
    if not p.exists():
        return set()
    with p.open(encoding="utf-8", newline="") as fh:
        return {r["RY_External_ID__c"] for r in csv.DictReader(fh)
                if r.get("RY_External_ID__c")}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="Actually delete. Without this it only reports.")
    args = ap.parse_args()

    url, tok = resolve()
    H = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

    def soql(q):
        p = "/services/data/v" + API + "/query?q=" + urllib.parse.quote(q)
        out, path = [], p
        while True:
            d = json.load(urllib.request.urlopen(
                urllib.request.Request(url + path if not path.startswith("http")
                                       else path, headers=H), timeout=120))
            out.extend(d["records"])
            if d.get("done") or not d.get("nextRecordsUrl"):
                return out
            path = d["nextRecordsUrl"]

    print(f"org: {url}")
    print("mode: DELETE" if args.apply else "mode: report only (use --apply to delete)")
    print()

    plan, total = [], 0
    for obj in ORDER:
        keep = wanted(obj)
        if not keep:
            continue
        rows = soql(f"SELECT Id, RY_External_ID__c FROM {obj} "
                    f"WHERE RY_External_ID__c != null")
        stale = [r for r in rows if r["RY_External_ID__c"] not in keep]
        print(f"  {obj:<14}{len(rows):>6} tagged{len(keep):>8} current"
              f"{len(stale):>8} stale")
        plan.append((obj, stale))
        total += len(stale)

    print(f"\n  {total} record(s) would be deleted")
    if not total:
        print("  nothing to do.")
        return
    if not args.apply:
        print("\n  Re-run with --apply to delete them.")
        return

    deleted, failed = 0, []
    for obj, stale in plan:
        for r in stale:
            req = urllib.request.Request(
                f"{url}/services/data/v{API}/sobjects/{obj}/{r['Id']}",
                headers=H, method="DELETE")
            try:
                urllib.request.urlopen(req, timeout=90)
                deleted += 1
            except HTTPError as e:
                failed.append((obj, r["RY_External_ID__c"], e.code,
                               e.read().decode(errors="replace")[:160]))
        print(f"  {obj:<14}done")

    print(f"\n  deleted {deleted}")
    if failed:
        print(f"  failed  {len(failed)}")
        for o, k, c, m in failed[:10]:
            print(f"    {o} {k}: HTTP {c} {m}")


if __name__ == "__main__":
    main()
