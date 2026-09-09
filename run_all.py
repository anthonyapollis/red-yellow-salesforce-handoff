#!/usr/bin/env python3
"""Runs the whole Red & Yellow platform end to end.

    python run_all.py                 # everything that needs no cloud credentials
    python run_all.py --scale dev     # smaller dataset, faster iteration
    python run_all.py --with-nifi     # also build the NiFi flow (needs NiFi running)

Stages that require credentials - the Fabric upload and the Salesforce import -
are deliberately not run here. They are printed at the end with the exact
command, because a script that silently skips a cloud deployment is worse than
one that tells you what it did not do.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
PY = sys.executable


def step(n, total, title):
    print(f"\n{'=' * 74}\n[{n}/{total}] {title}\n{'=' * 74}")


def run(cmd, cwd=None, env=None):
    t = time.time()
    e = dict(os.environ, **(env or {}))
    r = subprocess.run(cmd, cwd=cwd or REPO, env=e)
    if r.returncode != 0:
        sys.exit(f"\nFAILED: {' '.join(str(c) for c in cmd)}")
    print(f"  ({time.time() - t:.0f}s)")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scale", choices=["smoke", "dev", "full"], default="full")
    ap.add_argument("--with-nifi", action="store_true")
    ap.add_argument("--nifi-user", default=os.environ.get("NIFI_USER", ""))
    ap.add_argument("--nifi-password", default=os.environ.get("NIFI_PASSWORD", ""))
    ap.add_argument("--budget", type=int, default=2400,
                    help="Salesforce record budget for the CRM slice")
    args = ap.parse_args()

    dbt_dir = REPO / "dbt_redandyellow"
    dbt_env = {"DBT_PROFILES_DIR": "."}
    total = 8 + (1 if args.with_nifi else 0)
    t0 = time.time()

    step(1, total, f"Generate synthetic CRM + academic data (scale={args.scale})")
    run([PY, "generator/generate.py", "--scale", args.scale])

    step(2, total, "Scaffold the dbt project")
    run([PY, "generator/scaffold_dbt.py"])

    step(3, total, "Install dbt packages")
    run(["dbt", "deps"], cwd=dbt_dir, env=dbt_env)

    step(4, total, "Build and test the warehouse (models + 51 data tests)")
    run(["dbt", "build"], cwd=dbt_dir, env=dbt_env)

    step(5, total, "Generate the data catalogue")
    run(["dbt", "docs", "generate"], cwd=dbt_dir, env=dbt_env)

    step(6, total, "Build the Excel workbook and the data-story ebook")
    run([PY, "reporting/build_excel.py"])
    run([PY, "reporting/build_ebook.py"])

    step(7, total, "Export the marts and build the Power BI project")
    run([PY, "powerbi/export_marts.py"])
    run([PY, "powerbi/build_pbip.py"])
    run([PY, "powerbi/build_report.py"])

    step(8, total, "Cut the Salesforce CRM load")
    run([PY, "salesforce/prepare_crm_load.py", "--budget", str(args.budget)])

    if args.with_nifi:
        step(9, total, "Build the NiFi ingestion flow")
        if not (args.nifi_user and args.nifi_password):
            sys.exit("  --with-nifi needs --nifi-user and --nifi-password "
                     "(or NIFI_USER / NIFI_PASSWORD in the environment)")
        run([PY, "nifi/build_flow.py", "--user", args.nifi_user,
             "--password", args.nifi_password])

    print(f"\n{'=' * 74}")
    print(f"Done in {time.time() - t0:.0f}s.\n")
    print("Built locally:")
    print("  warehouse/redandyellow.duckdb            the full warehouse")
    print("  dbt_redandyellow/target/index.html       the data catalogue")
    print("  reporting/RedAndYellow_Analytics.xlsx    the workbook")
    print("  ebook/RedAndYellow_Data_Story.docx       the data story")
    print("  powerbi/RedAndYellow.pbip                the Power BI project")
    print("  data/crm_load/                           the Salesforce load")
    print("\nStages needing credentials, not run:")
    print("  Fabric      python fabric/deploy_fabric.py --check")
    print("              python fabric/deploy_fabric.py")
    print("  Salesforce  python tools/import_salesforce.py --preflight")
    print("              python tools/import_salesforce.py --apply \\")
    print("                --expected-host <org>.my.salesforce.com \\")
    print("                --opportunity-stage <a real StageName in that org>")
    print("\nNothing above writes to Salesforce or Fabric without those commands.")


if __name__ == "__main__":
    main()
