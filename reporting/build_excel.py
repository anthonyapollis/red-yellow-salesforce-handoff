#!/usr/bin/env python3
"""Builds the Red & Yellow analytics workbook from the dbt marts.

One workbook, eight sheets, native Excel charts (not pasted images) so every
number stays traceable to the cell it came from and the reader can re-sort and
re-filter without asking anyone to regenerate anything.

    python build_excel.py
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
import xlsxwriter

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "warehouse" / "redandyellow.duckdb"
OUT = REPO / "reporting" / "RedAndYellow_Analytics.xlsx"

# Red & Yellow's own identity, used sparingly: red for emphasis, yellow for
# highlight, charcoal for text. Charts stay on a muted categorical ramp so a
# ten-series chart does not turn into a warning light.
RED = "#E03127"
YELLOW = "#FFC629"
CHARCOAL = "#22252A"
SLATE = "#5A6472"
PAPER = "#FFFFFF"
RULE = "#D8DDE4"
SERIES = ["#E03127", "#F0A202", "#2E6E8E", "#4C9F70", "#8B5FBF",
          "#C7522A", "#3B7EA1", "#7A8B99", "#D4A03C", "#5C6F52", "#9E4A4A"]


def q(con, sql):
    return con.sql(sql).df()


def main():
    if not DB.exists():
        raise SystemExit(f"warehouse not built ({DB}) - run generate.py then dbt run")

    con = duckdb.connect(str(DB), read_only=True)
    truth = json.loads((REPO / "warehouse" / "_truth" / "defects.json").read_text())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(str(OUT), {"nan_inf_to_errors": True})

    # -- formats ------------------------------------------------------------
    f = dict(
        title=wb.add_format({"font_size": 22, "bold": True, "font_color": CHARCOAL,
                             "font_name": "Calibri"}),
        sub=wb.add_format({"font_size": 11, "font_color": SLATE, "font_name": "Calibri"}),
        h2=wb.add_format({"font_size": 13, "bold": True, "font_color": CHARCOAL,
                          "bottom": 1, "border_color": RULE}),
        hdr=wb.add_format({"bold": True, "font_color": PAPER, "bg_color": CHARCOAL,
                           "align": "left", "valign": "vcenter", "text_wrap": True,
                           "border": 1, "border_color": CHARCOAL}),
        cell=wb.add_format({"border": 1, "border_color": RULE}),
        num=wb.add_format({"num_format": "#,##0", "border": 1, "border_color": RULE}),
        money=wb.add_format({"num_format": "R #,##0", "border": 1, "border_color": RULE}),
        pct=wb.add_format({"num_format": "0.0%", "border": 1, "border_color": RULE}),
        dec=wb.add_format({"num_format": "0.00", "border": 1, "border_color": RULE}),
        kpi_v=wb.add_format({"font_size": 26, "bold": True, "font_color": RED,
                             "align": "center", "valign": "vcenter"}),
        kpi_l=wb.add_format({"font_size": 10, "font_color": SLATE, "align": "center",
                             "valign": "top", "text_wrap": True}),
        kpi_box=wb.add_format({"bg_color": "#FBFBFC", "border": 1, "border_color": RULE}),
        note=wb.add_format({"font_size": 10, "font_color": SLATE, "italic": True,
                            "text_wrap": True, "valign": "top"}),
        warn=wb.add_format({"font_size": 10, "font_color": CHARCOAL, "bg_color": "#FFF6D6",
                            "text_wrap": True, "valign": "top", "border": 1,
                            "border_color": YELLOW}),
    )

    def table(ws, df, row, col, fmts=None, width=None):
        """Write a dataframe as a bordered table and return the row after it."""
        for j, name in enumerate(df.columns):
            ws.write(row, col + j, name.replace("_", " "), f["hdr"])
        for i, rec in enumerate(df.itertuples(index=False), start=1):
            for j, v in enumerate(rec):
                fmt = (fmts or {}).get(df.columns[j], f["cell"])
                if pd.isna(v):
                    ws.write_blank(row + i, col + j, None, fmt)
                elif isinstance(v, (pd.Timestamp, datetime)):
                    ws.write(row + i, col + j, v.strftime("%Y-%m-%d"), fmt)
                else:
                    ws.write(row + i, col + j, v, fmt)
        for j, name in enumerate(df.columns):
            ws.set_column(col + j, col + j, (width or {}).get(name, max(12, len(name) + 3)))
        ws.set_row(row, 30)
        return row + len(df) + 1

    # ==================================================================== 1 ==
    ws = wb.add_worksheet("Executive Summary")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 2)
    ws.write("B2", "Red & Yellow", f["title"])
    ws.write("B3", "CRM & Academic Analytics - marketing spend through to student outcomes",
             f["sub"])
    ws.write("B4", f"Generated {datetime.now():%d %B %Y} from the dbt warehouse. "
                   f"Catalogue is real; all people and campaigns are synthetic.", f["sub"])

    kpis = q(con, """
        select
          (select count(*) from main_staging.stg_lead)                       as leads,
          (select count(*) from main_marts.dim_contact)                      as contacts,
          (select count(*) from main_marts.fct_admissions_funnel)            as opportunities,
          (select sum(is_enrolled) from main_marts.fct_admissions_funnel)    as enrolments,
          (select sum(spend_zar) from main_marts.dim_campaign)               as spend,
          (select sum(agreed_fee_zar) from main_staging.stg_enrolment)       as revenue,
          (select count(*) from main_quality.dq_issue_log)                   as dq_issues
    """).iloc[0]

    tiles = [
        ("Leads", f"{kpis.leads:,.0f}", "captured across 4 years"),
        ("Contacts", f"{kpis.contacts:,.0f}", "after de-duplication"),
        ("Opportunities", f"{kpis.opportunities:,.0f}", "admissions pipeline"),
        ("Enrolments", f"{kpis.enrolments:,.0f}", "converted to study"),
        ("Marketing spend", f"R{kpis.spend/1e6:,.0f}m", "all campaigns"),
        ("Enrolled revenue", f"R{kpis.revenue/1e6:,.0f}m", "agreed fees"),
    ]
    r = 6
    for i, (label, value, sub) in enumerate(tiles):
        c = 1 + (i % 3) * 3
        rr = r + (i // 3) * 4
        ws.merge_range(rr, c, rr + 1, c + 2, value, f["kpi_v"])
        ws.merge_range(rr + 2, c, rr + 2, c + 2, f"{label} - {sub}", f["kpi_l"])
        ws.conditional_format(rr, c, rr + 2, c + 2,
                              {"type": "no_errors", "format": f["kpi_box"]})

    ws.write(r + 9, 1, "Conversion through the funnel", f["h2"])
    funnel = q(con, """
        select 'Leads' as stage, count(*) as records, 1 as ord from main_staging.stg_lead
        union all select 'Contacts', count(*), 2 from main_marts.dim_contact
        union all select 'Opportunities', count(*), 3 from main_marts.fct_admissions_funnel
        union all select 'Applications', count(*), 4 from main_staging.stg_application
        union all select 'Enrolments', count(*), 5 from main_staging.stg_enrolment
        order by ord
    """)[["stage", "records"]]
    end = table(ws, funnel, r + 10, 1, {"records": f["num"]})

    ch = wb.add_chart({"type": "bar"})
    ch.add_series({
        "name": "Records",
        "categories": ["Executive Summary", r + 11, 1, r + 10 + len(funnel), 1],
        "values": ["Executive Summary", r + 11, 2, r + 10 + len(funnel), 2],
        "fill": {"color": RED}, "gap": 45,
    })
    ch.set_title({"name": "Marketing to enrolment"})
    ch.set_legend({"none": True})
    ch.set_size({"width": 520, "height": 300})
    ws.insert_chart(r + 10, 5, ch)

    ws.merge_range(end + 1, 1, end + 3, 8,
                   "Read the funnel as stages, not as a single cohort. Leads and contacts "
                   "overlap - a converted lead becomes a contact - so the drop between them "
                   "is not attrition. Opportunity-to-enrolment is the honest conversion rate.",
                   f["note"])

    # ==================================================================== 2 ==
    ws = wb.add_worksheet("Campaign Performance")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 2)
    ws.write("B2", "Campaign performance by channel", f["title"])
    ws.write("B3", "Spend is aggregated at campaign grain before joining to enrolments, "
                   "so a campaign's cost is never multiplied by its downstream row count.",
             f["sub"])

    chan = q(con, """
        select channel,
               count(*)                          as campaigns,
               sum(members)                      as members,
               sum(opportunities)                as opportunities,
               sum(enrolments)                   as enrolments,
               round(sum(spend_zar))             as spend_zar,
               round(sum(enrolled_revenue_zar))  as revenue_zar,
               round(sum(spend_zar) / nullif(sum(enrolments), 0)) as cost_per_enrolment,
               round(sum(enrolled_revenue_zar) / nullif(sum(spend_zar), 0), 2) as roas
        from main_marts.fct_campaign_performance
        group by 1 order by roas desc nulls last
    """)
    end = table(ws, chan, 5, 1,
                {"campaigns": f["num"], "members": f["num"], "opportunities": f["num"],
                 "enrolments": f["num"], "spend_zar": f["money"], "revenue_zar": f["money"],
                 "cost_per_enrolment": f["money"], "roas": f["dec"]},
                {"channel": 18})

    c1 = wb.add_chart({"type": "column"})
    c1.add_series({"name": "Cost per enrolment (R)",
                   "categories": ["Campaign Performance", 6, 1, 5 + len(chan), 1],
                   "values": ["Campaign Performance", 6, 8, 5 + len(chan), 8],
                   "fill": {"color": SERIES[2]}, "gap": 40})
    c1.set_title({"name": "Cost per enrolment by channel"})
    c1.set_legend({"none": True})
    c1.set_y_axis({"num_format": "R #,##0"})
    c1.set_size({"width": 560, "height": 300})
    ws.insert_chart(end + 2, 1, c1)

    c2 = wb.add_chart({"type": "column"})
    c2.add_series({"name": "Return on ad spend",
                   "categories": ["Campaign Performance", 6, 1, 5 + len(chan), 1],
                   "values": ["Campaign Performance", 6, 9, 5 + len(chan), 9],
                   "fill": {"color": SERIES[3]}, "gap": 40})
    c2.set_title({"name": "Return on ad spend by channel"})
    c2.set_legend({"none": True})
    c2.set_size({"width": 560, "height": 300})
    ws.insert_chart(end + 2, 11, c2)

    # ==================================================================== 3 ==
    ws = wb.add_worksheet("Programme Demand")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 2)
    ws.write("B2", "Programme demand", f["title"])
    ws.write("B3", "Against the 83 real programmes and 89 real offerings transcribed "
                   "from the Red & Yellow catalogue.", f["sub"])

    prog = q(con, """
        select d.programme_title, d.category, d.delivery_mode,
               d.advertised_fee_zar,
               count(*)                            as opportunities,
               sum(f.is_enrolled)                  as enrolments,
               round(avg(f.discount_pct), 1)       as avg_discount_pct,
               round(sum(f.agreed_fee_zar))        as revenue_zar
        from main_marts.fct_admissions_funnel f
        join main_marts.dim_offering d using (offering_external_id)
        group by 1,2,3,4
        having count(*) > 0
        order by enrolments desc
        limit 30
    """)
    end = table(ws, prog, 5, 1,
                {"advertised_fee_zar": f["money"], "opportunities": f["num"],
                 "enrolments": f["num"], "avg_discount_pct": f["dec"],
                 "revenue_zar": f["money"]},
                {"programme_title": 46, "category": 22, "delivery_mode": 16})

    ws.merge_range(end + 1, 1, end + 3, 8,
                   "Offerings priced 'Enquire' carry a blank advertised fee. That blank is "
                   "the catalogue's real state, not a gap in the data - it is never "
                   "substituted with zero, which would understate average price.", f["warn"])

    # ==================================================================== 4 ==
    ws = wb.add_worksheet("Student Risk")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 2)
    ws.write("B2", "Student success and early warning", f["title"])
    ws.write("B3", "At risk = attendance under 55%, or assessment average under 50%, "
                   "or three or more overdue assignments.", f["sub"])

    risk = q(con, """
        select week_number,
               count(*)                                        as students_tracked,
               sum(is_at_risk)                                 as at_risk,
               round(100.0 * sum(is_at_risk) / count(*), 1)    as at_risk_pct,
               round(avg(attendance_pct), 1)                   as avg_attendance_pct,
               round(avg(assessment_average_pct), 1)           as avg_assessment_pct
        from main_marts.fct_student_progress_weekly
        group by 1 order by 1
    """)
    end = table(ws, risk, 5, 1,
                {"students_tracked": f["num"], "at_risk": f["num"],
                 "at_risk_pct": f["dec"], "avg_attendance_pct": f["dec"],
                 "avg_assessment_pct": f["dec"]})

    c3 = wb.add_chart({"type": "line"})
    for i, (colname, colidx) in enumerate([("Avg attendance %", 5), ("Avg assessment %", 6)]):
        c3.add_series({"name": colname,
                       "categories": ["Student Risk", 6, 1, 5 + len(risk), 1],
                       "values": ["Student Risk", 6, colidx, 5 + len(risk), colidx],
                       "line": {"color": SERIES[i], "width": 2.25}})
    c3.set_title({"name": "Academic health over the study weeks"})
    c3.set_x_axis({"name": "Week of study"})
    c3.set_size({"width": 620, "height": 320})
    ws.insert_chart(end + 2, 1, c3)

    # ==================================================================== 5 ==
    ws = wb.add_worksheet("Data Quality")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 2)
    ws.write("B2", "Data quality", f["title"])
    ws.write("B3", "Defects were injected into the source data on purpose and recorded in a "
                   "ground-truth manifest. These counts are what the pipeline caught, "
                   "measured against what was planted.", f["sub"])

    dq = q(con, """
        select entity, issue_code, issue_description, issue_count
        from main_quality.dq_summary order by issue_count desc
    """)
    end = table(ws, dq, 5, 1, {"issue_count": f["num"]},
                {"issue_description": 58, "issue_code": 24, "entity": 18})

    c4 = wb.add_chart({"type": "bar"})
    c4.add_series({"name": "Records affected",
                   "categories": ["Data Quality", 6, 2, 5 + len(dq), 2],
                   "values": ["Data Quality", 6, 4, 5 + len(dq), 4],
                   "fill": {"color": SERIES[5]}, "gap": 40})
    c4.set_title({"name": "Detected issues by type"})
    c4.set_legend({"none": True})
    c4.set_size({"width": 620, "height": 380})
    ws.insert_chart(end + 2, 1, c4)

    inj = pd.DataFrame(sorted(truth["injected_defect_counts"].items()),
                       columns=["injected_defect", "records"])
    table(ws, inj, 5, 7, {"records": f["num"]}, {"injected_defect": 26})

    # ==================================================================== 5b =
    # Detection scored against the ground truth, rather than asserted.
    ws = wb.add_worksheet("DQ Scorecard")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 2)
    ws.write("B2", "Data quality: detected against injected", f["title"])
    ws.write("B3", "Defects were planted at recorded rates. Recall is what the "
                   "pipeline found, divided by what was planted - a measurement, "
                   "not a claim.", f["sub"])

    inj_counts = truth["injected_defect_counts"]
    det = {r.issue_code: r.issue_count for r in
           q(con, "select issue_code, issue_count from main_quality.dq_summary").itertuples()}
    pairs = [("Duplicate humans", "duplicate_person", "duplicate_person"),
             ("Missing attendance", "attendance_missing", "attendance_missing"),
             ("Duplicate campaign membership", "dup_campaign_member", "duplicate_membership"),
             ("Date inversions", "date_inversion", "date_inversion"),
             ("Negative values", "negative_fee", "negative_value")]
    rows = []
    for label, ikey, dkey in pairs:
        i, dd = inj_counts.get(ikey), det.get(dkey)
        if i and dd is not None:
            rows.append({"defect": label, "injected": i, "detected": dd,
                         "recall": round(dd / i, 3)})
    sc = pd.DataFrame(rows)
    end = table(ws, sc, 5, 1, {"injected": f["num"], "detected": f["num"],
                               "recall": f["dec"]}, {"defect": 34})
    ws.merge_range(end + 1, 1, end + 3, 6,
                   "Recall above 1.0 means the pipeline flagged more than was "
                   "planted - de-duplication also catches collisions that arose "
                   "naturally. Below 1.0 means some defects are unrecoverable: "
                   "a duplicate whose email and phone were both dropped cannot "
                   "be matched to anything.", f["note"])

    # ==================================================================== 5c =
    # The live CRM slice, read back out of Salesforce through the API.
    sf_dir = REPO / "warehouse" / "salesforce_raw"
    if (sf_dir / "contact.parquet").exists():
        ws = wb.add_worksheet("Salesforce CRM")
        ws.hide_gridlines(2)
        ws.set_column("A:A", 2)
        ws.write("B2", "Salesforce CRM - extracted via API", f["title"])
        ws.write("B3", "Pulled from the org with SOQL over REST on a "
                       "SystemModstamp watermark. Deleted records are retained "
                       "and flagged, so removals stay visible.", f["sub"])

        summary = []
        for name in ["account", "contact", "lead", "opportunity"]:
            p = sf_dir / f"{name}.parquet"
            if not p.exists():
                continue
            dfx = pd.read_parquet(p)
            deleted = int(dfx["is_deleted"].sum()) if "is_deleted" in dfx else 0
            summary.append({"object": name.title(), "rows_extracted": len(dfx),
                            "live_in_org": len(dfx) - deleted,
                            "deleted_captured": deleted})
        end = table(ws, pd.DataFrame(summary), 5, 1,
                    {"rows_extracted": f["num"], "live_in_org": f["num"],
                     "deleted_captured": f["num"]}, {"object": 16})

        cdf = pd.read_parquet(sf_dir / "contact.parquet")
        live = cdf[~cdf["is_deleted"]] if "is_deleted" in cdf else cdf
        cols = [c for c in ["RY_External_ID__c", "FirstName", "LastName",
                            "Email", "Id", "extracted_at"] if c in live.columns]
        table(ws, live[cols].head(300).reset_index(drop=True), end + 2, 1, {},
              {"Email": 34, "RY_External_ID__c": 22, "Id": 20,
               "extracted_at": 24})

    # ==================================================================== 5d =
    mlp = REPO / "warehouse" / "ml"
    if (mlp / "model_report.json").exists():
        rep = json.loads((mlp / "model_report.json").read_text(encoding="utf-8"))
        ws = wb.add_worksheet("Predictive Models")
        ws.hide_gridlines(2)
        ws.set_column("A:A", 2)
        ws.write("B2", "Predictive models", f["title"])
        ws.write("B3", "Split by time, not at random. Features restricted to "
                       "what is known at decision time. Metrics shown against "
                       "the base rate, because an AUC means nothing without it.",
                 f["sub"])

        mdf = pd.DataFrame([{"model": m["model"], "train_rows": m["train_rows"],
                             "test_rows": m["test_rows"], "base_rate": m["base_rate"],
                             "auc": m["auc"], "pr_auc": m["pr_auc"],
                             "top_decile_lift": m["top_decile_lift"]}
                            for m in rep["models"]])
        end = table(ws, mdf, 5, 1,
                    {"train_rows": f["num"], "test_rows": f["num"],
                     "base_rate": f["dec"], "auc": f["dec"], "pr_auc": f["dec"],
                     "top_decile_lift": f["dec"]}, {"model": 34})

        ws.write(end + 1, 1, "Feature importance", f["h2"])
        rows = []
        for m in rep["models"]:
            for ft in m["features"][:8]:
                rows.append({"model": m["model"], "feature": ft["feature"],
                             "share_of_gain": ft["share"]})
        end = table(ws, pd.DataFrame(rows), end + 2, 1,
                    {"share_of_gain": f["dec"]}, {"model": 34, "feature": 24})

        ws.write(end + 1, 1, "Recommendations", f["h2"])
        ins = pd.DataFrame(rep.get("insights", []))
        if not ins.empty:
            end = table(ws, ins[["area", "finding", "recommendation"]], end + 2, 1,
                        {}, {"area": 16, "finding": 62, "recommendation": 62})
        ws.merge_range(end + 1, 1, end + 3, 6,
                       "An AUC in the mid-0.6s is the honest result for human "
                       "decisions with this much unexplained variation. A model "
                       "claiming 0.95 here would mean a feature had leaked. The "
                       "lift is the number to act on.", f["warn"])

    # ==================================================================== 6 ==
    ws = wb.add_worksheet("Catalogue")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 2)
    ws.write("B2", "Programme catalogue (real)", f["title"])
    ws.write("B3", "83 programme identities, 89 offerings, 47 dated intakes, transcribed "
                   "from 17 screenshots of the public site on 8 September 2026.", f["sub"])
    cat = q(con, """
        select programme_title, category, delivery_mode, study_pace,
               duration_value, duration_unit, advertised_fee_zar, price_status,
               dated_intake_count
        from main_marts.dim_offering order by programme_title
    """)
    table(ws, cat, 5, 1, {"advertised_fee_zar": f["money"], "dated_intake_count": f["num"],
                          "duration_value": f["num"]},
          {"programme_title": 52, "category": 24, "delivery_mode": 16, "study_pace": 14})

    # ==================================================================== 7 ==
    ws = wb.add_worksheet("Method & Caveats")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 2)
    ws.set_column("B:B", 110)
    ws.write("B2", "Method and caveats", f["title"])
    notes = [
        ("What is real", "The programme catalogue: 83 programmes, 89 offerings, 47 dated "
         "intakes and their advertised fees, transcribed from the public Red & Yellow site. "
         "Nothing here is an export from Red & Yellow's own systems."),
        ("What is synthetic", "Every person, campaign, application, enrolment and progress "
         "record. Names are drawn from a South African distribution and all email addresses "
         "resolve to example-style consumer domains. No real individual is represented."),
        ("Why the data is dirty", "Defects are injected deliberately at known rates - "
         "duplicate humans, phone-format drift, invalid emails, province spelling variants, "
         "inverted dates, late-arriving records - and recorded in a manifest so the "
         "pipeline's detection can be measured rather than asserted."),
        ("Blanks that are not gaps", "Offerings priced 'Enquire for price' carry a null fee "
         "and a price status of Enquire. Clipped or unseen values in the source screenshots "
         "stay blank. Neither is ever filled with zero."),
        ("Spend attribution", "Campaign spend is aggregated at campaign grain before it "
         "meets enrolment rows. Joining spend to a fact table first would multiply each "
         "campaign's cost by its downstream row count."),
        ("Salesforce scope", "The CRM holds a referentially complete slice of a few thousand "
         "records, not the full warehouse. Salesforce charges storage per record and a "
         "Developer org holds roughly ten thousand records in total; volume belongs in the "
         "warehouse, which is where this design puts it."),
        ("Lineage", "Sources land in a raw layer, are cleansed once in staging, and are "
         "consumed by marts that assume clean inputs. Every integrated record carries its "
         "source system, source id, source update time, load time and deletion flag."),
    ]
    r = 4
    for head, body in notes:
        ws.write(r, 1, head, f["h2"])
        ws.merge_range(r + 1, 1, r + 3, 1, body, f["note"])
        r += 5

    wb.close()
    size = OUT.stat().st_size / 1024
    print(f"wrote {OUT}  ({size:,.0f} KB, {len(wb.worksheets())} sheets)")


if __name__ == "__main__":
    main()
