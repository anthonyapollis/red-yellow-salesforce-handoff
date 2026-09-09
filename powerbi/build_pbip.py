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
    # The entities the canonical ERD names. Without these the model showed only
    # the aggregated facts, so a reader could not walk programme -> offering ->
    # intake -> application -> enrolment -> progress the way the diagram does.
    "programme", "intake", "programme_enquiry", "application",
    "enrolment", "student", "campaign_member",
    # The live CRM slice, extracted back out of Salesforce through the API.
    "sf_account", "sf_contact", "sf_lead", "sf_opportunity",
    # Model output, scored across the whole population.
    "ml_lead_propensity", "ml_withdrawal_risk",
]

# One relationship per edge in erds/03_salesforce_canonical.mmd, so the model
# navigates the way the ERD reads.
RELATIONSHIPS = [
    # catalogue spine
    ("dim_offering", "programme_external_id", "programme", "programme_external_id"),
    ("intake", "offering_external_id", "dim_offering", "offering_external_id"),
    # marketing
    ("fct_campaign_performance", "campaign_external_id", "dim_campaign", "campaign_external_id"),
    ("fct_campaign_performance", "start_date", "dim_date", "date_day"),
    ("campaign_member", "campaign_external_id", "dim_campaign", "campaign_external_id"),
    ("campaign_member", "first_responded_date", "dim_date", "date_day"),
    ("fct_lead_conversion", "created_date", "dim_date", "date_day"),
    # enquiry -> application -> enrolment -> progress
    ("programme_enquiry", "contact_external_id", "dim_contact", "contact_external_id"),
    ("programme_enquiry", "offering_external_id", "dim_offering", "offering_external_id"),
    ("programme_enquiry", "enquiry_date", "dim_date", "date_day"),
    ("application", "contact_external_id", "dim_contact", "contact_external_id"),
    ("application", "intake_external_id", "intake", "intake_external_id"),
    ("application", "submitted_date", "dim_date", "date_day"),
    ("enrolment", "application_external_id", "application", "application_external_id"),
    ("enrolment", "student_external_id", "student", "student_external_id"),
    ("student", "contact_external_id", "dim_contact", "contact_external_id"),
    ("fct_student_progress_weekly", "enrolment_external_id", "enrolment",
     "enrolment_external_id"),
    ("fct_student_progress_weekly", "week_start", "dim_date", "date_day"),
    # aggregated funnel, kept alongside the granular chain
    ("fct_admissions_funnel", "contact_external_id", "dim_contact", "contact_external_id"),
    ("fct_admissions_funnel", "offering_external_id", "dim_offering", "offering_external_id"),
    ("fct_admissions_funnel", "opportunity_created_date", "dim_date", "date_day"),
    # model output back onto the entities it scores
    ("ml_lead_propensity", "created_date", "dim_date", "date_day"),
    ("ml_withdrawal_risk", "enrolment_external_id", "enrolment", "enrolment_external_id"),
]

# Every relationship the report's visuals actually filter across. If one of
# these is ever pushed off the active filter path, the visual still renders and
# still resolves - it just quietly stops responding to the slicer. Asserted at
# build time, because that failure is invisible in the artefact.
REQUIRED_ACTIVE = {
    ("fct_admissions_funnel", "dim_offering"),   # Opportunities/Enrolments by category
    ("fct_admissions_funnel", "dim_date"),       # ... over time
    ("fct_admissions_funnel", "dim_contact"),    # ... by province
    ("fct_campaign_performance", "dim_campaign"),
    ("fct_campaign_performance", "dim_date"),
    ("campaign_member", "dim_campaign"),
    ("fct_lead_conversion", "dim_date"),
    ("fct_student_progress_weekly", "enrolment"),
    ("ml_withdrawal_risk", "enrolment"),
    ("ml_lead_propensity", "dim_date"),
    ("dim_offering", "programme"),
}


