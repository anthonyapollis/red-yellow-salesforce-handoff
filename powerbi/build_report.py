#!/usr/bin/env python3
"""Generates the Power BI report pages for the Red & Yellow PBIP.

Writes RedAndYellow.Report/report.json in the PBIR-Legacy layout - the same
schema Power BI stores inside a .pbix as Report/Layout, so Desktop opens it
without any preview feature enabled.

Every field reference is checked against the TMDL semantic model before the
file is written, because a mistyped measure name is the failure that would
otherwise show up as a broken visual only after someone opens the report.

    python build_report.py
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SM = REPO / "powerbi" / "RedAndYellow.SemanticModel" / "definition"
RPT = REPO / "powerbi" / "RedAndYellow.Report"

W, H = 1280, 720

# Red & Yellow's own identity, used with restraint: red for emphasis and the
# primary series, yellow for highlight only. Charts run on a muted categorical
# ramp so a ten-series chart does not turn into a warning light, and the two
# brand colours keep their meaning.
RED = "#E03127"
YELLOW = "#FFC629"
CHARCOAL = "#22252A"
SLATE = "#5A6472"
PAPER = "#FFFFFF"
CANVAS = "#F7F8FA"
RULE = "#DDE2E8"
SERIES = ["#E03127", "#2E6E8E", "#4C9F70", "#F0A202", "#8B5FBF",
          "#C7522A", "#3B7EA1", "#7A8B99", "#5C6F52", "#9E4A4A"]
GOOD, WARN, BAD = "#4C9F70", "#F0A202", "#E03127"

M = "_Measures"


def gid():
    return uuid.uuid4().hex[:20]


def lit(s):
    return {"expr": {"Literal": {"Value": f"'{s}'"}}}


def colour(hexstr):
    return {"solid": {"color": {"expr": {"Literal": {"Value": f"'{hexstr}'"}}}}}


def _src(table):
    return table[0].lower() + table[1:3].lower()


def field(table, name, measure):
    """One Select entry plus the queryRef the projection points at."""
    alias = _src(table)
    ref = f"{table}.{name}"
    node = {"Expression": {"SourceRef": {"Source": alias}}, "Property": name}
    sel = {"Measure" if measure else "Column": node, "Name": ref}
    return alias, ref, sel


def series_colours(n):
    """Explicit per-series colours, so the report does not inherit whatever
    default theme the opener happens to have."""
    return [{"properties": {"fill": colour(SERIES[i % len(SERIES)])},
             "selector": {"data": [{"dataViewWildcard": {"matchingOption": 0}}],
                          "metadata": None}} for i in range(n)]


def visual(vtype, x, y, w, h, title=None, projections=None, objects=None, z=0,
           accent=None, subtitle=None):
    """Build one visualContainer.

    projections: {"Values": [(table, name, is_measure), ...], "Category": [...]}
    """
    projections = projections or {}
    froms, selects, proj = {}, [], {}
    for role, fields in projections.items():
        proj[role] = []
        for table, name, is_measure in fields:
            alias, ref, sel = field(table, name, is_measure)
            froms[alias] = table
            selects.append(sel)
            proj[role].append({"queryRef": ref})

    vc_objects = {
        "background": [{"properties": {
            "color": colour(PAPER),
            "show": {"expr": {"Literal": {"Value": "true"}}},
            "transparency": {"expr": {"Literal": {"Value": "0D"}}}}}],
        "border": [{"properties": {
            "color": colour(RULE),
            "show": {"expr": {"Literal": {"Value": "true"}}},
            "radius": {"expr": {"Literal": {"Value": "6D"}}}}}],
        "dropShadow": [{"properties": {
            "show": {"expr": {"Literal": {"Value": "false"}}}}}],
    }
    if title:
        vc_objects["title"] = [{"properties": {
            "text": lit(title),
            "fontColor": colour(accent or CHARCOAL),
            "fontSize": {"expr": {"Literal": {"Value": "11D"}}},
            "fontFamily": lit("Segoe UI Semibold"),
            "alignment": lit("left"),
            "show": {"expr": {"Literal": {"Value": "true"}}},
        }}]
    if subtitle:
        vc_objects["subTitle"] = [{"properties": {
            "text": lit(subtitle),
            "fontColor": colour(SLATE),
            "fontSize": {"expr": {"Literal": {"Value": "9D"}}},
            "show": {"expr": {"Literal": {"Value": "true"}}},
        }}]

    objects = dict(objects or {})
    # Colour the marks explicitly, and keep card values on brand red.
    n_series = len(proj.get("Y", [])) or len(proj.get("Values", [])) or 1
    if vtype in ("clusteredColumnChart", "clusteredBarChart", "lineChart",
                 "areaChart", "stackedColumnChart"):
        objects.setdefault("dataPoint", series_colours(n_series))
        objects.setdefault("categoryAxis", [{"properties": {
            "showAxisTitle": {"expr": {"Literal": {"Value": "false"}}},
            "fontSize": {"expr": {"Literal": {"Value": "9D"}}},
            "labelColor": colour(SLATE)}}])
        objects.setdefault("valueAxis", [{"properties": {
            "showAxisTitle": {"expr": {"Literal": {"Value": "false"}}},
            "fontSize": {"expr": {"Literal": {"Value": "9D"}}},
            "labelColor": colour(SLATE),
            "gridlineColor": colour(RULE)}}])
        objects.setdefault("legend", [{"properties": {
            "position": lit("Top"), "labelColor": colour(SLATE),
            "fontSize": {"expr": {"Literal": {"Value": "9D"}}},
            "showTitle": {"expr": {"Literal": {"Value": "false"}}}}}])
    if vtype == "card":
        objects.setdefault("labels", [{"properties": {
            "color": colour(accent or RED),
            "fontSize": {"expr": {"Literal": {"Value": "26D"}}},
            "fontFamily": lit("Segoe UI Semibold")}}])
        objects.setdefault("categoryLabels", [{"properties": {
            "show": {"expr": {"Literal": {"Value": "false"}}}}}])
    if vtype == "tableEx":
        objects.setdefault("columnHeaders", [{"properties": {
            "fontColor": colour(PAPER), "backColor": colour(CHARCOAL),
            "fontSize": {"expr": {"Literal": {"Value": "9D"}}}}}])
        objects.setdefault("values", [{"properties": {
            "fontSize": {"expr": {"Literal": {"Value": "9D"}}},
            "fontColor": colour(CHARCOAL)}}])

    cfg = {
        "name": gid(),
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": z,
                                           "width": w, "height": h}}],
        "singleVisual": {
            "visualType": vtype,
            "projections": proj,
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": a, "Entity": t, "Type": 0} for a, t in froms.items()],
                "Select": selects,
            },
            "drillFilterOtherVisuals": True,
            "objects": objects or {},
            "vcObjects": vc_objects,
        },
    }
    return {"x": x, "y": y, "z": z, "width": w, "height": h,
            "config": json.dumps(cfg), "filters": "[]"}


def textbox(x, y, w, h, runs, z=0):
    paragraphs = [{"textRuns": [{"value": t, "textStyle": st} for t, st in runs]}]
    cfg = {
        "name": gid(),
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": z,
                                           "width": w, "height": h}}],
        "singleVisual": {
            "visualType": "textbox",
            "drillFilterOtherVisuals": True,
            "objects": {"general": [{"properties": {
                "paragraphs": paragraphs}}]},
            "vcObjects": {"background": [{"properties": {"show": {
                "expr": {"Literal": {"Value": "false"}}}}}]},
        },
    }
    return {"x": x, "y": y, "z": z, "width": w, "height": h,
            "config": json.dumps(cfg), "filters": "[]"}


def page(name, display, ordinal, visuals):
    return {
        "id": ordinal,
        "name": f"ReportSection{gid()}",
        "displayName": display,
        "filters": "[]",
        "ordinal": ordinal,
        "visualContainers": visuals,
        "config": json.dumps({"objects": {"background": [{"properties": {
            "color": colour(CANVAS), "transparency": {
                "expr": {"Literal": {"Value": "0D"}}}}}],
            "displayArea": [{"properties": {
                "verticalAlignment": lit("Top")}}]}}),
        "displayOption": 1,
        "width": W,
        "height": H,
    }


TITLE = ("Segoe UI", {"fontSize": "22pt", "fontWeight": "bold", "color": CHARCOAL})
SUB = {"fontSize": "10pt", "color": SLATE}
BIG = {"fontSize": "22pt", "fontWeight": "bold", "color": CHARCOAL}


def build():
    pages = []

    # ---------------------------------------------------------------- 1 ----
    cards = [("Leads", 40), ("Contacts", 240), ("Opportunities", 440),
             ("Enrolments", 640), ("Marketing Spend", 840), ("Enrolled Revenue", 1040)]
    v = [
        textbox(30, 20, 700, 44, [("Red & Yellow — marketing to enrolment", BIG)]),
        textbox(30, 62, 900, 30,
                [("Catalogue is real. People, campaigns and outcomes are synthetic.", SUB)]),
    ]
    for label, x in cards:
        v.append(visual("card", x, 110, 190, 110, label,
                        {"Values": [(M, label, True)]}))
    v += [
        # Titled for what it actually plots. An earlier draft called this
        # "Funnel by stage" while charting programme category - a label that
        # would have been read as stage-to-stage conversion and quietly
        # misinformed anyone who trusted it.
        visual("clusteredBarChart", 30, 250, 610, 300,
               "Opportunities and enrolments by programme category",
               {"Category": [("dim_offering", "category", False)],
                "Y": [(M, "Opportunities", True), (M, "Enrolments", True)]}),
        visual("lineChart", 660, 250, 590, 300, "Opportunities over time",
               {"Category": [("dim_date", "month_start", False)],
                "Y": [(M, "Opportunities", True), (M, "Enrolments", True)]}),
        visual("clusteredColumnChart", 30, 570, 610, 130, "Enrolments by province",
               {"Category": [("dim_contact", "province", False)],
                "Y": [(M, "Enrolments", True)]}),
        visual("slicer", 660, 570, 290, 130, "Year",
               {"Values": [("dim_date", "calendar_year", False)]}),
        visual("slicer", 960, 570, 290, 130, "Delivery mode",
               {"Values": [("dim_offering", "delivery_mode", False)]}),
    ]
    pages.append(page("exec", "Executive Summary", 0, v))

    # ---------------------------------------------------------------- 2 ----
    v = [
        textbox(30, 20, 900, 40, [("Campaign performance", BIG)]),
        textbox(30, 60, 1000, 34,
                [("Spend is aggregated at campaign grain before it meets enrolments, "
                  "so a campaign's cost is never multiplied by its row count.", SUB)]),
        visual("card", 30, 105, 200, 100, "Marketing Spend",
               {"Values": [(M, "Marketing Spend", True)]}),
        visual("card", 240, 105, 200, 100, "Cost per Enrolment",
               {"Values": [(M, "Cost per Enrolment", True)]}),
        visual("card", 450, 105, 200, 100, "Return on Ad Spend",
               {"Values": [(M, "Return on Ad Spend", True)]}),
        visual("card", 660, 105, 200, 100, "Engagement Rate",
               {"Values": [(M, "Engagement Rate", True)]}),
        visual("slicer", 870, 105, 380, 100, "Channel",
               {"Values": [("dim_campaign", "channel", False)]}),
        visual("clusteredColumnChart", 30, 220, 610, 250, "Cost per enrolment by channel",
               {"Category": [("dim_campaign", "channel", False)],
                "Y": [(M, "Cost per Enrolment", True)]}),
        visual("clusteredColumnChart", 660, 220, 590, 250, "Return on ad spend by channel",
               {"Category": [("dim_campaign", "channel", False)],
                "Y": [(M, "Return on Ad Spend", True)]}),
        visual("tableEx", 30, 485, 1220, 215, "Campaigns",
               {"Values": [("dim_campaign", "campaign_name", False),
                           ("dim_campaign", "channel", False),
                           (M, "Campaign Members", True),
                           (M, "Opportunities", True),
                           (M, "Campaign Enrolments", True),
                           (M, "Marketing Spend", True),
                           (M, "Cost per Enrolment", True),
                           (M, "Return on Ad Spend", True)]}),
    ]
    pages.append(page("campaign", "Campaign Performance", 1, v))

    # ---------------------------------------------------------------- 3 ----
    v = [
        textbox(30, 20, 900, 40, [("Admissions and student success", BIG)]),
        textbox(30, 60, 1000, 34,
                [("At risk = attendance under 55%, or assessment average under 50%, "
                  "or three or more overdue assignments.", SUB)]),
        visual("card", 30, 105, 200, 100, "Applications",
               {"Values": [(M, "Applications", True)]}),
        visual("card", 240, 105, 200, 100, "Opportunity to Enrolment",
               {"Values": [(M, "Opportunity to Enrolment", True)]}),
        visual("card", 450, 105, 200, 100, "Avg Days to Decision",
               {"Values": [(M, "Avg Days to Decision", True)]}),
        visual("card", 660, 105, 200, 100, "At Risk Rate",
               {"Values": [(M, "At Risk Rate", True)]}),
        visual("card", 870, 105, 200, 100, "Avg Attendance",
               {"Values": [(M, "Avg Attendance", True)]}),
        visual("card", 1080, 105, 170, 100, "Students At Risk",
               {"Values": [(M, "Students At Risk", True)]}),
        visual("lineChart", 30, 220, 610, 250, "Academic health by week of study",
               {"Category": [("fct_student_progress_weekly", "week_number", False)],
                "Y": [(M, "Avg Attendance", True), (M, "Avg Assessment", True),
                      (M, "At Risk Rate", True)]}),
        visual("clusteredBarChart", 660, 220, 590, 250, "At-risk rate by programme",
               {"Category": [("fct_student_progress_weekly", "programme_title", False)],
                "Y": [(M, "At Risk Rate", True)]}),
        visual("tableEx", 30, 485, 1220, 215, "Programme demand",
               {"Values": [("dim_offering", "programme_title", False),
                           ("dim_offering", "delivery_mode", False),
                           ("dim_offering", "advertised_fee_zar", False),
                           (M, "Opportunities", True),
                           (M, "Applications", True),
                           (M, "Enrolments", True),
                           (M, "Average Discount", True)]}),
    ]
    pages.append(page("students", "Admissions & Students", 2, v))

    # ---------------------------------------------------------------- 4 ----
    v = [
        textbox(30, 20, 900, 40, [("Data quality", BIG)]),
        textbox(30, 60, 1050, 34,
                [("Defects were injected at known rates and recorded in a ground-truth "
                  "manifest. These are what the pipeline caught.", SUB)]),
        visual("card", 30, 105, 230, 100, "Quality Issues",
               {"Values": [(M, "Quality Issues", True)]}),
        visual("card", 270, 105, 230, 100, "Duplicate Contacts",
               {"Values": [(M, "Duplicate Contacts", True)]}),
        visual("card", 510, 105, 230, 100, "Duplicate Rate",
               {"Values": [(M, "Duplicate Rate", True)]}),
        visual("card", 750, 105, 230, 100, "Unresolved Provinces",
               {"Values": [(M, "Unresolved Provinces", True)]}),
        visual("slicer", 990, 105, 260, 100, "Entity",
               {"Values": [("dq_issue_log", "entity", False)]}),
        visual("clusteredBarChart", 30, 220, 610, 250, "Issues by type",
               {"Category": [("dq_issue_log", "issue_code", False)],
                "Y": [(M, "Quality Issues", True)]}),
        visual("clusteredColumnChart", 660, 220, 590, 250, "Issues by entity",
               {"Category": [("dq_issue_log", "entity", False)],
                "Y": [(M, "Quality Issues", True)]}),
        visual("tableEx", 30, 485, 1220, 215, "Issue detail",
               {"Values": [("dq_summary", "entity", False),
                           ("dq_summary", "issue_code", False),
                           ("dq_summary", "issue_description", False),
                           ("dq_summary", "issue_count", False)]}),
    ]
    pages.append(page("quality", "Data Quality", 3, v))

    # ---------------------------------------------------------------- 5 ----
    v = [
        textbox(30, 20, 900, 40, [("Salesforce CRM - live", BIG)]),
        textbox(30, 60, 1060, 34,
                [("Extracted from the org through the REST API on a "
                  "SystemModstamp watermark. Deleted records are retained and "
                  "flagged rather than dropped, so removals are visible.", SUB)]),
        visual("card", 30, 105, 196, 100, "CRM Accounts",
               {"Values": [(M, "CRM Accounts", True)]}),
        visual("card", 236, 105, 196, 100, "CRM Contacts",
               {"Values": [(M, "CRM Contacts", True)]}),
        visual("card", 442, 105, 196, 100, "CRM Leads",
               {"Values": [(M, "CRM Leads", True)]}),
        visual("card", 648, 105, 196, 100, "CRM Opportunities",
               {"Values": [(M, "CRM Opportunities", True)]}),
        visual("card", 854, 105, 196, 100, "CRM Pipeline Value",
               {"Values": [(M, "CRM Pipeline Value", True)]}),
        visual("card", 1060, 105, 190, 100, "Deleted, captured",
               {"Values": [(M, "CRM Records Deleted", True)]}, accent=SLATE),

        visual("clusteredColumnChart", 30, 220, 610, 250,
               "Opportunity pipeline by stage",
               {"Category": [("sf_opportunity", "StageName", False)],
                "Y": [(M, "CRM Opportunities", True)]}),
        visual("clusteredBarChart", 660, 220, 590, 250, "Leads by status",
               {"Category": [("sf_lead", "RY_Sample_Status__c", False)],
                "Y": [(M, "CRM Leads", True)]}),

        visual("card", 30, 485, 196, 90, "Email completeness",
               {"Values": [(M, "CRM Email Completeness", True)]}, accent=GOOD),
        visual("slicer", 236, 485, 200, 90, "Lead source",
               {"Values": [("sf_lead", "LeadSource", False)]}),
        visual("tableEx", 446, 485, 804, 215, "Contacts in the CRM",
               {"Values": [("sf_contact", "RY_External_ID__c", False),
                           ("sf_contact", "FirstName", False),
                           ("sf_contact", "LastName", False),
                           ("sf_contact", "Email", False),
                           ("sf_contact", "is_deleted", False)]}),
        visual("tableEx", 30, 585, 406, 115, "Accounts",
               {"Values": [("sf_account", "Name", False)]}),
    ]
    pages.append(page("crm", "Salesforce CRM", 4, v))

    return {
        "id": 0,
        "resourcePackages": [],
        "sections": pages,
        "config": json.dumps({
            "version": "5.43",
            "themeCollection": {"baseTheme": {"name": "CY24SU06",
                                              "version": "5.55",
                                              "type": 2}},
            "activeSectionIndex": 0,
            "defaultDrillFilterOtherVisuals": True,
            "settings": {"useStylableVisualContainerHeader": True},
        }),
        "layoutOptimization": 0,
    }


def model_fields():
    """Read the TMDL back to learn what actually exists in the model."""
    tables = {}
    for f in (SM / "tables").glob("*.tmdl"):
        text = f.read_text(encoding="utf-8")
        tname = re.match(r"table\s+(\S+)", text).group(1)
        cols = set(re.findall(r"^\tcolumn\s+(\S+)", text, re.M))
        meas = set(re.findall(r"^\tmeasure\s+'([^']+)'", text, re.M))
        tables[tname] = (cols, meas)
    return tables


def main():
    if not (SM / "tables").exists():
        raise SystemExit("semantic model not generated - run build_pbip.py first")

    tables = model_fields()
    report = build()

    # Validate every projection against the model before writing anything.
    problems, checked = [], 0
    for sec in report["sections"]:
        for vc in sec["visualContainers"]:
            cfg = json.loads(vc["config"])
            sv = cfg["singleVisual"]
            for sel in sv.get("prototypeQuery", {}).get("Select", []):
                kind = "Measure" if "Measure" in sel else "Column"
                tbl, prop = sel["Name"].split(".", 1)
                checked += 1
                if tbl not in tables:
                    problems.append(f"{sec['displayName']}: unknown table {tbl}")
                    continue
                cols, meas = tables[tbl]
                pool = meas if kind == "Measure" else cols
                if prop not in pool:
                    problems.append(
                        f"{sec['displayName']}: {tbl}[{prop}] is not a "
                        f"{kind.lower()} in the model")

    if problems:
        print("REPORT NOT WRITTEN - field references do not resolve:")
        for p in problems:
            print("  -", p)
        raise SystemExit(1)

    RPT.mkdir(parents=True, exist_ok=True)
    (RPT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    n_vis = sum(len(s["visualContainers"]) for s in report["sections"])
    print(f"wrote {RPT / 'report.json'}")
    print(f"  {len(report['sections'])} pages, {n_vis} visuals")
    print(f"  {checked} field references checked, all resolve against the model")
    for s in report["sections"]:
        print(f"    {s['ordinal'] + 1}. {s['displayName']:<26}"
              f"{len(s['visualContainers'])} visuals")


if __name__ == "__main__":
    main()
