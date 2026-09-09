#!/usr/bin/env python3
"""Exports the dbt marts to Parquet for the Power BI semantic model.

Power BI reads these directly, so the report is one refresh away from whatever
the last dbt build produced. On Fabric the same model would point at the
warehouse instead; this keeps the local path working with no cloud auth.
"""
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "warehouse" / "redandyellow.duckdb"
OUT = REPO / "powerbi" / "data"

MARTS = ["dim_date", "dim_contact", "dim_offering", "dim_campaign",
         "fct_campaign_performance", "fct_admissions_funnel",
         "fct_student_progress_weekly", "fct_lead_conversion"]
# Silver tables the report needs at grain: campaign membership is the
# reach side of marketing, and the ERD entities let the model be walked.
SILVER = ["stg_campaign_member", "stg_programme", "stg_intake",
          "stg_programme_enquiry", "stg_application", "stg_enrolment",
          "stg_student"]
QUALITY = ["dq_issue_log", "dq_summary"]


def main():
    if not DB.exists():
        raise SystemExit(f"warehouse not built ({DB}) - run dbt build first")
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB), read_only=True)

    total = 0.0
    for schema, tables in (("main_gold", MARTS), ("main_quality", QUALITY),
                           ("main_silver", SILVER)):
        for t in tables:
            name = t.replace("stg_", "")
            dest = (OUT / f"{name}.parquet").as_posix()
            con.sql(f"copy (select * from {schema}.{t}) to '{dest}' "
                    f"(format parquet, compression zstd)")
            mb = (OUT / f"{name}.parquet").stat().st_size / 1024 / 1024
            total += mb
            print(f"  {name:<32}{mb:>8.1f} MB")
    print(f"  {'TOTAL':<32}{total:>8.1f} MB")


if __name__ == "__main__":
    main()