def resolve_ambiguity(relationships):
    """Split the relationships into an active spanning forest and the rest.

    Power BI REFUSES to open a model whose active relationships contain a cycle
    - "ambiguous paths between X and Y" - and it is not a warning, the project
    will not load at all. This model has 23 relationships over 17 tables, so
    seven of them close loops: enrolment reaches dim_contact through student and
    again through application, and several entities carry their own date join
    while the fact they roll up to carries one too.

    The redundant ones stay in the model as INACTIVE, so the diagram still reads
    the way the ERD does and USERELATIONSHIP can reach them, but exactly one
    path filters. Which ones give way is decided by rank(): the fact-to-dimension
    star is kept first because that is what every measure in the report filters
    across, then the catalogue spine, and the duplicate entity-to-dimension
    joins yield last.
    """
    def rank(r):
        ft, _fc, tt, _tc = r
        star = ft.startswith(("fct_", "ml_"))
        if star and tt.startswith("dim_"):
            return 0
        if tt == "programme" or (ft == "intake" and tt == "dim_offering"):
            return 1
        if star:
            return 2
        return 4 if tt.startswith("dim_") else 3

    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    active, inactive = [], []
    for r in sorted(relationships, key=rank):
        ra, rb = find(r[0]), find(r[2])
        if ra == rb:
            inactive.append(r)
        else:
            parent[ra] = rb
            active.append(r)

    missing = REQUIRED_ACTIVE - {(r[0], r[2]) for r in active}
    if missing:
        raise SystemExit(
            "MODEL NOT WRITTEN - these relationships must stay active but were "
            "pushed off the filter path:\n" +
            "\n".join(f"  {a} -> {b}" for a, b in sorted(missing)))
    return active, set(inactive)


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

    # Reach, at membership grain rather than pre-aggregated.
    ("Campaign Reach", "COUNTROWS(campaign_member)", "#,0", "01 Marketing"),
    ("Unique Memberships",
     "CALCULATE(COUNTROWS(campaign_member), campaign_member[is_unique_membership] = 1)",
     "#,0", "01 Marketing"),
    ("Responded",
     "CALCULATE(COUNTROWS(campaign_member), campaign_member[is_engaged] = 1)",
     "#,0", "01 Marketing"),
    ("Response Rate", "DIVIDE([Responded], [Unique Memberships])", "0.0%",
     "01 Marketing"),
    ("Duplicate Memberships",
     "CALCULATE(COUNTROWS(campaign_member), campaign_member[is_unique_membership] = 0)",
     "#,0", "01 Marketing"),

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
    # 06 - model output. Scored across the whole population, not just a holdout,
    # so the CRM can be worked in priority order rather than in arrival order.
    ("Scored Leads", "COUNTROWS(ml_lead_propensity)", "#,0", "06 Predictive"),
    ("Avg Propensity", "AVERAGE(ml_lead_propensity[propensity])", "0.0%",
     "06 Predictive"),
    ("Priority Leads",
     "CALCULATE(COUNTROWS(ml_lead_propensity), "
     "ml_lead_propensity[propensity_band] = \"Priority\")", "#,0", "06 Predictive"),
    ("Actual Conversion Rate",
     "DIVIDE(SUM(ml_lead_propensity[target]), COUNTROWS(ml_lead_propensity))",
     "0.0%", "06 Predictive"),
    ("Scored Enrolments", "COUNTROWS(ml_withdrawal_risk)", "#,0", "06 Predictive"),
    ("Avg Withdrawal Risk", "AVERAGE(ml_withdrawal_risk[withdrawal_risk])", "0.0%",
     "06 Predictive"),
    ("Students To Intervene",
     "CALCULATE(COUNTROWS(ml_withdrawal_risk), "
     "ml_withdrawal_risk[risk_band] IN {\"Elevated\", \"Intervene\"})", "#,0",
     "06 Predictive"),
    ("Actual Withdrawal Rate",
     "DIVIDE(SUM(ml_withdrawal_risk[target]), COUNTROWS(ml_withdrawal_risk))",
     "0.0%", "06 Predictive"),

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

    active, inactive = resolve_ambiguity(RELATIONSHIPS)
    rel_lines = []
    for ft, fc, tt, tc in RELATIONSHIPS:
        rel_lines += [f"relationship {tag()}"]
        if (ft, fc, tt, tc) in inactive:
            rel_lines.append("\tisActive: false")
        rel_lines += [f"\tfromColumn: {ft}.{fc}",
                      f"\ttoColumn: {tt}.{tc}", ""]
    (SM / "definition" / "relationships.tmdl").write_text(
        "\n".join(rel_lines), encoding="utf-8")

    # Auto date/time off. Left on, Power BI silently builds a hidden date table
    # and a relationship for EVERY date column - reading the loaded model back
    # showed 27 of them, against the 23 relationships we actually declare. They
    # inflate the file, clutter the field list with date hierarchies nobody
    # asked for, and add filter paths that can create the very ambiguity
    # resolve_ambiguity() exists to prevent. dim_date is the date table here.
    model = ["model Model",
             "\tculture: en-ZA",
             "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
             "\tdiscourageImplicitMeasures",
             "\tsourceQueryCulture: en-ZA",
             "",
             "\tannotation __PBI_TimeIntelligenceEnabled = 0",
             "",
             "\tannotation PBI_ProTooling = [\"DaxQueryView\",\"TMDL\"]", ""]
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
