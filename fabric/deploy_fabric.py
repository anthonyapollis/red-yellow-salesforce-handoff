#!/usr/bin/env python3
"""Provisions the Microsoft Fabric side and uploads the warehouse to OneLake.

What it does, in order:
  1. Authenticates to Entra ID (interactive by default - no secret in the repo).
  2. Ensures the workspace exists, and a Lakehouse inside it.
  3. Uploads warehouse/raw/*.parquet to OneLake Files/bronze/.
  4. Prints the dbt environment variables needed to point the models at Fabric.

Nothing here is destructive: existing workspaces and lakehouses are reused, and
uploads overwrite only the bronze paths this project owns.

    python deploy_fabric.py --workspace WS_RedAndYellow --lakehouse LH_RedAndYellow
    python deploy_fabric.py --check          # auth + capacity only, no writes

Cost note: a Fabric trial capacity does not stop on its own. Delete the
workspace when the project is done, or when the trial ends.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

try:
    from azure.identity import DeviceCodeCredential, DefaultAzureCredential
except ImportError:
    sys.exit("pip install azure-identity")

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "warehouse" / "raw"

FABRIC_API = "https://api.fabric.microsoft.com/v1"
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
ONELAKE = "https://onelake.dfs.fabric.microsoft.com"
ONELAKE_SCOPE = "https://storage.azure.com/.default"
CHUNK = 4 * 1024 * 1024  # OneLake append limit is well above this; 4 MB is a safe stride


def token(cred, scope):
    return cred.get_token(scope).token


def api(cred, method, path, **kw):
    r = requests.request(method, f"{FABRIC_API}{path}",
                         headers={"Authorization": f"Bearer {token(cred, FABRIC_SCOPE)}"},
                         timeout=120, **kw)
    if not r.ok:
        sys.exit(f"{method} {path} -> {r.status_code}\n{r.text[:800]}")
    return r.json() if r.content else {}


def ensure_workspace(cred, name):
    for w in api(cred, "GET", "/workspaces").get("value", []):
        if w["displayName"] == name:
            print(f"  workspace  {name} (existing)")
            return w["id"]
    w = api(cred, "POST", "/workspaces", json={"displayName": name,
                                               "description": "Red & Yellow CRM analytics"})
    print(f"  workspace  {name} (created)")
    return w["id"]


def ensure_lakehouse(cred, ws_id, name):
    for it in api(cred, "GET", f"/workspaces/{ws_id}/items").get("value", []):
        if it["displayName"] == name and it["type"] == "Lakehouse":
            print(f"  lakehouse  {name} (existing)")
            return it["id"]
    it = api(cred, "POST", f"/workspaces/{ws_id}/items",
             json={"displayName": name, "type": "Lakehouse"})
    print(f"  lakehouse  {name} (created)")
    return it["id"]


def upload(cred, workspace, lakehouse, local: Path, rel: str):
    """PUT a file into OneLake via the ADLS Gen2 API (create, append, flush)."""
    url = f"{ONELAKE}/{workspace}/{lakehouse}.Lakehouse/Files/{rel}"
    hdr = {"Authorization": f"Bearer {token(cred, ONELAKE_SCOPE)}"}

    r = requests.put(f"{url}?resource=file", headers=hdr, timeout=120)
    if r.status_code not in (201, 202):
        sys.exit(f"create {rel} -> {r.status_code}\n{r.text[:400]}")

    pos = 0
    with local.open("rb") as fh:
        while chunk := fh.read(CHUNK):
            r = requests.patch(f"{url}?action=append&position={pos}", headers=hdr,
                               data=chunk, timeout=600)
            if r.status_code != 202:
                sys.exit(f"append {rel} @{pos} -> {r.status_code}\n{r.text[:400]}")
            pos += len(chunk)

    r = requests.patch(f"{url}?action=flush&position={pos}", headers=hdr, timeout=120)
    if r.status_code not in (200, 201):
        sys.exit(f"flush {rel} -> {r.status_code}\n{r.text[:400]}")
    return pos


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", default="WS_RedAndYellow")
    ap.add_argument("--lakehouse", default="LH_RedAndYellow")
    ap.add_argument("--check", action="store_true",
                    help="Authenticate and list workspaces; write nothing")
    ap.add_argument("--device-code", action="store_true",
                    help="Use device-code auth instead of the default credential chain")
    args = ap.parse_args()

    cred = DeviceCodeCredential() if args.device_code else DefaultAzureCredential(
        exclude_managed_identity_credential=True)

    print("\nauthenticating to Fabric...")
    ws_list = api(cred, "GET", "/workspaces").get("value", [])
    print(f"  authenticated. {len(ws_list)} workspace(s) visible")
    for w in ws_list:
        print(f"    - {w['displayName']}")
    if args.check:
        print("\n--check: no changes made.")
        return

    ws_id = ensure_workspace(cred, args.workspace)
    ensure_lakehouse(cred, ws_id, args.lakehouse)

    files = sorted(RAW.glob("*.parquet"))
    if not files:
        sys.exit(f"no parquet in {RAW} - run generator/generate.py first")

    print(f"\nuploading {len(files)} tables to OneLake bronze...")
    total = 0
    for p in files:
        n = upload(cred, args.workspace, args.lakehouse, p, f"bronze/{p.stem}/{p.name}")
        total += n
        print(f"  {p.stem:<22} {n/1024/1024:>8.1f} MB")
    print(f"\n  uploaded {total/1024/1024:,.0f} MB")

    print("\nNext:")
    print("  1. In Fabric, run fabric/notebooks/load_bronze_to_delta.ipynb to create the")
    print("     Delta tables the dbt sources point at.")
    print("  2. Point dbt at Fabric:")
    print(f'       set FABRIC_SERVER=<your-warehouse>.datawarehouse.fabric.microsoft.com')
    print(f'       set FABRIC_DATABASE=WH_RedAndYellow')
    print("       dbt build --target fabric")
    print("\n  Remember to delete the workspace when the trial ends - a Fabric trial")
    print("  capacity keeps running schedules without warning.")


if __name__ == "__main__":
    main()
