#!/usr/bin/env python3
"""Generates the Power BI project (PBIP) for Red & Yellow.

PBIP rather than a binary .pbix, for three reasons: it is plain text so the
model diffs in git, it can be generated deterministically from the warehouse,
and - unlike a .pbix - the TMDL definition can be loaded and validated without
Power BI Desktop, so the model is verified rather than assumed.

Column types and names are read from the exported Parquet, so the model cannot
drift from the marts.

    python build_pbip.py
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "powerbi" / "data"
PROJ = REPO / "powerbi" / "RedAndYellow"
SM = PROJ.parent / "RedAndYellow.SemanticModel"
RPT = PROJ.parent / "RedAndYellow.Report"

# Parquet/DuckDB type -> TMDL dataType, and a sensible default format string.
TYPES = {
    "BIGINT": ("int64", "#,0"), "INTEGER": ("int64", "#,0"),
    "HUGEINT": ("int64", "#,0"), "SMALLINT": ("int64", "#,0"),
    "DOUBLE": ("double", "#,0.00"), "FLOAT": ("double", "#,0.00"),
    "DECIMAL": ("decimal", "#,0.00"),
    "VARCHAR": ("string", None), "BOOLEAN": ("boolean", None),
    "DATE": ("dateTime", "yyyy-mm-dd"),
    "TIMESTAMP": ("dateTime", "yyyy-mm-dd hh:nn:ss"),
    "TIMESTAMP WITH TIME ZONE": ("dateTime", "yyyy-mm-dd hh:nn:ss"),
}

# Money columns get a rand format regardless of their numeric type.
MONEY = ("_zar", "spend", "revenue", "fee", "value")

TABLES = [
    "dim_date", "dim_contact", "dim_offering", "dim_campaign",
    "fct_campaign_performance", "fct_admissions_funnel",
    "fct_student_progress_weekly", "fct_lead_conversion",
    "dq_issue_log", "dq_summary",
    # The live CRM slice, extracted back out of Salesforce through the API.
    "sf_account", "sf_contact", "sf_lead", "sf_opportunity",
]

RELATIONSHIPS = [
    ("fct_campaign_performance", "campaign_external_id", "dim_campaign", "campaign_external_id"),
    ("fct_campaign_performance", "start_date", "dim_date", "date_day"),
    ("fct_admissions_funnel", "contact_external_id", "dim_contact", "contact_external_id"),
    ("fct_admissions_funnel", "offering_external_id", "dim_offering", "offering_external_id"),
    ("fct_admissions_funnel", "opportunity_created_date", "dim_date", "date_day"),
    ("fct_student_progress_weekly", "week_start", "dim_date", "date_day"),
    ("fct_lead_conversion", "created_date", "dim_date", "date_day"),
]

# Measures live on one dedicated table so the field list reads as a menu of
# answers rather than a pile of columns.
MEASURES = [
    ("Leads", "COUNTROWS(fct_lead_conversion)", "#,0", "01 Marketing"),
    ("Contacts", "COUNTROWS(dim_contact)", "#,0", "01 Marketing"),
    ("Marketing Spend", "SUM(dim_campaign[spend_zar])", '"R"#,0', "01 Marketing"),
    ("Campaign Members", "SUM(fct_campaign_performance[members])", "#,0", "01 Marketing"),
    ("Engaged Members", "SUM(fct_campaign_performance[engaged_members])", "#,0", "01 Marketing"),
    ("Engagement Rate", "DIVIDE([Engaged Members], [Campaign Members])", "0.0%", "01 Marketing"),
    ("Enrolled Revenue", "SUM(fct_campaign_performance[enrolled_revenue_zar])", '"R"#,0', "01 Marketing"),
    ("Cost per Enrolment",
     "DIVIDE([Marketing Spend], [Campaign Enrolments])", '"R"#,0', "01 Marketing"),
    ("Return on Ad Spend",
     "DIVIDE([Enrolled Revenue], [Marketing Spend])", "0.00", "01 Marketing"),
    ("Campaign Enrolments", "SUM(fct_campaign_performance[enrolments])", "#,0", "01 Marketing"),

    ("Opportunities", "COUNTROWS(fct_admissions_funnel)", "#,0", "02 Admissions"),
    ("Applications",
     "CALCULATE(COUNTROWS(fct_admissions_funnel), "
     "NOT ISBLANK(fct_admissions_funnel[application_external_id]))", "#,0", "02 Admissions"),
    ("Enrolments", "SUM(fct_admissions_funnel[is_enrolled])", "#,0", "02 Admissions"),
    ("Opportunity to Application", "DIVIDE([Applications], [Opportunities])", "0.0%", "02 Admissions"),
    ("Application to Enrolment", "DIVIDE([Enrolments], [Applications])", "0.0%", "02 Admissions"),
    ("Opportunity to Enrolment", "DIVIDE([Enrolments], [Opportunities])", "0.0%", "02 Admissions"),
    ("Pipeline Value", "SUM(fct_admissions_funnel[expected_value_zar])", '"R"#,0', "02 Admissions"),
    ("Agreed Fees", "SUM(fct_admissions_funnel[agreed_fee_zar])", '"R"#,0', "02 Admissions"),
    ("Average Discount", "AVERAGE(fct_admissions_funnel[discount_pct])", "0.0", "02 Admissions"),
    ("Avg Days to Decision", "AVERAGE(fct_admissions_funnel[days_to_decision])", "#,0.0", "02 Admissions"),

    ("Tracked Weeks", "COUNTROWS(fct_student_progress_weekly)", "#,0", "03 Student Success"),
    ("Students At Risk",
     "CALCULATE(DISTINCTCOUNT(fct_student_progress_weekly[enrolment_external_id]), "
     "fct_student_progress_weekly[is_at_risk] = 1)", "#,0", "03 Student Success"),
    ("At Risk Rate",
     "DIVIDE(SUM(fct_student_progress_weekly[is_at_risk]), [Tracked Weeks])", "0.0%",
     "03 Student Success"),
    ("Avg Attendance", "AVERAGE(fct_student_progress_weekly[attendance_pct])", "0.0",
     "03 Student Success"),
    ("Avg Assessment", "AVERAGE(fct_student_progress_weekly[assessment_average_pct])", "0.0",
     "03 Student Success"),
    ("Overdue Assignments", "SUM(fct_student_progress_weekly[overdue_assignments])", "#,0",
     "03 Student Success"),

    ("Quality Issues", "COUNTROWS(dq_issue_log)", "#,0", "04 Data Quality"),
    ("Duplicate Contacts",
     "CALCULATE([Quality Issues], dq_issue_log[issue_code] = \"duplicate_person\")", "#,0",
     "04 Data Quality"),
    ("Contacts With Duplicates",
     "CALCULATE(COUNTROWS(dim_contact), dim_contact[has_duplicates] = 1)", "#,0",
     "04 Data Quality"),
    ("Duplicate Rate", "DIVIDE([Contacts With Duplicates], [Contacts])", "0.0%", "04 Data Quality"),
    ("Unresolved Provinces",
     "CALCULATE(COUNTROWS(dim_contact), dim_contact[province] = \"Unknown\")", "#,0",
     "04 Data Quality"),

    # 05 - the live CRM. Every measure filters is_deleted, because queryAll
    # retains deleted rows on purpose and counting them would overstate the org.
    ("CRM Accounts",
     "CALCULATE(COUNTROWS(sf_account), sf_account[is_deleted] = FALSE())", "#,0",
     "05 Salesforce CRM"),
    ("CRM Contacts",
     "CALCULATE(COUNTROWS(sf_contact), sf_contact[is_deleted] = FALSE())", "#,0",
     "05 Salesforce CRM"),
    ("CRM Leads",
     "CALCULATE(COUNTROWS(sf_lead), sf_lead[is_deleted] = FALSE())", "#,0",
     "05 Salesforce CRM"),
    ("CRM Opportunities",
     "CALCULATE(COUNTROWS(sf_opportunity), sf_opportunity[is_deleted] = FALSE())",
     "#,0", "05 Salesforce CRM"),
    ("CRM Pipeline Value",
     "CALCULATE(SUM(sf_opportunity[RY_Expected_Value_ZAR__c]), "
     "sf_opportunity[is_deleted] = FALSE())", '"R"#,0', "05 Salesforce CRM"),
    ("CRM Records Deleted",
     "CALCULATE(COUNTROWS(sf_contact), sf_contact[is_deleted] = TRUE()) + "
     "CALCULATE(COUNTROWS(sf_lead), sf_lead[is_deleted] = TRUE()) + "
     "CALCULATE(COUNTROWS(sf_opportunity), sf_opportunity[is_deleted] = TRUE())",
     "#,0", "05 Salesforce CRM"),
    ("CRM Contacts Missing Email",
     "CALCULATE(COUNTROWS(sf_contact), sf_contact[is_deleted] = FALSE(), "
     "ISBLANK(sf_contact[Email]))", "#,0", "05 Salesforce CRM"),
    ("CRM Email Completeness",
     "DIVIDE([CRM Contacts] - [CRM Contacts Missing Email], [CRM Contacts])",
     "0.0%", "05 Salesforce CRM"),
]


def tag():
    return str(uuid.uuid4())


def col_type(duck_type: str, name: str):
    base = duck_type.upper().split("(")[0].strip()
    dtype, fmt = TYPES.get(base, ("string", None))
    if dtype in ("double", "decimal", "int64") and any(m in name.lower() for m in MONEY):
        fmt = '"R"#,0'
    return dtype, fmt


def table_tmdl(name: str, cols, is_date_table=False):
    L = [f"table {name}", f"\tlineageTag: {tag()}", ""]
    if is_date_table:
        L.insert(2, "\tdataCategory: Time")
    for cname, ctype in cols:
        dtype, fmt = col_type(ctype, cname)
        L += [f"\tcolumn {cname}",
              f"\t\tdataType: {dtype}"]
        if is_date_table and cname == "date_day":
            L.append("\t\tisKey")
        if fmt:
            L.append(f'\t\tformatString: {fmt}')
        L += [f"\t\tlineageTag: {tag()}",
              "\t\tsummarizeBy: none" if dtype in ("string", "boolean", "dateTime")
              else "\t\tsummarizeBy: sum",
              f"\t\tsourceColumn: {cname}", ""]

    src = (DATA / f"{name}.parquet").as_posix().replace("/", "\\")
    L += [f"\tpartition {name} = m",
          "\t\tmode: import",
          "\t\tsource =",
          "\t\t\t\tlet",
          f'\t\t\t\t    Source = Parquet.Document(File.Contents("{src}"))',
          "\t\t\t\tin",
          "\t\t\t\t    Source",
          "", "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(L)


def measures_tmdl():
    L = ["table _Measures", f"\tlineageTag: {tag()}", ""]
    for mname, expr, fmt, folder in MEASURES:
        L += [f"\tmeasure '{mname}' = {expr}",
              f"\t\tformatString: {fmt}",
              f"\t\tdisplayFolder: {folder}",
              f"\t\tlineageTag: {tag()}", ""]
    # A measures-only table still needs a partition and a placeholder column.
    L += ["\tcolumn _placeholder",
          "\t\tisHidden",
          "\t\tdataType: string",
          f"\t\tlineageTag: {tag()}",
          "\t\tsummarizeBy: none",
          "\t\tsourceColumn: _placeholder", "",
          "\tpartition _Measures = m",
          "\t\tmode: import",
          "\t\tsource =",
          "\t\t\t\tlet",
          '\t\t\t\t    Source = #table(type table [_placeholder = text], {{""}})',
          "\t\t\t\tin",
          "\t\t\t\t    Source", ""]
    return "\n".join(L)


def main():
    if not DATA.exists() or not list(DATA.glob("*.parquet")):
        raise SystemExit(f"no parquet in {DATA} - export the marts first")

    con = duckdb.connect()
    schemas = {}
    for t in TABLES:
        p = DATA / f"{t}.parquet"
        if not p.exists():
            raise SystemExit(f"missing {p}")
        d = con.sql(f"describe select * from read_parquet('{p.as_posix()}')").df()
        schemas[t] = list(zip(d["column_name"], d["column_type"]))

    for d in (SM, RPT):
        if d.exists():
            shutil.rmtree(d)
    (SM / "definition" / "tables").mkdir(parents=True)
    (RPT).mkdir(parents=True)

    # ---- semantic model -------------------------------------------------
    (SM / "definition" / "database.tmdl").write_text(
        "database RedAndYellow\n\tcompatibilityLevel: 1550\n", encoding="utf-8")

    for t, cols in schemas.items():
        (SM / "definition" / "tables" / f"{t}.tmdl").write_text(
            table_tmdl(t, cols, is_date_table=(t == "dim_date")), encoding="utf-8")
    (SM / "definition" / "tables" / "_Measures.tmdl").write_text(
        measures_tmdl(), encoding="utf-8")

    rel_lines = []
    for ft, fc, tt, tc in RELATIONSHIPS:
        rel_lines += [f"relationship {tag()}",
                      f"\tfromColumn: {ft}.{fc}",
                      f"\ttoColumn: {tt}.{tc}", ""]
    (SM / "definition" / "relationships.tmdl").write_text(
        "\n".join(rel_lines), encoding="utf-8")

    model = ["model Model",
             "\tculture: en-ZA",
             "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
             "\tdiscourageImplicitMeasures",
             "\tsourceQueryCulture: en-ZA", ""]
    for t in ["_Measures"] + TABLES:
        model.append(f"ref table {t}")
    (SM / "definition" / "model.tmdl").write_text("\n".join(model) + "\n", encoding="utf-8")

    (SM / "definition.pbism").write_text(
        '{\n  "version": "4.2",\n  "settings": {}\n}\n', encoding="utf-8")

    # ---- report shell ---------------------------------------------------
    # 1.0 = PBIR-Legacy, matching the report.json that build_report.py writes.
    # 4.0 would tell Desktop to expect the newer definition/pages folder layout,
    # which this project does not use, and it would fail to find one.
    (RPT / "definition.pbir").write_text(
        '{\n  "version": "1.0",\n'
        '  "datasetReference": {\n'
        '    "byPath": { "path": "../RedAndYellow.SemanticModel" }\n'
        '  }\n}\n', encoding="utf-8")

    (PROJ.parent / "RedAndYellow.pbip").write_text(
        '{\n  "version": "1.0",\n'
        '  "artifacts": [\n    { "report": { "path": "RedAndYellow.Report" } }\n  ],\n'
        '  "settings": { "enableAutoRecovery": true }\n}\n', encoding="utf-8")

    n_cols = sum(len(c) for c in schemas.values())
    print(f"wrote PBIP to {PROJ.parent}")
    print(f"  {len(schemas)} tables, {n_cols} columns")
    print(f"  {len(MEASURES)} measures across 4 display folders")
    print(f"  {len(RELATIONSHIPS)} relationships")
    print(f"\n  model: {SM}")
    print(f"  open:  {PROJ.parent / 'RedAndYellow.pbip'}")


if __name__ == "__main__":
    main()
