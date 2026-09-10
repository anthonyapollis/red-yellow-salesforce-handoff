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


def repair_null_typed(out_dir):
    """Give every all-null parquet column a concrete type.

    A column that is null for every row lands in parquet as Arrow type `null`.
    Power Query has no .NET type to map that onto, and the refresh fails on the
    WHOLE FILE with "'dataType' argument cannot be null" - naming no table and
    no column, so it reads as a corrupt export rather than one empty field.

    It bit sf_contact.Phone, sf_lead.[Phone, LeadSource, ConvertedContactId]
    and sf_opportunity.[Amount, AccountId] - Salesforce fields that are
    legitimately empty across every record in the org. Those files come from
    the extract, not from this script, which is why this repairs the folder
    Power BI actually reads rather than the queries this script happens to run.

    Casting to string keeps the column present and visibly empty, which is the
    honest representation: the field exists in the CRM and carries no data.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    repaired = []
    for f in sorted(Path(out_dir).glob("*.parquet")):
        schema = pq.read_schema(f)
        nulls = [x.name for x in schema if pa.types.is_null(x.type)]
        if not nulls:
            continue
        t = pq.read_table(f)
        for name in nulls:
            i = t.schema.get_field_index(name)
            t = t.set_column(i, pa.field(name, pa.string()),
                             t.column(i).cast(pa.string()))
        pq.write_table(t, f, compression="zstd")
        repaired.append((f.name, nulls))

    if repaired:
        print("\n  typed all-null columns so Power Query can load them:")
        for name, cols in repaired:
            print(f"    {name:<30}{', '.join(cols)}")
    return repaired


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

    repair_null_typed(OUT)


if __name__ == "__main__":
    main()
