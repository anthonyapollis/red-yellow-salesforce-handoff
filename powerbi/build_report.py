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

import base64
import json
import re
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SM = REPO / "powerbi" / "RedAndYellow.SemanticModel" / "definition"
RPT = REPO / "powerbi" / "RedAndYellow.Report"
LOGO = REPO / "powerbi" / "assets" / "red-yellow-logo.png"

W, H = 1280, 720

# Red & Yellow's own identity, used with restraint: red for emphasis and the
# primary series, yellow for highlight only. Charts run on a muted categorical
# ramp so a ten-series chart does not turn into a warning light, and the two
# brand colours keep their meaning.
RED = "#F52635"
YELLOW = "#FFB71B"
CHARCOAL = "#1D1D1B"
SLATE = "#60646B"
PAPER = "#FFFFFF"
CANVAS = "#FFF9F0"
# KPI tiles sit on a light yellow rather than white: it ties them to the
# brand without competing with the accent-coloured figure they carry, and it
# separates the number band from the charts below, which stay white so the
# data ink reads cleanly.
TILE, TILE_EDGE = "#FFF4D6", "#E9C46A"   # KPI tile ground and its edge
RULE = "#E5DED2"
SERIES = ["#F52635", "#007C83", "#008C45", "#E39B16", "#7D3C6A",
          "#D9574A", "#2C6FA3", "#707A84", "#5B7250", "#9E3540"]
GOOD, WARN, BAD = "#008C45", "#E39B16", "#F52635"

M = "_Measures"

