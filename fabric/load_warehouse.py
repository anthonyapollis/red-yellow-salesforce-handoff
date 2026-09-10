#!/usr/bin/env python3
"""Lands the raw tables in the Fabric Warehouse so dbt's `fabric` target has sources.

The bronze parquet is already in OneLake under the Lakehouse's Files/bronze, but
a Lakehouse SQL endpoint is read-only and only exposes Delta *tables* - raw files
sitting in Files/ are invisible to it. So the Warehouse pulls them in directly
with COPY INTO, which reads OneLake over the executing user's own Entra identity.

Schemas are inferred from the parquet rather than hand-written, because there are
13 tables and a hand-maintained DDL would drift the moment the generator changes
a column - the same failure that put wrong numbers in PLATFORM.md.

    python load_warehouse.py                 # create schema + load every table
    python load_warehouse.py --only campaign # one table, for a quick probe
    python load_warehouse.py --check         # report row counts, load nothing

Auth is an Azure CLI access token, so nothing interactive and no stored secret.
"""
from __future__ import annotations

import argparse
import json
import struct
import subprocess
import sys
from pathlib import Path

import pyarrow.parquet as pq
import pyodbc

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "warehouse" / "raw"
SCHEMA = "raw_salesforce"
WORKSPACE = "WS_RedAndYellow"

# COPY INTO will not resolve OneLake paths written with display names - it
# reports "Access token couldn't be fetched ... unsupported URL", which reads
# like an auth failure and is not one. Workspace and item GUIDs work.
# The uploader also writes each table into its own directory, so the file is at
# Files/bronze/<table>/<table>.parquet, not Files/bronze/<table>.parquet.
ONELAKE_HOST = "https://onelake.dfs.fabric.microsoft.com"

TABLES = ["campaign", "lead", "contact", "campaign_member", "opportunity",
          "application", "student", "enrolment", "student_progress",
          "programme_enquiry", "programme", "programme_offering", "intake"]


def resolve():
    """Returns (sql server, workspace id, lakehouse id) - GUIDs, not names."""
    import requests
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from deploy_fabric import token, FABRIC_API, FABRIC_SCOPE
    from azure.identity import DefaultAzureCredential
    cred = DefaultAzureCredential(exclude_managed_identity_credential=True)
    H = {"Authorization": "Bearer " + token(cred, FABRIC_SCOPE)}
    ws = next(w["id"] for w in requests.get(FABRIC_API + "/workspaces", headers=H,
                                            timeout=90).json()["value"]
              if w["displayName"] == WORKSPACE)
    items = requests.get(f"{FABRIC_API}/workspaces/{ws}/items",
                         headers=H, timeout=90).json()["value"]
    wh = next(i for i in items
              if i["type"] == "Warehouse" and i["displayName"] == "WH_RedAndYellow")
    lh = next(i for i in items if i["type"] == "Lakehouse")
    props = requests.get(f"{FABRIC_API}/workspaces/{ws}/warehouses/{wh['id']}",
                         headers=H, timeout=90).json()["properties"]
    return props["connectionString"], ws, lh["id"]


def connect(srv):
    out = subprocess.run(["az", "account", "get-access-token", "--resource",
                          "https://database.windows.net/", "-o", "json"],
                         capture_output=True, text=True, shell=True)
    tok = json.loads(out.stdout)["accessToken"].encode("utf-16-le")
    return pyodbc.connect(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={srv};"
        f"DATABASE=WH_RedAndYellow;Encrypt=yes;TrustServerCertificate=no",
        attrs_before={1256: struct.pack("=i", len(tok)) + tok}, timeout=90)


def sql_type(field):
    """Map an Arrow type to what a Fabric Warehouse will actually accept.

    Fabric has no NVARCHAR and no VARCHAR(MAX) - strings are VARCHAR(n) with a
    UTF-8 collation. Widths are taken generously rather than measured, because a
    truncation here would silently corrupt data on load.
    """
    import pyarrow as pa
    t = field.type
    if pa.types.is_boolean(t):
        return "bit"
    if pa.types.is_integer(t):
        return "bigint"
    if pa.types.is_floating(t) or pa.types.is_decimal(t):
        return "float"
    if pa.types.is_date(t):
        return "date"
    if pa.types.is_timestamp(t):
        return "datetime2(6)"
    return "varchar(4000)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    tables = [args.only] if args.only else TABLES
    srv, ws_id, lh_id = resolve()
    bronze = f"{ONELAKE_HOST}/{ws_id}/{lh_id}/Files/bronze"
    print(f"server  {srv}\n")
    cn = connect(srv)
    cn.autocommit = True
    cur = cn.cursor()

    cur.execute("if not exists (select 1 from sys.schemas where name = ?) "
                "exec('create schema " + SCHEMA + "')", SCHEMA)

    for t in tables:
        if args.check:
            try:
                n = cur.execute(f"select count(*) from {SCHEMA}.{t}").fetchone()[0]
                print(f"  {t:<22}{n:>12,}")
            except Exception as e:
                print(f"  {t:<22}{'-':>12}  ({str(e)[:60]})")
            continue

        pf = RAW / f"{t}.parquet"
        if not pf.exists():
            print(f"  {t:<22}skipped - no local parquet to read a schema from")
            continue

        cols = ", ".join(f"[{f.name}] {sql_type(f)}" for f in pq.read_schema(pf))
        cur.execute(f"if object_id('{SCHEMA}.{t}') is not null drop table {SCHEMA}.{t}")
        cur.execute(f"create table {SCHEMA}.{t} ({cols})")
        cur.execute(f"""
            copy into {SCHEMA}.{t}
            from '{bronze}/{t}/{t}.parquet'
            with (file_type = 'PARQUET')""")
        n = cur.execute(f"select count(*) from {SCHEMA}.{t}").fetchone()[0]
        print(f"  {t:<22}{n:>12,} rows loaded")

    cn.close()


if __name__ == "__main__":
    main()
