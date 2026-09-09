#!/usr/bin/env python3
"""Extracts Salesforce objects via the REST API into the warehouse.

This is the round trip the role is actually about: data leaves the CRM through
its API, lands in a queryable store with its lineage attached, and becomes
available to dbt and Power BI without anyone exporting a CSV by hand.

What it demonstrates, deliberately:

  * SOQL against the REST API with automatic pagination (nextRecordsUrl), so the
    2,000-record page limit is handled rather than silently truncating.
  * Incremental extraction on SystemModstamp, with the high-water mark persisted
    between runs. A first run is a full load; later runs pull only changes.
  * Deletion capture via queryAll, so records deleted in Salesforce are marked
    is_deleted in the warehouse instead of lingering forever.
  * Integration metadata on every row - source system, source id, source update
    time, extraction time - which is what makes a warehouse auditable.

    python extract_to_warehouse.py                 # incremental
    python extract_to_warehouse.py --full-refresh  # ignore the high-water mark
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sf_auth import resolve  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "warehouse" / "salesforce_raw"
STATE = REPO / "warehouse" / "_state" / "sf_watermarks.json"
API = "62.0"

# Fields are listed explicitly rather than SELECT * - Salesforce has no SELECT *,
# and naming them means a field disappearing from the org fails loudly here
# instead of silently dropping a column downstream.
OBJECTS = {
    "Account": ["Id", "Name", "RY_External_ID__c", "CreatedDate",
                "SystemModstamp", "IsDeleted"],
    "Contact": ["Id", "FirstName", "LastName", "Email", "Phone", "AccountId",
                "RY_External_ID__c", "CreatedDate", "SystemModstamp", "IsDeleted"],
    "Lead": ["Id", "FirstName", "LastName", "Email", "Phone", "Company", "Status",
             "LeadSource", "RY_External_ID__c", "RY_Sample_Status__c",
             "ConvertedContactId", "IsConverted", "CreatedDate", "SystemModstamp",
             "IsDeleted"],
    "Opportunity": ["Id", "Name", "StageName", "Amount", "CloseDate", "IsWon",
                    "IsClosed", "AccountId", "RY_External_ID__c",
                    "RY_Sample_Stage__c", "RY_Expected_Value_ZAR__c",
                    "CreatedDate", "SystemModstamp", "IsDeleted"],
}


class SF:
    def __init__(self):
        self.url, self.token = resolve()

    def _get(self, path):
        req = urllib.request.Request(
            path if path.startswith("http") else self.url + path,
            headers={"Authorization": f"Bearer {self.token}"})
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.load(r)

    def query(self, soql, include_deleted=False):
        """Run SOQL and follow nextRecordsUrl until every page is retrieved."""
        verb = "queryAll" if include_deleted else "query"
        path = f"/services/data/v{API}/{verb}?q={urllib.parse.quote(soql)}"
        rows, pages = [], 0
        while True:
            d = self._get(path)
            rows.extend(d.get("records", []))
            pages += 1
            nxt = d.get("nextRecordsUrl")
            if d.get("done") or not nxt:
                return rows, pages
            path = nxt


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {}


def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--full-refresh", action="store_true",
                    help="Ignore stored watermarks and re-extract everything")
    ap.add_argument("--objects", nargs="*", default=list(OBJECTS),
                    help="Subset of objects to extract")
    args = ap.parse_args()

    sf = SF()
    OUT.mkdir(parents=True, exist_ok=True)
    state = {} if args.full_refresh else load_state()
    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    print(f"\nExtracting from {sf.url}")
    print(f"mode: {'FULL REFRESH' if args.full_refresh else 'incremental'}\n")
    print(f"  {'object':<14}{'rows':>8}{'pages':>7}  {'new watermark':<26}mode")
    print("  " + "-" * 68)

    summary, total = [], 0
    for obj in args.objects:
        fields = OBJECTS[obj]
        since = state.get(obj)
        where = f" WHERE SystemModstamp > {since}" if since else ""
        soql = f"SELECT {','.join(fields)} FROM {obj}{where} ORDER BY SystemModstamp"

        try:
            rows, pages = sf.query(soql, include_deleted=True)
        except HTTPError as e:
            body = e.read().decode(errors="replace")[:300]
            print(f"  {obj:<14} FAILED HTTP {e.code}: {body}")
            continue

        df = pd.DataFrame([{k: r.get(k) for k in fields} for r in rows])
        if df.empty:
            print(f"  {obj:<14}{0:>8}{pages:>7}  {'(unchanged)':<26}"
                  f"{'incremental' if since else 'full'}")
            summary.append({"object": obj, "rows": 0, "pages": pages})
            continue

        # Deletions come back through queryAll, flagged per row. IsDeleted must
        # be in the SELECT or every deleted record is written as live - which is
        # worse than not capturing deletions at all, because it looks like it
        # worked. Assert rather than default to False.
        if "IsDeleted" not in fields:
            raise SystemExit(f"{obj}: IsDeleted missing from the field list; "
                             f"queryAll would report deleted rows as live")
        df["is_deleted"] = df["IsDeleted"].fillna(False).astype(bool)

        df["source_system"] = "SALESFORCE"
        df["source_record_id"] = df["Id"]
        df["source_updated_at"] = pd.to_datetime(df["SystemModstamp"], errors="coerce", utc=True)
        df["extracted_at"] = run_at

        path = OUT / f"{obj.lower()}.parquet"
        if path.exists() and since:
            # Incremental: merge onto what is already there, newest row wins.
            old = pd.read_parquet(path)
            df = (pd.concat([old, df], ignore_index=True)
                    .sort_values("source_updated_at")
                    .drop_duplicates("Id", keep="last"))
        df.to_parquet(path, index=False, compression="snappy")

        # The watermark advances only after the write succeeds, so a crash
        # re-extracts rather than skipping a window.
        state[obj] = max(r["SystemModstamp"] for r in rows)
        total += len(rows)
        print(f"  {obj:<14}{len(rows):>8}{pages:>7}  {state[obj]:<26}"
              f"{'incremental' if since else 'full'}")
        summary.append({"object": obj, "rows": len(rows), "pages": pages,
                        "watermark": state[obj], "file": str(path)})

    save_state(state)

    print(f"\n  {'TOTAL':<14}{total:>8} records extracted")
    print(f"  landed in {OUT}")
    print(f"  watermarks {STATE}")

    manifest = {"extracted_at": run_at, "instance": sf.url,
                "mode": "full_refresh" if args.full_refresh else "incremental",
                "objects": summary, "total_records": total}
    (OUT / "_extract_manifest.json").write_text(json.dumps(manifest, indent=2),
                                                encoding="utf-8")
    print("\n  Re-run to see incremental behaviour: unchanged objects return 0 rows.")


if __name__ == "__main__":
    main()
