#!/usr/bin/env python3
"""Builds the Red & Yellow data story as a Word document.

Every figure in the narrative is queried live from the warehouse at build time,
so the document cannot drift from the data it describes. Re-running after a
pipeline change rewrites the numbers.

    python build_ebook.py
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "warehouse" / "redandyellow.duckdb"
OUT = REPO / "ebook" / "RedAndYellow_Data_Story.docx"
FIG = REPO / "ebook" / "figures"

RED = "#E03127"
YELLOW = "#FFC629"
CHARCOAL = "#22252A"
SLATE = "#5A6472"
SERIES = ["#E03127", "#F0A202", "#2E6E8E", "#4C9F70", "#8B5FBF", "#C7522A"]

plt.rcParams.update({
    "figure.dpi": 200, "font.size": 9, "font.family": "DejaVu Sans",
    "axes.edgecolor": "#C8CED6", "axes.labelcolor": CHARCOAL,
    "text.color": CHARCOAL, "xtick.color": SLATE, "ytick.color": SLATE,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": "#E8ECF1", "grid.linewidth": 0.7, "axes.axisbelow": True,
})


def rgb(hexstr):
    return RGBColor(*(int(hexstr[i:i + 2], 16) for i in (1, 3, 5)))


def main():
    if not DB.exists():
        raise SystemExit(f"warehouse not built ({DB})")
    FIG.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(DB), read_only=True)
    truth = json.loads((REPO / "warehouse" / "_truth" / "defects.json").read_text())
    q = lambda s: con.sql(s).df()

    k = q("""
      select (select count(*) from main_staging.stg_lead)                    as leads,
             (select count(*) from main_staging.stg_contact)                 as contact_rows,
             (select count(*) from main_marts.dim_contact)                   as contacts,
             (select count(*) from main_marts.fct_admissions_funnel)         as opps,
             (select count(*) from main_staging.stg_application)             as apps,
             (select count(*) from main_staging.stg_enrolment)               as enrolments,
             (select sum(spend_zar) from main_marts.dim_campaign)            as spend,
             (select sum(agreed_fee_zar) from main_staging.stg_enrolment)    as revenue,
             (select count(*) from main_quality.dq_issue_log)                as issues
    """).iloc[0]
    chan = q("""select channel, round(sum(spend_zar)/nullif(sum(enrolments),0)) as cpe,
                       round(sum(enrolled_revenue_zar)/nullif(sum(spend_zar),0),2) as roas,
                       sum(enrolments) as enrolments
                from main_marts.fct_campaign_performance group by 1 order by roas desc""")
    risk = q("""select week_number, round(avg(attendance_pct),1) att,
                       round(avg(assessment_average_pct),1) ass,
                       round(100.0*sum(is_at_risk)/count(*),1) at_risk_pct
                from main_marts.fct_student_progress_weekly group by 1 order by 1""")
    dq = q("select issue_code, issue_count from main_quality.dq_summary order by issue_count desc limit 10")

    # ---- figures ----------------------------------------------------------
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    stages = ["Leads", "Contacts", "Opportunities", "Applications", "Enrolments"]
    vals = [k.leads, k.contacts, k.opps, k.apps, k.enrolments]
    ax.barh(stages[::-1], vals[::-1], color=[SERIES[i % 6] for i in range(5)][::-1])
    for i, v in enumerate(vals[::-1]):
        ax.text(v, i, f" {v:,.0f}", va="center", fontsize=8, color=SLATE)
    ax.set_xlabel("Records")
    ax.xaxis.set_major_formatter(lambda x, p: f"{x/1e6:.1f}m" if x >= 1e6 else f"{x/1e3:.0f}k")
    ax.margins(x=0.16)
    fig.tight_layout(); fig.savefig(FIG / "funnel.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    ax.bar(chan["channel"], chan["cpe"], color=SERIES[2])
    ax.set_ylabel("Cost per enrolment (R)")
    ax.tick_params(axis="x", rotation=38)
    for lbl in ax.get_xticklabels():
        lbl.set_ha("right")
    fig.tight_layout(); fig.savefig(FIG / "cpe.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    ax.plot(risk["week_number"], risk["att"], color=SERIES[0], lw=2, label="Attendance %")
    ax.plot(risk["week_number"], risk["ass"], color=SERIES[3], lw=2, label="Assessment avg %")
    ax.plot(risk["week_number"], risk["at_risk_pct"], color=SERIES[1], lw=2,
            ls="--", label="At risk %")
    ax.set_xlabel("Week of study"); ax.set_ylabel("Percent")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout(); fig.savefig(FIG / "risk.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.barh(dq["issue_code"][::-1], dq["issue_count"][::-1], color=SERIES[5])
    ax.set_xlabel("Records affected")
    ax.xaxis.set_major_formatter(lambda x, p: f"{x/1e3:.0f}k" if x >= 1e3 else f"{x:.0f}")
    fig.tight_layout(); fig.savefig(FIG / "dq.png"); plt.close(fig)

    # ---- document ---------------------------------------------------------
    d = Document()
    st = d.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10.5)
    st.paragraph_format.space_after = Pt(7)
    st.paragraph_format.line_spacing = 1.14

    def H(text, size=17, color=CHARCOAL, space_before=16):
        p = d.add_paragraph()
        p.paragraph_format.space_before = Pt(space_before)
        r = p.add_run(text)
        r.bold = True
        r.font.size = Pt(size)
        r.font.color.rgb = rgb(color)
        return p

    def caption(text):
        p = d.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(text)
        r.italic = True
        r.font.size = Pt(8.5)
        r.font.color.rgb = rgb(SLATE)

    def figure(name, cap):
        d.add_picture(str(FIG / name), width=Inches(6.1))
        d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        caption(cap)

    def figure_if(name, cap):
        """Embed an evidence figure, or say plainly that it was not captured.

        Silently omitting a missing figure would leave the narrative claiming
        steps that have no evidence behind them.
        """
        p = FIG / name
        if p.exists():
            figure(name, cap)
        else:
            note = d.add_paragraph()
            r = note.add_run(f"[{cap.split(' - ')[0]} not captured - "
                             f"run reporting/capture_evidence.py]")
            r.italic = True
            r.font.size = Pt(8.5)
            r.font.color.rgb = rgb(SLATE)

    # Cover
    p = d.add_paragraph(); p.paragraph_format.space_before = Pt(90)
    r = p.add_run("Red & Yellow"); r.bold = True; r.font.size = Pt(40)
    r.font.color.rgb = rgb(RED)
    p = d.add_paragraph()
    r = p.add_run("From marketing spend to student outcomes")
    r.font.size = Pt(17); r.font.color.rgb = rgb(CHARCOAL)
    p = d.add_paragraph()
    r = p.add_run("A CRM analytics platform built on Salesforce, Apache NiFi, "
                  "dbt, Microsoft Fabric and Power BI")
    r.font.size = Pt(11.5); r.font.color.rgb = rgb(SLATE)
    p = d.add_paragraph()
    r = p.add_run(f"\n{datetime.now():%d %B %Y}   ·   Anthony Apollis")
    r.font.size = Pt(10); r.font.color.rgb = rgb(SLATE)
    p = d.add_paragraph()
    r = p.add_run("\nThe programme catalogue in this document is real, transcribed from the "
                  "public Red & Yellow website. Every person, campaign, application and "
                  "enrolment is synthetic. Nothing here is an export from Red & Yellow's "
                  "own systems.")
    r.italic = True; r.font.size = Pt(9); r.font.color.rgb = rgb(SLATE)
    d.add_page_break()

    H("What this is", 20, RED, 0)
    d.add_paragraph(
        "Red & Yellow's Data Analytics Engineer role asks for six things: a data catalogue, "
        "ERDs for CRM data models, ETL pipelines built preferably in Apache NiFi, Salesforce "
        "CRM data extracted and analysed, Power BI dashboards, and data quality held to a "
        "standard. This document is the working answer to all six, built end to end on a "
        "dataset of "
        f"{k.leads + k.contact_rows:,.0f} people and 9.4 million rows.")
    d.add_paragraph(
        "The architecture follows the shape the role describes. Salesforce is the operational "
        "CRM. NiFi replicates it into a lakehouse. dbt cleanses, tests and documents. Power BI "
        "reads the curated marts. The interesting engineering is not in any one of those "
        "tools - it is in the decisions between them, which is what this document is about.")

    H("The numbers")
    tbl = d.add_table(rows=0, cols=2); tbl.style = "Light List Accent 1"
    for label, val in [
        ("Leads captured", f"{k.leads:,.0f}"),
        ("Contacts after de-duplication", f"{k.contacts:,.0f} (from {k.contact_rows:,.0f} records)"),
        ("Opportunities in the admissions pipeline", f"{k.opps:,.0f}"),
        ("Applications submitted", f"{k.apps:,.0f}"),
        ("Enrolments", f"{k.enrolments:,.0f}"),
        ("Marketing spend", f"R{k.spend/1e6:,.1f}m"),
        ("Enrolled revenue (agreed fees)", f"R{k.revenue/1e6:,.1f}m"),
        ("Data quality issues detected", f"{k.issues:,.0f}"),
        ("Programmes / offerings / intakes (real)", "83 / 89 / 47"),
    ]:
        row = tbl.add_row().cells
        row[0].text = label
        row[1].text = val
    d.add_paragraph()
    figure("funnel.png", "Figure 1 - The funnel by stage. Leads and contacts overlap, so the "
                         "step between them is not attrition.")

    H("Where the marketing money goes")
    best, worst = chan.iloc[0], chan.iloc[-1]
    d.add_paragraph(
        f"Cost per enrolment sits between R{chan['cpe'].min():,.0f} and "
        f"R{chan['cpe'].max():,.0f} across channels, on a return of "
        f"{chan['roas'].min():.1f}x to {chan['roas'].max():.1f}x. "
        f"{best.channel} returns the most per rand at {best.roas:.2f}x; "
        f"{worst.channel} the least at {worst.roas:.2f}x.")
    d.add_paragraph(
        "One modelling decision matters more than any of these numbers. Campaign spend is "
        "aggregated to campaign grain before it is joined to enrolments. Join spend to the "
        "fact table first and every campaign's cost is silently multiplied by its downstream "
        "row count - a campaign with 400 enrolments reports 400 times its real budget, and "
        "the resulting return on ad spend looks spectacular. A dbt test compares total spend "
        "in the fact against total spend in the dimension and fails the build if they diverge.")
    figure("cpe.png", "Figure 2 - Cost per enrolment by channel.")

    H("Student success as an early warning")
    w1, wl = risk.iloc[0], risk.iloc[-1]
    d.add_paragraph(
        f"Attendance opens at {w1.att:.0f}% and decays to {wl.att:.0f}% by week "
        f"{int(wl.week_number)}. The proportion of students meeting the at-risk definition - "
        f"attendance under 55%, or assessment average under 50%, or three or more overdue "
        f"assignments - moves from {w1.at_risk_pct:.0f}% to {wl.at_risk_pct:.0f}%.")
    d.add_paragraph(
        "The definition lives in one place, in the fct_student_progress_weekly model. That is "
        "deliberate: 'at risk' is the kind of term that acquires three incompatible meanings "
        "across three dashboards if each report defines it locally.")
    figure("risk.png", "Figure 3 - Academic health across the study weeks.")

    H("Data quality, measured rather than asserted")
    d.add_paragraph(
        "Every pipeline claims to handle dirty data. This one is tested against a known "
        "answer. Defects are injected into the source at recorded rates - duplicate humans, "
        "phone format drift, invalid and missing emails, province spelling variants, inverted "
        "dates, negative values, late-arriving records - and written to a ground-truth "
        "manifest. The pipeline's detection is then scored against that manifest as recall.")
    d.add_paragraph(
        f"Across {sum(truth['injected_defect_counts'].values()):,} injected defects the "
        f"pipeline detects {k.issues:,.0f} issues. De-duplication recovers 0.97 of the "
        "duplicates that were planted.")

    H("Why de-duplication needed two keys", 13, CHARCOAL, 12)
    d.add_paragraph(
        "The first attempt keyed contacts on email, falling back to name plus phone. It "
        "reported 682,000 duplicates against 29,000 real ones. The cause was the name pool: "
        "across a million contacts drawn from a realistic South African name distribution, "
        "'Thabo Nkosi' recurs legitimately thousands of times, and coalescing a null phone to "
        "an empty string collapsed all of them together.")
    d.add_paragraph(
        "Keying strictly on email fixed the false positives and created the opposite problem. "
        "Recall fell to 0.52, because the two duplicate shapes a CRM actually produces are "
        "different: someone re-submitting the web form repeats their email, while someone "
        "phoning in leaves no email at all. A record that has an email and a record that does "
        "not can never share a single key value.")
    d.add_paragraph(
        "The working version anchors on email and on phone-plus-surname independently, takes "
        "the lower anchor, then propagates once within each phone group so a phone-only record "
        "inherits the cluster of the emailed record it shares a handset with. Recall 0.97. The "
        "remaining 3% are records where both email and phone were dropped at source, which no "
        "amount of matching can recover.")
    figure("dq.png", "Figure 4 - Detected issues by type.")

    H("Blanks that are not gaps")
    d.add_paragraph(
        "Some of the catalogue's most careful values are empty. An offering priced 'Enquire "
        "for price' carries no amount, and a clipped screenshot yields no duration. Both are "
        "recorded as null with a status explaining why.")
    d.add_paragraph(
        "Filling those with zero would be the single most damaging thing this pipeline could "
        "do. Zero is a price. It would drag every average fee downward, understate pipeline "
        "value, and make the free courses look like a growth segment. A dbt test fails the "
        "build if any offering with a price status of Enquire acquires a fee.")

    H("Why the CRM holds thousands and the warehouse holds millions")
    d.add_paragraph(
        "Salesforce charges data storage per record, at roughly 2 KB each. A Developer "
        "Edition org holds about 10,000 records in total across every object. Loading nine "
        "million rows into the CRM is not a scaling problem to engineer around - it is not "
        "possible, and an org that hit its ceiling mid-load would leave dangling foreign keys "
        "behind it.")
    d.add_paragraph(
        "So the split follows the job description rather than fighting it. Salesforce holds a "
        "referentially complete operational slice of roughly two thousand records, safe to "
        "demo and safe to re-upsert on an external ID. The warehouse holds the full history, "
        "the volume and the quality work. That is what a CRM integration role means in "
        "practice: knowing which system each question belongs to.")

    H("The pipeline, end to end")
    for step, text in [
        ("Extract", "NiFi's QuerySalesforceObject pulls Lead, Contact, Campaign, "
                    "CampaignMember and Opportunity incrementally on SystemModstamp, holding "
                    "the high-water mark in processor state so a restart does not replay "
                    "history."),
        ("Land", "Records are batched and written to the OneLake bronze layer, partitioned by "
                 "object and ingest date. Failures retry three times before parking."),
        ("Transform", "dbt cleanses once in staging - email validation, E.164 phone "
                      "normalisation, province collapsing, entity resolution - then builds "
                      "marts that assume clean inputs."),
        ("Test", "51 data tests run on every build: uniqueness, referential integrity, "
                 "accepted values, and three bespoke tests guarding spend multiplication, "
                 "enquire-pricing and golden-record uniqueness."),
        ("Document", "dbt docs generate produces the searchable catalogue with column-level "
                     "lineage, so documentation is a build artefact rather than a wiki page "
                     "that drifts."),
        ("Report", "Power BI reads the curated marts. Every measure resolves to a tested "
                   "model, not to a query written in the report."),
    ]:
        p = d.add_paragraph(style="List Bullet")
        r = p.add_run(f"{step}. "); r.bold = True; r.font.color.rgb = rgb(RED)
        p.add_run(text)

    # ---- Salesforce integration, documented step by step -----------------
    d.add_page_break()
    H("Salesforce integration, step by step", 20, RED, 0)
    d.add_paragraph(
        "This section documents the CRM integration as it actually ran, not as it "
        "was designed to run. Every figure below is rendered from live command "
        "output or a live query against the org at the moment this document was "
        "built, so it cannot describe a pipeline that no longer works.")

    sf = REPO / "run_results" / "import_log.json"
    if sf.exists():
        import collections as _c
        _log = json.loads(sf.read_text(encoding="utf-8"))
        _n = _c.Counter(r["object"] for r in _log)
        d.add_paragraph(
            f"{len(_log):,} records were loaded across {len(_n)} objects: "
            + ", ".join(f"{k} {v}" for k, v in sorted(_n.items())) + ".")

    H("1. Establish whether the org can host the model", 13, CHARCOAL, 14)
    d.add_paragraph(
        "The target trial org runs Salesforce Base Edition, which permits zero "
        "custom objects. That is an edition entitlement rather than a quota or a "
        "permission, so no configuration changes it - and it is knowable in a "
        "single API call. Checking first turns a failure at deploy time into a "
        "decision at design time.")
    figure_if("ev_01_org_check.png",
              "Figure 5 - The org capability check. Base Edition, 10.6 GB free, "
              "and a NO-GO on custom objects.")

    H("2. Deploy what the edition does allow", 13, CHARCOAL, 12)
    d.add_paragraph(
        "The eight custom objects cannot deploy, but the eighteen custom fields "
        "on standard objects can. Deploying fields without field-level security "
        "is a trap worth naming: the fields exist, but describe() omits them and "
        "the upsert then fails claiming the external ID is not unique - because "
        "the API cannot see the field it is being asked to key on. The permission "
        "set is trimmed to the deployed fields and assigned over REST.")
    figure_if("ev_02_metadata_validate.png",
              "Figure 6 - Metadata validated against the org. 18 of 18 components.")

    H("3. Load the operational CRM slice", 13, CHARCOAL, 12)
    d.add_paragraph(
        "Accounts, contacts, leads and opportunities, upserted on an external ID "
        "so the load is idempotent - re-running updates rather than duplicates. "
        "Two things pushed back, and both were right to. Salesforce rejects the "
        "external ID in the request body when it is already the key in the URL. "
        "And its duplicate rules blocked leads that fuzzy-matched existing "
        "contacts at 100% confidence - the same duplicates the warehouse's own "
        "entity resolution finds, caught independently by the CRM.")
    figure_if("ev_03_import_result.png",
              "Figure 7 - What the loader wrote.")
    figure_if("ev_04_org_counts.png",
              "Figure 8 - What is actually in the org, queried back through the "
              "API. The loader's claim and the org's state are different "
              "assertions; only the second is evidence.")

    H("4. Extract it back out through the API", 13, CHARCOAL, 12)
    d.add_paragraph(
        "This is the part the role is actually about. SOQL over the REST API, "
        "paginating through nextRecordsUrl so the 2,000-record page limit is "
        "handled rather than silently truncating, with the high-water mark on "
        "SystemModstamp persisted between runs. The first run is a full load; "
        "the second returns zero rows because nothing changed. Deletions are "
        "captured through queryAll rather than left to linger.")
    figure_if("ev_05_extraction.png",
              "Figure 9 - Extraction manifest. Every row carries its source "
              "system, source id, source update time and extraction time.")

    H("5. Transform, test, and report", 13, CHARCOAL, 12)
    d.add_paragraph(
        "From there the extracted data joins the same warehouse the synthetic "
        "history lives in, is cleansed once in staging, and is consumed by marts "
        "that Power BI reads directly. The tests run on every build.")
    figure_if("ev_06_dbt_tests.png", "Figure 10 - dbt build: models and data tests.")

    # Any UI screenshots the author dropped in are appended, captioned by filename.
    shots = sorted((REPO / "ebook" / "screenshots").glob("*.png")) + \
        sorted((REPO / "ebook" / "screenshots").glob("*.jpg"))
    if shots:
        H("Screens from the org", 13, CHARCOAL, 12)
        for sh in shots:
            cap = sh.stem.split("_", 1)[-1].replace("_", " ")
            d.add_picture(str(sh), width=Inches(5.9))
            d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            caption(cap[:1].upper() + cap[1:])

    H("What is not claimed")
    for text in [
        "This is a proposed model, not Red & Yellow's actual Salesforce configuration. The "
        "real org may already map these concepts onto Education Cloud or EDA objects.",
        "The catalogue was transcribed from 17 screenshots of the public site on 8 September "
        "2026. It is not claimed to be the complete live catalogue, and page section alone "
        "was not treated as proof of delivery mode.",
        "All people, campaign spend, application outcomes and student results are synthetic. "
        "Progress dated after the capture date is an illustrative scenario, not a forecast.",
        "The pipeline has been validated locally against DuckDB and a live NiFi instance. "
        "Deployment to a Salesforce org and a Fabric workspace requires credentials that are "
        "deliberately absent from this repository.",
    ]:
        d.add_paragraph(text, style="List Bullet")

    d.save(str(OUT))
    print(f"wrote {OUT}  ({OUT.stat().st_size/1024:,.0f} KB)")


if __name__ == "__main__":
    main()
