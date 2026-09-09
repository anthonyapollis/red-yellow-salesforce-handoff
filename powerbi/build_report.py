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
RED = "#E03127"
CHARCOAL = "#22252A"
SLATE = "#5A6472"

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


def visual(vtype, x, y, w, h, title=None, projections=None, objects=None, z=0):
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

    vc_objects = {}
    if title:
        vc_objects["title"] = [{"properties": {
            "text": lit(title),
            "fontColor": colour(CHARCOAL),
            "fontSize": {"expr": {"Literal": {"Value": "12D"}}},
            "show": {"expr": {"Literal": {"Value": "true"}}},
        }}]

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
            "color": colour("#FFFFFF"), "transparency": {
                "expr": {"Literal": {"Value": "0D"}}}}}]}}),
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
