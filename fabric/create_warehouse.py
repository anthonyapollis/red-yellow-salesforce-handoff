#!/usr/bin/env python3
"""Creates the Fabric Warehouse that dbt's `fabric` target builds into.

The workspace already holds a Lakehouse with the bronze parquet in OneLake, but
a Lakehouse SQL endpoint is READ-ONLY - it surfaces Delta tables for querying
and will not accept CREATE TABLE. dbt needs somewhere it can write, which on
Fabric means a Warehouse item.

    python create_warehouse.py            # create it, print the SQL endpoint
    python create_warehouse.py --check    # report only, create nothing
    python create_warehouse.py --delete   # remove it (trial capacity hygiene)

Auth is the same Entra path deploy_fabric.py uses, so no secret is stored here.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_fabric import token, FABRIC_API, FABRIC_SCOPE  # noqa: E402
from azure.identity import DefaultAzureCredential  # noqa: E402

WORKSPACE = "WS_RedAndYellow"
WAREHOUSE = "WH_RedAndYellow"


def headers():
    cred = DefaultAzureCredential(exclude_managed_identity_credential=True)
    return {"Authorization": "Bearer " + token(cred, FABRIC_SCOPE)}


def workspace_id(H):
    for w in requests.get(FABRIC_API + "/workspaces", headers=H, timeout=90).json()["value"]:
        if w["displayName"] == WORKSPACE:
            return w["id"]
    raise SystemExit(f"workspace {WORKSPACE} not found")


def find(H, ws, item_type, name):
    items = requests.get(f"{FABRIC_API}/workspaces/{ws}/items",
                         headers=H, timeout=90).json()["value"]
    for it in items:
        if it["type"] == item_type and it["displayName"] == name:
            return it
    return None


def endpoint(H, ws, wh_id):
    """The warehouse's SQL connection string, once Fabric has provisioned it."""
    for _ in range(30):
        r = requests.get(f"{FABRIC_API}/workspaces/{ws}/warehouses/{wh_id}",
                         headers=H, timeout=90)
        if r.ok:
            props = r.json().get("properties") or {}
            conn = props.get("connectionString")
            if conn:
                return conn
        time.sleep(10)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--delete", action="store_true")
    args = ap.parse_args()

    H = headers()
    ws = workspace_id(H)
    print(f"workspace  {WORKSPACE}  {ws}")

    wh = find(H, ws, "Warehouse", WAREHOUSE)

    if args.delete:
        if not wh:
            print("  nothing to delete")
            return
        r = requests.delete(f"{FABRIC_API}/workspaces/{ws}/items/{wh['id']}",
                            headers=H, timeout=90)
        print(f"  deleted {WAREHOUSE}" if r.ok else f"  delete failed {r.status_code} {r.text[:200]}")
        return

    if wh:
        print(f"  exists     {WAREHOUSE}  {wh['id']}")
    elif args.check:
        print(f"  MISSING    {WAREHOUSE} - run without --check to create it")
        return
    else:
        r = requests.post(f"{FABRIC_API}/workspaces/{ws}/warehouses", headers=H,
                          json={"displayName": WAREHOUSE,
                                "description": "dbt target for the Red & Yellow "
                                               "medallion warehouse"},
                          timeout=180)
        if r.status_code in (200, 201):
            wh = r.json()
        elif r.status_code == 202:
            # Long-running create: poll the workspace until it appears.
            for _ in range(30):
                time.sleep(10)
                wh = find(H, ws, "Warehouse", WAREHOUSE)
                if wh:
                    break
        if not wh:
            raise SystemExit(f"create failed: {r.status_code} {r.text[:400]}")
        print(f"  created    {WAREHOUSE}  {wh['id']}")

    conn = endpoint(H, ws, wh["id"])
    if conn:
        print(f"\n  FABRIC_SERVER={conn}")
        print(f"  FABRIC_DATABASE={WAREHOUSE}")
        print("\nSet those in the environment, then dbt can target fabric:")
        print("  dbt build --target fabric")
    else:
        print("\n  SQL endpoint not provisioned yet - re-run in a minute.")


if __name__ == "__main__":
    main()