THEME = {
    "name": "RedAndYellow",
    "dataColors": [
        "#F52635",
        "#FFB71B",
        "#007C83",
        "#008C45",
        "#E56A2C",
        "#7D3C6A",
        "#D9574A",
        "#2C6FA3",
        "#5B7250",
        "#707A84"
    ],
    "background": "#FFFFFF",
    "foreground": "#1D1D1B",
    "tableAccent": "#F52635",
    "good": "#008C45",
    "neutral": "#FFB71B",
    "bad": "#F52635",
    "maximum": "#F52635",
    "center": "#FFB71B",
    "minimum": "#008C45",
    "textClasses": {
        "title": {
            "fontSize": 13,
            "fontFace": "Segoe UI Semibold",
            "color": "#1D1D1B"
        },
        "header": {
            "fontSize": 11,
            "fontFace": "Segoe UI Semibold",
            "color": "#1D1D1B"
        },
        "label": {
            "fontSize": 10,
            "fontFace": "Segoe UI",
            "color": "#60646B"
        },
        "callout": {
            "fontSize": 30,
            "fontFace": "Segoe UI Semibold",
            "color": "#F52635"
        }
    },
    "visualStyles": {
        "*": {
            "*": {
                "background": [
                    {
                        "show": True,
                        "color": {
                            "solid": {
                                "color": "#FFFFFF"
                            }
                        },
                        "transparency": 0
                    }
                ],
                "border": [
                    {
                        "show": True,
                        "color": {
                            "solid": {
                                "color": "#E2E7ED"
                            }
                        },
                        "radius": 6
                    }
                ],
                "dropShadow": [
                    {
                        "show": False
                    }
                ],
                "title": [
                    {
                        "show": True,
                        "fontColor": {
                            "solid": {
                                "color": "#1D1D1B"
                            }
                        },
                        "fontSize": 11,
                        "fontFamily": "Segoe UI Semibold",
                        "alignment": "left"
                    }
                ],
                "categoryAxis": [
                    {
                        "showAxisTitle": False,
                        "fontSize": 10,
                        "labelColor": {
                            "solid": {
                                "color": "#60646B"
                            }
                        },
                        "gridlineShow": False
                    }
                ],
                "valueAxis": [
                    {
                        "showAxisTitle": False,
                        "fontSize": 10,
                        "labelColor": {
                            "solid": {
                                "color": "#60646B"
                            }
                        },
                        "gridlineColor": {
                            "solid": {
                                "color": "#EDF0F4"
                            }
                        }
                    }
                ],
                "legend": [
                    {
                        "show": True,
                        "position": "Top",
                        "showTitle": False,
                        "fontSize": 10,
                        "labelColor": {
                            "solid": {
                                "color": "#60646B"
                            }
                        }
                    }
                ],
                "labels": [
                    {
                        "fontSize": 10,
                        "color": {
                            "solid": {
                                "color": "#60646B"
                            }
                        }
                    }
                ]
            }
        },
        "card": {
            "*": {
                "labels": [
                    {
                        "fontSize": 22,
                        "fontFamily": "Segoe UI Semibold",
                        "color": {
                            "solid": {
                                "color": "#F52635"
                            }
                        }
                    }
                ],
                "categoryLabels": [
                    {
                        "show": False
                    }
                ],
                "title": [
                    {
                        "show": True,
                        "fontSize": 10,
                        "fontColor": {
                            "solid": {
                                "color": "#60646B"
                            }
                        },
                        "fontFamily": "Segoe UI",
                        "alignment": "left"
                    }
                ],
                "wordWrap": [
                    {
                        "show": False
                    }
                ]
            }
        },
        "tableEx": {
            "*": {
                "columnHeaders": [
                    {
                        "fontSize": 10,
                        "fontColor": {
                            "solid": {
                                "color": "#FFFFFF"
                            }
                        },
                        "backColor": {
                            "solid": {
                                "color": "#1D1D1B"
                            }
                        }
                    }
                ],
                "values": [
                    {
                        "fontSize": 10,
                        "fontColor": {
                            "solid": {
                                "color": "#1D1D1B"
                            }
                        },
                        "backColorPrimary": {
                            "solid": {
                                "color": "#FFFFFF"
                            }
                        },
                        "backColorSecondary": {
                            "solid": {
                                "color": "#FAFBFC"
                            }
                        }
                    }
                ],
                "grid": [
                    {
                        "gridVertical": False,
                        "outlineColor": {
                            "solid": {
                                "color": "#E2E7ED"
                            }
                        }
                    }
                ]
            }
        },
        "slicer": {
            "*": {
                "header": [
                    {
                        "fontSize": 10,
                        "fontColor": {
                            "solid": {
                                "color": "#60646B"
                            }
                        }
                    }
                ],
                "items": [
                    {
                        "fontSize": 10,
                        "fontColor": {
                            "solid": {
                                "color": "#1D1D1B"
                            }
                        }
                    }
                ]
            }
        }
    }
}


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
            "fontSize": {"expr": {"Literal": {"Value": "10D"}}},
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
            "fontSize": {"expr": {"Literal": {"Value": "10D"}}},
            "labelColor": colour(SLATE)}}])
        objects.setdefault("valueAxis", [{"properties": {
            "showAxisTitle": {"expr": {"Literal": {"Value": "false"}}},
            "fontSize": {"expr": {"Literal": {"Value": "10D"}}},
            "labelColor": colour(SLATE),
            "gridlineColor": colour(RULE)}}])
        objects.setdefault("legend", [{"properties": {
            "position": lit("Top"), "labelColor": colour(SLATE),
            "fontSize": {"expr": {"Literal": {"Value": "10D"}}},
            "showTitle": {"expr": {"Literal": {"Value": "false"}}}}}])
    if vtype == "card":
        # KPI tiles are the only warm surfaces on the page. Charts remain white
        # so their marks and labels keep their contrast.
        vc_objects["background"] = [{"properties": {
            "color": colour(TILE),
            "show": {"expr": {"Literal": {"Value": "true"}}},
            "transparency": {"expr": {"Literal": {"Value": "0D"}}}}}]
        vc_objects["border"] = [{"properties": {
            "color": colour(TILE_EDGE),
            "show": {"expr": {"Literal": {"Value": "true"}}},
            "radius": {"expr": {"Literal": {"Value": "6D"}}}}}]
        objects.setdefault("labels", [{"properties": {
            "color": colour(accent or RED),
            "fontSize": {"expr": {"Literal": {"Value": "22D"}}},
            "fontFamily": lit("Segoe UI Semibold")}}])
        objects.setdefault("categoryLabels", [{"properties": {
            "show": {"expr": {"Literal": {"Value": "false"}}}}}])
    if vtype == "tableEx":
        objects.setdefault("columnHeaders", [{"properties": {
            "fontColor": colour(PAPER), "backColor": colour(CHARCOAL),
            "fontSize": {"expr": {"Literal": {"Value": "10D"}}}}}])
        objects.setdefault("values", [{"properties": {
            "fontSize": {"expr": {"Literal": {"Value": "10D"}}},
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


def logo_visual(x=1120, y=18, w=130, h=70, z=20):
    """Embed the supplied Red & Yellow logo using Power BI's native Image visual.

    A data URI keeps the PBIP portable: the report needs no external URL or
    separate deployment step to render its brand mark.
    """
    if not LOGO.exists():
        raise SystemExit(f"Missing brand asset: {LOGO}")
    payload = base64.b64encode(LOGO.read_bytes()).decode("ascii")
    image_url = f"data:image/png;base64,{payload}"
    cfg = {
        "name": gid(),
        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": z,
                                           "width": w, "height": h}}],
        "singleVisual": {
            "visualType": "image",
            "drillFilterOtherVisuals": True,
            "objects": {"image": [{"properties": {
                "imageUrl": lit(image_url),
                "scaling": lit("Fit"),
            }}]},
            "vcObjects": {
                "background": [{"properties": {"show": {
                    "expr": {"Literal": {"Value": "false"}}}}}],
                "border": [{"properties": {"show": {
                    "expr": {"Literal": {"Value": "false"}}}}}],
            },
        },
    }
    return {"x": x, "y": y, "z": z, "width": w, "height": h,
            "config": json.dumps(cfg), "filters": "[]"}


def brand_wordmark(x=1115, y=8, w=155, h=82, z=20):
    """Native text wordmark fallback for Desktop builds where image visuals
    render as an empty placeholder instead of showing a data URI."""
    return textbox(x, y, w, h, [
        ("Red ", {"fontSize": "17pt", "fontWeight": "bold", "color": RED}),
        ("&", {"fontSize": "28pt", "fontWeight": "bold", "color": CHARCOAL}),
        (" Yellow", {"fontSize": "17pt", "fontWeight": "bold", "color": YELLOW}),
    ], z=z)


def page(name, display, ordinal, visuals):
    visuals = [*visuals, brand_wordmark()]
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
SUBB = {"fontSize": "10pt", "fontWeight": "bold", "color": "#F52635"}


def build():
    pages = []

    # ---------------------------------------------------------------- 1 ----
    cards = [("Leads", 40), ("Contacts", 240), ("Opportunities", 440),
             ("Enrolments", 640), ("Marketing Spend", 840), ("Enrolled Revenue", 1040)]
    v = [
        textbox(30, 20, 700, 44, [("Red & Yellow — marketing to enrolment", BIG)]),
        textbox(30, 66, 900, 28,
                [("What: headline funnel and geography. Why: orient demand and value. How: use Calendar year and On/off campus.", SUB)]),
    ]
    for label, x in cards:
        v.append(visual("card", x, 110, 190, 110, label,
                        {"Values": [(M, label, True)]}))
    v += [
        # Titled for what it actually plots. An earlier draft called this
        # "Funnel by stage" while charting programme category - a label that
        # would have been read as stage-to-stage conversion and quietly
        # misinformed anyone who trusted it.
        visual("clusteredBarChart", 30, 245, 610, 260,
               "Opportunities and enrolments by programme category",
               {"Category": [("dim_offering", "category", False)],
                "Y": [(M, "Opportunities", True), (M, "Enrolments", True)]}),
        visual("lineChart", 660, 245, 590, 260, "Opportunities over time",
               {"Category": [("dim_date", "month_start", False)],
                "Y": [(M, "Opportunities", True), (M, "Enrolments", True)]}),
        visual("clusteredColumnChart", 30, 520, 610, 180, "Enrolments by province",
               {"Category": [("dim_contact", "province", False)],
                "Y": [(M, "Enrolments", True)]}),
        visual("slicer", 660, 520, 290, 180, "Calendar year",
               {"Values": [("dim_date", "calendar_year", False)]}),
        visual("slicer", 960, 520, 290, 180, "On/off campus",
               {"Values": [("dim_offering", "delivery_mode", False)]}),
    ]
    pages.append(page("exec", "Executive Summary", 0, v))

    # ---------------------------------------------------------------- 2 ----
    v = [
        textbox(30, 20, 900, 40, [("Campaign performance", BIG)]),
        textbox(30, 60, 1000, 34,
                [("What: spend, response and ROAS. Why: protect budget from misleading joins. How: select Acquisition channel.", SUB)]),
        visual("card", 30, 105, 200, 100, "Marketing Spend",
               {"Values": [(M, "Marketing Spend", True)]}),
        visual("card", 240, 105, 200, 100, "Cost per Enrolment",
               {"Values": [(M, "Cost per Enrolment", True)]}),
        visual("card", 450, 105, 200, 100, "Return on Ad Spend",
               {"Values": [(M, "Return on Ad Spend", True)]}),
        visual("card", 660, 105, 190, 100, "Engagement Rate",
               {"Values": [(M, "Engagement Rate", True)]}),
        # Reach was missing entirely: the page showed what was spent and what
        # came back without the audience in between, so a poor return could not
        # be read as "few people" versus "wrong people".
        visual("card", 860, 105, 190, 100, "Campaign Reach",
               {"Values": [(M, "Campaign Reach", True)]}),
        visual("card", 1060, 105, 190, 100, "Response Rate",
               {"Values": [(M, "Response Rate", True)]}, accent=GOOD),
        visual("clusteredColumnChart", 30, 220, 480, 250, "Cost per enrolment by channel",
               {"Category": [("dim_campaign", "channel", False)],
                "Y": [(M, "Cost per Enrolment", True)]}),
        visual("clusteredColumnChart", 520, 220, 480, 250, "Return on ad spend by channel",
               {"Category": [("dim_campaign", "channel", False)],
                "Y": [(M, "Return on Ad Spend", True)]}),
        visual("slicer", 1010, 220, 240, 250, "Acquisition channel",
               {"Values": [("dim_campaign", "channel", False)]}),
        visual("tableEx", 30, 485, 1220, 215, "Campaigns",
               {"Values": [("dim_campaign", "campaign_name", False),
                           ("dim_campaign", "channel", False),
                           (M, "Campaign Members", True),
                           (M, "Responded", True),
                           (M, "Response Rate", True),
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
                [("What: admissions flow and learner health. Why: find friction and early risk. How: compare programme and week.", SUB)]),
        visual("card", 30, 105, 190, 100, "Applications",
               {"Values": [(M, "Applications", True)]}),
        visual("card", 230, 105, 190, 100, "Opportunity to Enrolment",
               {"Values": [(M, "Opportunity to Enrolment", True)]}),
        visual("card", 430, 105, 190, 100, "Avg Days to Decision",
               {"Values": [(M, "Avg Days to Decision", True)]}),
        visual("card", 630, 105, 190, 100, "At Risk Rate",
               {"Values": [(M, "At Risk Rate", True)]}),
        visual("card", 830, 105, 190, 100, "Avg Attendance",
               {"Values": [(M, "Avg Attendance", True)]}),
        visual("card", 1030, 105, 190, 100, "Students At Risk",
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
                [("What: detected data defects. Why: make trust measurable. How: filter Issue entity, then open Issue detail.", SUB)]),
        visual("card", 30, 105, 230, 100, "Quality Issues",
               {"Values": [(M, "Quality Issues", True)]}),
        visual("card", 270, 105, 230, 100, "Duplicate Contacts",
               {"Values": [(M, "Duplicate Contacts", True)]}),
        visual("card", 510, 105, 230, 100, "Duplicate Rate",
               {"Values": [(M, "Duplicate Rate", True)]}),
        visual("card", 750, 105, 230, 100, "Unresolved Provinces",
               {"Values": [(M, "Unresolved Provinces", True)]}),
        visual("slicer", 990, 105, 260, 100, "Issue entity",
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
        textbox(30, 20, 900, 40, [("Salesforce CRM - extracted", BIG)]),
        textbox(30, 60, 1060, 34,
                [("What: extracted CRM records. Why: reconcile operational truth. How: inspect deleted flags and email completeness.", SUB)]),
        visual("card", 30, 105, 190, 100, "CRM Accounts",
               {"Values": [(M, "CRM Accounts", True)]}),
        visual("card", 230, 105, 190, 100, "CRM Contacts",
               {"Values": [(M, "CRM Contacts", True)]}),
        visual("card", 430, 105, 190, 100, "CRM Leads",
               {"Values": [(M, "CRM Leads", True)]}),
        visual("card", 630, 105, 190, 100, "CRM Opportunities",
               {"Values": [(M, "CRM Opportunities", True)]}),
        visual("card", 830, 105, 190, 100, "CRM Pipeline Value",
               {"Values": [(M, "CRM Pipeline Value", True)]}),
        visual("card", 1030, 105, 190, 100, "Deleted, captured",
               {"Values": [(M, "CRM Records Deleted", True)]}, accent=SLATE),

        visual("clusteredColumnChart", 30, 220, 610, 250,
               "Opportunity pipeline by stage",
               {"Category": [("sf_opportunity", "StageName", False)],
                "Y": [(M, "CRM Opportunities", True)]}),
        visual("clusteredBarChart", 660, 220, 590, 250, "Leads by status",
               {"Category": [("sf_lead", "RY_Sample_Status__c", False)],
                "Y": [(M, "CRM Leads", True)]}),

        # The slicer that stood here bound sf_lead[LeadSource], which is empty
        # for every one of the 816 extracted records - it could only ever offer
        # "(Blank)". A filter over a field the org never populates is worse than
        # no filter: it looks like the data is missing rather than the field.
        # Two CRM data-quality figures earn the space instead.
        visual("card", 30, 485, 196, 100, "Email completeness",
               {"Values": [(M, "CRM Email Completeness", True)]}, accent=GOOD),
        visual("card", 30, 595, 196, 105, "Contacts missing email",
               {"Values": [(M, "CRM Contacts Missing Email", True)]}, accent=WARN),
        # Accounts had 115px and showed three of 25 rows, clipping the rest.
        # Stacking the two figures in a narrow left column frees the full
        # height of the band for the table.
        visual("tableEx", 236, 485, 200, 215, "Accounts",
               {"Values": [("sf_account", "Name", False)]}),
        visual("tableEx", 446, 485, 804, 215, "Contacts in the CRM",
               {"Values": [("sf_contact", "RY_External_ID__c", False),
                           ("sf_contact", "FirstName", False),
                           ("sf_contact", "LastName", False),
                           ("sf_contact", "Email", False),
                           ("sf_contact", "is_deleted", False)]}),
    ]
    pages.append(page("crm", "Salesforce CRM", 4, v))

    # ---------------------------------------------------------------- 6 ----
    v = [
        textbox(30, 20, 900, 40, [("Predictive models and recommendations", BIG)]),
        textbox(30, 60, 1080, 34,
                [("What: decision-time model scores. Why: prioritise action safely. How: compare bands before assigning a human queue.", SUB)]),

        visual("card", 30, 105, 190, 96, "Scored leads",
               {"Values": [(M, "Scored Leads", True)]}),
        visual("card", 230, 105, 190, 96, "Priority band",
               {"Values": [(M, "Priority Leads", True)]}, accent=GOOD),
        visual("card", 430, 105, 190, 96, "Actual conversion",
               {"Values": [(M, "Actual Conversion Rate", True)]}),
        visual("card", 630, 105, 190, 96, "Scored enrolments",
               {"Values": [(M, "Scored Enrolments", True)]}),
        visual("card", 830, 105, 190, 96, "To intervene",
               {"Values": [(M, "Students To Intervene", True)]}, accent=BAD),
        visual("card", 1030, 105, 190, 96, "Withdrawal rate",
               {"Values": [(M, "Actual Withdrawal Rate", True)]}),

        # The bar that matters: does the model's ranking actually separate?
        visual("clusteredColumnChart", 30, 215, 610, 250,
               "Conversion by propensity band - does the ranking separate?",
               {"Category": [("ml_lead_propensity", "propensity_band", False)],
                "Y": [(M, "Actual Conversion Rate", True)]}),
        visual("clusteredColumnChart", 660, 215, 590, 250,
               "Withdrawal rate by predicted risk band",
               {"Category": [("ml_withdrawal_risk", "risk_band", False)],
                "Y": [(M, "Actual Withdrawal Rate", True)]}),

        textbox(30, 485, 1220, 46,
                [("Marketing. ", SUBB), ("The top 5% of leads by propensity convert at 13.3%, against 2.8% in the bottom half - a 5x difference. ", SUB),
                 ("Action: Route the Priority band to human follow-up within 24 hours and leave the Low band to automated nurture. The same team covers more pipeline without more headcount.", SUBB)]),
        textbox(30, 537, 1220, 46,
                [("Channel mix. ", SUBB), ("Referral converts at 9.8% versus Walk-in at 2.2%, on 30,421 leads. ", SUB),
                 ("Action: Rebalance spend toward Referral, and either fix the qualification criteria on Walk-in or stop paying for it.", SUBB)]),
        textbox(30, 589, 1220, 46,
                [("Retention. ", SUBB), ("168 enrolments (0.1%) are flagged Elevated or Intervene from weeks 1-4 alone, and they withdraw at 45.8% against 12.5% overall. ", SUB),
                 ("Action: Trigger outreach at week 4 rather than at the first missed assessment. The signal is present before the student is far enough behind to recover from.", SUBB)]),
        textbox(30, 641, 1220, 46,
                [("Early warning. ", SUBB), ("Withdrawal rate by weeks 1-4 attendance: (0, 50] 21.4%, (50, 65] 22.4%, (65, 80] 16.4%, (80, 100] 9.1% ", SUB),
                 ("Action: Attendance below 65% in the first month is the single clearest trigger. It needs no model to act on - the model only tells you how much of the remaining population needs attention.", SUBB)]),
    ]
    pages.append(page("ml", "Predictive & Actions", 5, v))

    # ---------------------------------------------------------------- 6 ----
    # A dedicated course view makes the model actionable: the reader can rank
    # programmes by observed withdrawal and compare that signal with the
    # decision-time risk score, attendance and assessment.
    v = [
        textbox(30, 20, 900, 40, [("Course performance and early risk", BIG)]),
        textbox(30, 60, 1060, 34,
                [("What: rank courses by learner outcomes. Why: find where support is needed. How: filter delivery mode and compare actual withdrawal with the model score.", SUB)]),
        visual("card", 30, 105, 190, 96, "Scored enrolments",
               {"Values": [(M, "Scored Enrolments", True)]}),
        visual("card", 230, 105, 190, 96, "Actual withdrawal",
               {"Values": [(M, "Actual Withdrawal Rate", True)]}, accent=BAD),
        visual("card", 430, 105, 190, 96, "Predicted risk",
               {"Values": [(M, "Avg Withdrawal Risk", True)]}, accent=WARN),
        visual("card", 630, 105, 190, 96, "Avg attendance",
               {"Values": [(M, "Avg Attendance", True)]}),
        visual("card", 830, 105, 190, 96, "Avg assessment",
               {"Values": [(M, "Avg Assessment", True)]}),
        visual("card", 1030, 105, 190, 96, "To intervene",
               {"Values": [(M, "Students To Intervene", True)]}, accent=BAD),
        visual("clusteredBarChart", 30, 220, 760, 300,
               "Course withdrawal ranking (lower is better)",
               {"Category": [("ml_withdrawal_risk", "programme_title", False)],
                "Y": [(M, "Actual Withdrawal Rate", True)]}),
        visual("tableEx", 810, 220, 440, 300, "Course risk detail",
               {"Values": [("ml_withdrawal_risk", "programme_title", False),
                           ("ml_withdrawal_risk", "delivery_mode", False),
                           (M, "Actual Withdrawal Rate", True),
                           (M, "Avg Withdrawal Risk", True),
                           (M, "Avg Attendance", True),
                           (M, "Avg Assessment", True)]}),
        visual("slicer", 30, 545, 300, 125, "Delivery mode",
               {"Values": [("ml_withdrawal_risk", "delivery_mode", False)]}),
        textbox(350, 545, 900, 125,
                [("How to act. ", SUBB),
                 ("Treat Elevated risk or first-month attendance below 65% as a human-review queue. Start with the highest-withdrawal courses, check cohort size and delivery mode, offer support, and measure withdrawal after intervention. The synthetic model ranks risk; it does not make an automated student decision.", SUB)]),
    ]
    pages.append(page("course", "Course Risk Ranking", 6, v))

    # ---------------------------------------------------------------- 7 ----
    v = [
        textbox(30, 20, 900, 40, [("Marketing analytics", BIG)]),
        textbox(30, 60, 1040, 34,
                [("What: reach through revenue. Why: choose the next rand. How: select Acquisition channel and read the scorecard.", SUB)]),
        visual("card", 30, 105, 190, 100, "Campaign Reach",
               {"Values": [(M, "Campaign Reach", True)]}),
        visual("card", 230, 105, 190, 100, "Responded",
               {"Values": [(M, "Responded", True)]}),
        visual("card", 430, 105, 190, 100, "Response Rate",
               {"Values": [(M, "Response Rate", True)]}, accent=GOOD),
        visual("card", 630, 105, 190, 100, "Marketing Enrolment Rate",
               {"Values": [(M, "Marketing Enrolment Rate", True)]}, accent=GOOD),
        visual("card", 830, 105, 190, 100, "Spend per Response",
               {"Values": [(M, "Spend per Response", True)]}),
        visual("card", 1030, 105, 190, 100, "Revenue per Member",
               {"Values": [(M, "Revenue per Member", True)]}),
        visual("clusteredColumnChart", 30, 220, 480, 250,
               "Responses and enrolments by channel",
               {"Category": [("dim_campaign", "channel", False)],
                "Y": [(M, "Responded", True), (M, "Campaign Enrolments", True)]}),
        visual("clusteredColumnChart", 520, 220, 480, 250,
               "Revenue per member by channel",
               {"Category": [("dim_campaign", "channel", False)],
                "Y": [(M, "Revenue per Member", True)]}),
        visual("slicer", 1010, 220, 240, 250, "Acquisition channel",
               {"Values": [("dim_campaign", "channel", False)]}),
        visual("tableEx", 30, 485, 1220, 215, "Channel scorecard",
               {"Values": [("dim_campaign", "channel", False),
                           (M, "Campaign Reach", True),
                           (M, "Response Rate", True),
                           (M, "Marketing Enrolment Rate", True),
                           (M, "Marketing Spend", True),
                           (M, "Spend per Response", True),
                           (M, "Cost per Enrolment", True),
                           (M, "Return on Ad Spend", True),
                           (M, "Revenue per Member", True)]}),
    ]
    pages.append(page("marketing", "Marketing Analytics", 7, v))

    # ---------------------------------------------------------------- 8 ----
    # Turn the findings into an operating plan. Every recommendation names the
    # intervention and the measure that should move.
    v = [
        textbox(30, 20, 900, 40, [("Recommendations & solutions", BIG)]),
        textbox(30, 60, 1080, 34,
                [("What: actions and owners. Why: turn a signal into change. How: follow the 90-day rollout and measure outcomes.", SUB)]),
        visual("card", 30, 105, 190, 96, "Priority leads",
               {"Values": [(M, "Priority Leads", True)]}, accent=GOOD),
        visual("card", 230, 105, 190, 96, "Conversion rate",
               {"Values": [(M, "Actual Conversion Rate", True)]}),
        visual("card", 430, 105, 190, 96, "Email completeness",
               {"Values": [(M, "CRM Email Completeness", True)]}, accent=GOOD),
        visual("card", 630, 105, 190, 96, "Withdrawal rate",
               {"Values": [(M, "Actual Withdrawal Rate", True)]}, accent=BAD),
        visual("card", 830, 105, 190, 96, "Duplicate rate",
               {"Values": [(M, "Duplicate Rate", True)]}, accent=WARN),
        visual("card", 1030, 105, 190, 96, "Enrolment rate",
               {"Values": [(M, "Marketing Enrolment Rate", True)]}, accent=GOOD),

        textbox(30, 225, 295, 145,
                [("1  Acquire efficiently\n", {"fontSize": "13pt", "fontWeight": "bold", "color": RED}),
                 ("Shift the next test budget toward the channels with the strongest response, enrolment rate and revenue per member. Put a stop rule on channels that spend without converting.\n\nOwner: Marketing | Measure: ROAS, spend per response, revenue per member", SUB)]),
        textbox(340, 225, 295, 145,
                [("2  Convert faster\n", {"fontSize": "13pt", "fontWeight": "bold", "color": RED}),
                 ("Route Priority leads to a named human queue within 24 hours. Keep Low-band leads in automated nurture so the team spends its scarce call time where the ranking separates.\n\nOwner: Admissions | Measure: response SLA, conversion rate, top-band lift", SUB)]),
        textbox(650, 225, 295, 145,
                [("3  Retain earlier\n", {"fontSize": "13pt", "fontWeight": "bold", "color": RED}),
                 ("Trigger a support conversation when first-month attendance falls below 65% or the risk band reaches Elevated. Record the intervention and compare withdrawal outcomes with the prior cohort.\n\nOwner: Student success | Measure: week-4 attendance, withdrawal rate", SUB)]),
        textbox(960, 225, 290, 145,
                [("4  Repair the data loop\n", {"fontSize": "13pt", "fontWeight": "bold", "color": RED}),
                 ("Make email, external IDs and campaign membership required at capture; send exceptions to a daily queue. Keep unknown prices as unknown and never turn them into zero.\n\nOwner: CRM + Data | Measure: completeness, duplicate rate, unresolved issues", SUB)]),

        textbox(30, 405, 1220, 34, [("90-day rollout", {"fontSize": "16pt", "fontWeight": "bold", "color": CHARCOAL})]),
        textbox(30, 450, 390, 210,
                [("Days 0-30 | Stabilise\n", {"fontSize": "13pt", "fontWeight": "bold", "color": RED}),
                 ("Confirm the CRM field rules, remove blank-only filters, assign the Priority lead queue, and baseline the six KPI cards.\n\nSuccess: no blank-bound slicers, a named owner for each queue, and a refresh that passes the dbt quality gate.", SUB)]),
        textbox(445, 450, 390, 210,
                [("Days 31-60 | Test\n", {"fontSize": "13pt", "fontWeight": "bold", "color": RED}),
                 ("Run channel and follow-up experiments with holdout groups. Compare Referral and Walk-in qualification, and log every student-support intervention from week 1.\n\nSuccess: measured lift in response or conversion, with spend and cohort definitions unchanged.", SUB)]),
        textbox(860, 450, 390, 210,
                [("Days 61-90 | Scale\n", {"fontSize": "13pt", "fontWeight": "bold", "color": RED}),
                 ("Promote only interventions that beat the baseline, publish the weekly action list, and monitor model drift and data quality by delivery mode and channel.\n\nSuccess: repeatable operating cadence, documented decisions, and no automated adverse action from a model score.", SUB)]),
    ]
    pages.append(page("actions", "Recommendations & Solutions", 8, v))

    # ---------------------------------------------------------------- 10 ----
    v = [
        textbox(30, 20, 900, 40, [("BA & SA improvement backlog", BIG)]),
        textbox(30, 60, 1060, 34,
                [("What: translate website and platform findings into delivery work. Why: remove ambiguity at the business and system boundaries. How: assign owners, acceptance evidence and release gates.", SUB)]),
        visual("card", 30, 105, 190, 96, "Leads",
               {"Values": [(M, "Leads", True)]}),
        visual("card", 230, 105, 190, 96, "Funnel conversion",
               {"Values": [(M, "Opportunity to Enrolment", True)]}),
        visual("card", 430, 105, 190, 96, "Email completeness",
               {"Values": [(M, "CRM Email Completeness", True)]}, accent=GOOD),
        visual("card", 630, 105, 190, 96, "At-risk rate",
               {"Values": [(M, "At Risk Rate", True)]}, accent=WARN),
        visual("card", 830, 105, 190, 96, "Marketing spend",
               {"Values": [(M, "Marketing Spend", True)]}),
        visual("card", 1030, 105, 190, 96, "Withdrawal rate",
               {"Values": [(M, "Actual Withdrawal Rate", True)]}, accent=BAD),
        textbox(30, 225, 590, 220,
                [("Business analysis improvements\n", {"fontSize": "15pt", "fontWeight": "bold", "color": RED}),
                 ("Define one catalogue and KPI dictionary for on-campus and online delivery; label every metric with source system and as-of date; agree funnel denominators and attribution; and turn each signal into a user story with an owner, SLA and outcome measure. Website evidence to prioritise: non-200 sitemap URLs, missing metadata, unclear price status and broken application paths.", SUB)]),
        textbox(660, 225, 590, 220,
                [("Systems analysis improvements\n", {"fontSize": "15pt", "fontWeight": "bold", "color": RED}),
                 ("Choose the GA4 Data API or native BigQuery route deliberately; keep analytics identifiers separate from CRM external IDs; add watermarks, run IDs, rejects, retries and replay paths to NiFi/Fabric; enforce metadata and structured-data controls by page template; and document model version, drift checks and human review for dropout-risk actions.", SUB)]),
        textbox(30, 480, 1220, 190,
                [("Release gates\n", {"fontSize": "15pt", "fontWeight": "bold", "color": RED}),
                 ("Now: repair or approve non-200 sitemap entries, publish source-of-truth definitions, remove blank-only slicers and finish Fabric SQL compatibility. Next: activate the selected GA4 route, add ingestion observability and template SEO controls. Then: connect website campaign events to CRM attribution and pilot course-risk interventions with measured outcomes. These are recommendations from the analysed website and platform evidence; they are not claims that production website changes have already shipped.", SUB)]),
    ]
    pages.append(page("ba_sa", "BA & SA Improvements", 9, v))

    return {
        "id": 0,
        # The theme has to be registered as a resource AND named in the config.
        # Setting colours per visual does not work: Power BI resolves marks from
        # the active theme, so a report shipped without one renders in whatever
        # theme the person opening it happens to have - which is why the first
        # build came out in default blue despite every visual specifying red.
        "resourcePackages": [{
            "resourcePackage": {
                "disabled": False,
                "items": [{"name": "RedAndYellow",
                           "path": "StaticResources/RegisteredResources/"
                                   "RedAndYellow.json",
                           "type": 202}],
                "name": "SharedResources",
                "type": 2,
            }
        }],
        "sections": pages,
        "config": json.dumps({
            "version": "5.43",
            "themeCollection": {
                "baseTheme": {"name": "CY24SU06", "version": "5.55", "type": 2},
                "customTheme": {"name": "RedAndYellow",
                                "reportVersionAtImport": "5.43", "type": 2},
            },
            "activeSectionIndex": 0,
            "defaultDrillFilterOtherVisuals": True,
            "settings": {"useStylableVisualContainerHeader": True},
        }),
        "layoutOptimization": 0,
    }


def validate_layout(report):
    """Reject accidental off-canvas or overlapping visuals before Desktop sees them."""
    problems = []
    for sec in report["sections"]:
        rects = []
        for idx, vc in enumerate(sec["visualContainers"], start=1):
            x, y, w, h = (vc["x"], vc["y"], vc["width"], vc["height"])
            if x < 0 or y < 0 or x + w > W or y + h > H:
                problems.append(
                    f"{sec['displayName']}: visual {idx} is outside the {W}x{H} canvas")
            for other_idx, ox, oy, ow, oh in rects:
                if max(x, ox) < min(x + w, ox + ow) and max(y, oy) < min(y + h, oy + oh):
                    problems.append(
                        f"{sec['displayName']}: visuals {other_idx} and {idx} overlap")
            rects.append((idx, x, y, w, h))
    return problems

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

    layout_problems = validate_layout(report)
    if layout_problems:
        print("REPORT NOT WRITTEN - layout validation failed:")
        for problem in layout_problems:
            print(f"  - {problem}")
        raise SystemExit(1)

    if problems:
        print("REPORT NOT WRITTEN - field references do not resolve:")
        for p in problems:
            print("  -", p)
        raise SystemExit(1)

    RPT.mkdir(parents=True, exist_ok=True)

    # Power BI Desktop UPGRADES a legacy project on save: it writes
    # definition/pages/<section>/visuals/<visual>.json, sets definition.pbir to
    # version 4.0, and DELETES report.json. After that it reads only the folder
    # format, so regenerating report.json changes nothing on screen - which is
    # exactly what happened: five rebuilds, none of them visible.
    #
    # So the generator now clears the upgraded artefacts and re-asserts the
    # legacy format it owns. Anything Desktop added by hand is discarded, which
    # is correct here: this report is generated, not hand-edited.
    import shutil as _sh
    for stale in ("definition", ".pbi", ".platform"):
        target = RPT / stale
        if target.is_dir():
            _sh.rmtree(target)
            print(f"  removed Desktop-upgraded {stale}/")
        elif target.exists():
            target.unlink()
            print(f"  removed Desktop-upgraded {stale}")

    (RPT / "definition.pbir").write_text(
        '{\n  "version": "1.0",\n'
        '  "datasetReference": {\n'
        '    "byPath": { "path": "../RedAndYellow.SemanticModel" }\n'
        '  }\n}\n', encoding="utf-8")

    # The theme is written here, not once by hand: Desktop's upgrade carried
    # StaticResources away with it, and a report that names a theme it does not
    # ship renders in Power BI's default blue - which is precisely the symptom
    # that took several rebuilds to explain.
    theme_dir = RPT / "StaticResources" / "RegisteredResources"
    theme_dir.mkdir(parents=True, exist_ok=True)
    (theme_dir / "RedAndYellow.json").write_text(json.dumps(THEME, indent=2),
                                                 encoding="utf-8")

    (RPT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    n_vis = sum(len(s["visualContainers"]) for s in report["sections"])
    print(f"wrote {RPT / 'report.json'}")
    print(f"  {len(report['sections'])} pages, {n_vis} visuals")
    print(f"  {checked} field references and page layout checked, all resolve")
    for s in report["sections"]:
        print(f"    {s['ordinal'] + 1}. {s['displayName']:<26}"
              f"{len(s['visualContainers'])} visuals")


if __name__ == "__main__":
    main()
