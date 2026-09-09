#!/usr/bin/env python3
"""Counts what is actually in the org, and reconciles it against the load.

The import log says what was sent. This says what is there. They are different
claims, and only the second one is evidence.

    python verify_org_counts.py
"""
from __future__ import annotations

import collections
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sf_auth import resolve  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OBJECTS = ["Account", "Contact", "Lead", "Opportunity"]


def main():
    url, tok = resolve()
    H = {"Authorization": f"Bearer {tok}"}

    def soql(q):
        p = "/services/data/v62.0/query?q=" + urllib.parse.quote(q)
        return json.load(urllib.request.urlopen(
            urllib.request.Request(url + p, headers=H), timeout=120))

    print(f"org: {url}\n")
    print(f"  {'object':<14}{'total':>9}{'with RY id':>12}{'sent':>8}  reconciles")
    print("  " + "-" * 56)

    log_path = REPO / "run_results" / "import_log.json"
    sent = collections.Counter()
    if log_path.exists():
        for r in json.loads(log_path.read_text(encoding="utf-8")):
            sent[r["object"]] += 1

    ok = True
    for o in OBJECTS:
        total = soql(f"SELECT COUNT() FROM {o}")["totalSize"]
        tagged = soql(f"SELECT COUNT() FROM {o} "
                      f"WHERE RY_External_ID__c != null")["totalSize"]
        expected = sent.get(o, 0)
        good = tagged == expected
        ok &= good
        print(f"  {o:<14}{total:>9}{tagged:>12}{expected:>8}  "
              f"{'yes' if good else 'NO'}")

    print()
    if ok:
        print("  Every record the loader reported is present in the org.")
    else:
        print("  Counts differ - records were rejected after the write, or")
        print("  something else in the org is creating or deleting rows.")

    # A sample, so the figures are not just numbers.
    print("\n  sample contacts:")
    for r in soql("SELECT FirstName, LastName, Email, RY_External_ID__c "
                  "FROM Contact WHERE RY_External_ID__c != null "
                  "ORDER BY RY_External_ID__c LIMIT 5")["records"]:
        print(f"    {r['RY_External_ID__c']:<20}"
              f"{(r.get('FirstName') or ''):<12}{(r.get('LastName') or ''):<16}"
              f"{r.get('Email') or '(none)'}")


if __name__ == "__main__":
    main()
