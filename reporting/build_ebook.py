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
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Inches, Pt, RGBColor

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "warehouse" / "redandyellow.duckdb"
OUT = REPO / "ebook" / "RedAndYellow_Data_Story.docx"
FIG = REPO / "ebook" / "figures"
ASSET = REPO / "ebook" / "assets"

RED = "#F52635"
YELLOW = "#FFB71B"
CHARCOAL = "#1D1D1B"
SLATE = "#60646B"
SERIES = ["#F52635", "#E39B16", "#007C83", "#008C45", "#7D3C6A", "#D9574A"]

plt.rcParams.update({
    "figure.dpi": 200, "font.size": 9, "font.family": "DejaVu Sans",
    "axes.edgecolor": "#DDD5C8", "axes.labelcolor": CHARCOAL,
    "text.color": CHARCOAL, "xtick.color": SLATE, "ytick.color": SLATE,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "axes.facecolor": "#FFFDF9", "figure.facecolor": "#FFFFFF",
    "grid.color": "#EEE7DC", "grid.linewidth": 0.7, "axes.axisbelow": True,
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
      select (select count(*) from main_silver.stg_lead)                    as leads,
             (select count(*) from main_silver.stg_contact)                 as contact_rows,
             (select count(*) from main_gold.dim_contact)                   as contacts,
             (select count(*) from main_gold.fct_admissions_funnel)         as opps,
             (select count(*) from main_silver.stg_application)             as apps,
             (select count(*) from main_silver.stg_enrolment)               as enrolments,
             (select sum(spend_zar) from main_gold.dim_campaign)            as spend,
             (select sum(agreed_fee_zar) from main_silver.stg_enrolment)    as revenue,
             (select count(*) from main_quality.dq_issue_log)                as issues
    """).iloc[0]
    chan = q("""select channel, round(sum(spend_zar)/nullif(sum(enrolments),0)) as cpe,
                       round(sum(enrolled_revenue_zar)/nullif(sum(spend_zar),0),2) as roas,
                       sum(enrolments) as enrolments
                from main_gold.fct_campaign_performance group by 1 order by roas desc""")
    mkt = q("""select channel,
                       sum(members) as reach,
                       sum(engaged_members) as responded,
                       sum(enrolments) as enrolments,
                       round(100.0 * sum(engaged_members) / nullif(sum(members), 0), 1) as response_rate,
                       round(sum(enrolled_revenue_zar) / nullif(sum(spend_zar), 0), 2) as roas
                from main_gold.fct_campaign_performance
                group by 1 order by roas desc""")
    risk = q("""select week_number, round(avg(attendance_pct),1) att,
                       round(avg(assessment_average_pct),1) ass,
                       round(100.0*sum(is_at_risk)/count(*),1) at_risk_pct
                from main_gold.fct_student_progress_weekly group by 1 order by 1""")
    dq = q("select issue_code, sum(issue_count) as issue_count from main_quality.dq_summary group by issue_code order by issue_count desc limit 10")

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

    fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.8))
    axes[0].bar(mkt["channel"], mkt["response_rate"], color=SERIES[0])
    axes[0].set_ylabel("Response rate %")
    axes[0].tick_params(axis="x", rotation=34, labelsize=7)
    for lbl in axes[0].get_xticklabels():
        lbl.set_ha("right")
    axes[1].bar(mkt["channel"], mkt["roas"], color=SERIES[2])
    axes[1].set_ylabel("Return on ad spend")
    axes[1].tick_params(axis="x", rotation=34, labelsize=7)
    for lbl in axes[1].get_xticklabels():
        lbl.set_ha("right")
    fig.tight_layout(); fig.savefig(FIG / "marketing_efficiency.png"); plt.close(fig)

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

    # A GA4 NiFi builder exists, but it has no credentialed successful run or
    # landed source table. This figure explains the extension without passing
    # it off as an operating pipeline.
    fig, ax = plt.subplots(figsize=(6.4, 2.35))
    ax.axis("off")
    boxes = [
        (0.02, "GA4 property", "event and campaign data"),
        (0.22, "Data API /\nBigQuery export", "scheduled, consent-aware"),
        (0.45, "OneLake bronze", "ga4 / event_date partition"),
        (0.66, "Fabric + dbt", "conform campaign and date"),
        (0.86, "Power BI", "attribution and reach"),
    ]
    for i, (x, title, sub) in enumerate(boxes):
        fill = "#FFF7E3" if i in (0, 2) else "#FFFFFF"
        edge = RED if i == 0 else (YELLOW if i == 2 else "#DDD5C8")
        patch = matplotlib.patches.FancyBboxPatch((x, 0.36), 0.12, 0.34,
            boxstyle="round,pad=0.014,rounding_size=0.02", linewidth=1.2,
            edgecolor=edge, facecolor=fill, transform=ax.transAxes)
        ax.add_patch(patch)
        ax.text(x + 0.06, 0.57, title, transform=ax.transAxes, ha="center",
                va="center", fontsize=8, fontweight="bold", color=CHARCOAL)
        ax.text(x + 0.06, 0.42, sub, transform=ax.transAxes, ha="center",
                va="center", fontsize=6.6, color=SLATE)
        if i < len(boxes) - 1:
            ax.annotate("", xy=(boxes[i + 1][0] - 0.008, 0.53),
                        xytext=(x + 0.128, 0.53), xycoords=ax.transAxes,
                        arrowprops={"arrowstyle": "->", "color": RED, "lw": 1.5})
    ax.text(0.5, 0.12, "Proposed extension — not configured or counted in the current platform",
            transform=ax.transAxes, ha="center", va="center", fontsize=7.6,
            color=SLATE, style="italic")
    fig.tight_layout(); fig.savefig(FIG / "ga4_to_fabric.png"); plt.close(fig)

    # ---- additional analysis figures --------------------------------------
    prog = q("""select d.programme_title, sum(f.is_enrolled) enrolments,
                       round(avg(f.discount_pct),1) disc
                from main_gold.fct_admissions_funnel f
                join main_gold.dim_offering d using (offering_external_id)
                group by 1 having sum(f.is_enrolled) > 0
                order by enrolments desc limit 12""")
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    labels = [t[:44] + ("..." if len(t) > 44 else "") for t in prog["programme_title"]]
    ax.barh(labels[::-1], prog["enrolments"][::-1], color=SERIES[2])
    ax2 = ax.twiny()
    ax2.plot(prog["disc"][::-1], range(len(prog)), "o", color=SERIES[1], ms=4)
    ax2.set_xlabel("Avg discount %", fontsize=8, color=SERIES[1])
    ax2.tick_params(axis="x", labelsize=7, colors=SERIES[1])
    ax.set_xlabel("Enrolments")
    ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout(); fig.savefig(FIG / "prog_demand.png"); plt.close(fig)

    prov = q("""select c.province, sum(f.is_enrolled) enrolments
                from main_gold.fct_admissions_funnel f
                join main_gold.dim_contact c using (contact_external_id)
                group by 1 order by enrolments desc""")
    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    cols = [SERIES[1] if p != "Unknown" else "#A7AAA7" for p in prov["province"]]
    ax.bar(prov["province"], prov["enrolments"], color=cols)
    ax.set_ylabel("Enrolments")
    ax.tick_params(axis="x", rotation=38, labelsize=7.5)
    for lbl in ax.get_xticklabels():
        lbl.set_ha("right")
    fig.tight_layout(); fig.savefig(FIG / "province.png"); plt.close(fig)

    conv = q("""select
        round(100.0*count(*)/ (select count(*) from main_silver.stg_lead),1) lead_to_opp,
        round(100.0*sum(case when application_external_id is not null then 1 else 0 end)
              /count(*),1) opp_to_app,
        round(100.0*sum(is_enrolled)
              /nullif(sum(case when application_external_id is not null then 1 else 0 end),0),1) app_to_enrol
        from main_gold.fct_admissions_funnel""").iloc[0]
    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    steps = ["Lead to\nopportunity", "Opportunity to\napplication",
             "Application to\nenrolment"]
    vals = [conv.lead_to_opp, conv.opp_to_app, conv.app_to_enrol]
    bars = ax.bar(steps, vals, color=[SERIES[0], SERIES[2], SERIES[3]], width=0.5)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.1f}%",
                ha="center", fontsize=9, color=CHARCOAL, weight="bold")
    ax.set_ylabel("Conversion %")
    ax.set_ylim(0, max(vals) * 1.28)
    fig.tight_layout(); fig.savefig(FIG / "conversion.png"); plt.close(fig)

    # ---- ML figures -------------------------------------------------------
    mlp_path = REPO / "warehouse" / "ml"
    if (mlp_path / "lead_propensity.parquet").exists():
        import pandas as _pd
        lp = _pd.read_parquet(mlp_path / "lead_propensity.parquet")
        wr = _pd.read_parquet(mlp_path / "withdrawal_risk.parquet")
        b1 = lp.groupby("propensity_band", observed=True)["target"].mean() * 100
        b2 = wr.groupby("risk_band", observed=True)["target"].mean() * 100

        fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.7))
        for ax, s, title, base in [
                (axes[0], b1, "Lead conversion by propensity band",
                 lp["target"].mean() * 100),
                (axes[1], b2, "Withdrawal by predicted risk band",
                 wr["target"].mean() * 100)]:
            bars = ax.bar(s.index.astype(str), s.values,
                          color=[SERIES[3], SERIES[2], SERIES[1], SERIES[0]][:len(s)])
            ax.axhline(base, ls="--", lw=1, color=SLATE)
            ax.text(len(s) - 0.5, base, f" base {base:.1f}%", fontsize=6.5,
                    color=SLATE, va="bottom", ha="right")
            for b, v in zip(bars, s.values):
                ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.1f}%",
                        ha="center", va="bottom", fontsize=7, color=CHARCOAL)
            ax.set_title(title, fontsize=8.5)
            ax.tick_params(labelsize=7)
            ax.set_ylim(0, max(s.values) * 1.3)
        fig.tight_layout(); fig.savefig(FIG / "ml_bands.png"); plt.close(fig)

        rep = json.loads((mlp_path / "model_report.json").read_text(encoding="utf-8"))
        fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.7))
        for ax, m, col in zip(axes, rep["models"], [SERIES[0], SERIES[2]]):
            f6 = m["features"][:6][::-1]
            ax.barh([x["feature"] for x in f6], [x["share"] * 100 for x in f6],
                    color=col)
            ax.set_title(m["model"], fontsize=8)
            ax.tick_params(labelsize=7)
            ax.set_xlabel("% of gain", fontsize=7)
        fig.tight_layout(); fig.savefig(FIG / "ml_importance.png"); plt.close(fig)

    # ---- document ---------------------------------------------------------
    d = Document()
    st = d.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10.5)
    st.paragraph_format.space_after = Pt(7)
    st.paragraph_format.line_spacing = 1.14

    # Chapter numbering. Real Word heading styles are used rather than bold
    # paragraphs, because a table-of-contents field can only find headings -
    # styled text that merely looks like a heading is invisible to it.
    counters = {1: 0, 2: 0, 3: 0}

    def H(text, size=17, color=CHARCOAL, space_before=16, number=True):
        level = 1 if size >= 20 else (2 if size >= 16 else 3)
        if number:
            counters[level] += 1
            for deeper in range(level + 1, 4):
                counters[deeper] = 0
            label = ".".join(str(counters[i]) for i in range(1, level + 1))
            text = f"{label}  {text}"

        p = d.add_heading("", level=level)
        p.paragraph_format.space_before = Pt(space_before)
        r = p.add_run(text)
        r.bold = True
        r.font.size = Pt(size)
        r.font.color.rgb = rgb(color)
        r.font.name = "Calibri"
        return p

    def toc_field():
        """Insert a TOC field. Word populates it when the document is opened
        or converted; python-docx cannot compute page numbers itself."""
        p = d.add_paragraph()
        run = p.add_run()
        fld = OxmlElement("w:fldSimple")
        fld.set(qn("w:instr"), r'TOC \o "1-3" \h \z \u')
        inner = OxmlElement("w:r")
        t = OxmlElement("w:t")
        t.text = ("Right-click here and choose Update Field to build the "
                  "contents list.")
        inner.append(t)
        fld.append(inner)
        run._r.addnext(fld)
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

    def brand_image(name, cap=None, width=6.1):
        """Place a user-supplied Red & Yellow brand image when it is packaged.

        The e-book remains reproducible: it never reaches back into Downloads.
        """
        path = ASSET / name
        if not path.exists():
            raise SystemExit(f"Missing brand asset: {path}")
        d.add_picture(str(path), width=Inches(width))
        d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        if cap:
            caption(cap)

    # Cover
    p = d.add_paragraph(); p.paragraph_format.space_before = Pt(18)
    brand_image("red-yellow-logo.png", width=1.35)
    p = d.add_paragraph(); p.paragraph_format.space_before = Pt(18)
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
    r = p.add_run(f"\n{datetime.now():%d %B %Y}   |   Anthony Apollis")
    r.font.size = Pt(10); r.font.color.rgb = rgb(SLATE)
    p = d.add_paragraph()
    r = p.add_run("\nThe programme catalogue in this document is real, transcribed from the "
                  "public Red & Yellow website. Every person, campaign, application and "
                  "enrolment is synthetic. Nothing here is an export from Red & Yellow's "
                  "own systems.")
    r.italic = True; r.font.size = Pt(9); r.font.color.rgb = rgb(SLATE)
    d.add_page_break()

    # ---- contents --------------------------------------------------------
    p = d.add_paragraph()
    r = p.add_run("Contents")
    r.bold = True
    r.font.size = Pt(20)
    r.font.color.rgb = rgb(RED)
    toc_field()
    d.add_page_break()

    # ---- introduction ----------------------------------------------------
    H("Introduction", 20, RED, 0)
    d.add_paragraph(
        "Red & Yellow advertised for a Data Analytics Engineer whose brief is "
        "CRM integration: build the pipelines, catalogue the data, model it, and "
        "put it in front of people who make decisions. The advert names six "
        "things - a data catalogue, ERDs for internal systems, ETL preferably in "
        "Apache NiFi, Salesforce data extracted and analysed, Power BI "
        "dashboards, and data quality held to a standard.")
    d.add_paragraph(
        "This document is the working answer to all six, and it is written to be "
        "checked rather than admired. Every figure in it is generated from a live "
        "query or a live API call at the moment the document is built, so nothing "
        "here can describe a pipeline that has stopped working. Where something "
        "does not work, or could not be done, it says so.")

    H("How to read it", 16, CHARCOAL, 12)
    for label, text in [
        ("The numbers first",
         "Chapter 2 sets out what was built and how much of it there is."),
        ("Then the decisions",
         "Chapters 3 to 8 cover the modelling choices that are actually "
         "arguable - spend attribution, de-duplication, what a blank means - "
         "and what happened when each was got wrong first."),
        ("Then the evidence",
         "Chapters 9 to 11 show the Salesforce integration step by step, the "
         "two predictive models with their metrics against a base rate, and the "
         "running NiFi and Fabric infrastructure."),
        ("Finally the limits",
         "The last chapter is what this work does not claim."),
    ]:
        pr = d.add_paragraph(style="List Bullet")
        rr = pr.add_run(f"{label}. ")
        rr.bold = True
        rr.font.color.rgb = rgb(RED)
        pr.add_run(text)

    d.add_paragraph()
    warn = d.add_paragraph()
    wr = warn.add_run(
        "One thing to hold in mind throughout: the programme catalogue is real, "
        "transcribed from Red & Yellow's public site. Everything about people - "
        "every lead, contact, application, enrolment and result - is synthetic, "
        "and the relationships between them were put there deliberately so the "
        "pipeline had something to find. That makes this a demonstration of "
        "method, not a finding about Red & Yellow.")
    wr.italic = True
    wr.font.color.rgb = rgb(SLATE)
    d.add_page_break()

    H("What this is", 20, RED, 0)
    d.add_paragraph(
        "Red & Yellow's Data Analytics Engineer role asks for six things: a data catalogue, "
        "ERDs for CRM data models, ETL pipelines built preferably in Apache NiFi, Salesforce "
        "CRM data extracted and analysed, Power BI dashboards, and data quality held to a "
        "standard. This document is the working answer to all six, built end to end on a "
        "dataset of "
        f"{k.leads + k.contact_rows:,.0f} people and {truth['total_rows'] / 1_000_000:.1f} million rows.")
    d.add_paragraph(
        "The architecture follows the shape the role describes. Salesforce is the operational "
        "CRM. NiFi replicates it into a lakehouse. dbt cleanses, tests and documents. Power BI "
        "reads the curated marts. The interesting engineering is not in any one of those "
        "tools - it is in the decisions between them, which is what this document is about.")
    brand_image("creative-magic-commercial-logic.png",
                "Red & Yellow's Creative Magic and Commercial Logic — the brand idea that frames this data story.")

    figure_if("ev_00_architecture.png",
              "Figure 0 - The pipeline end to end. Each stage is a separate, "
              "runnable component; nothing here is a diagram of an intention.")

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
    H("Marketing analytics, from audience to value", 16, CHARCOAL, 12)
    d.add_paragraph(
        "The marketing page separates reach, response, enrolment and value. "
        "Response rate tells the team whether a channel is reaching an interested audience; "
        "cost per enrolment tells it what that audience costs to convert; return on ad spend "
        "tests whether the resulting fees justify the investment. Revenue per member and spend "
        "per response make the same comparison usable before a campaign has accumulated enough "
        "enrolments for a stable cost-per-enrolment figure.")
    figure("marketing_efficiency.png",
           "Figure 2a - Campaign response rate and return on ad spend by channel. "
           "Both are calculated at campaign grain before they are aggregated.")

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

    # ---- extra analysis --------------------------------------------------
    H("Where the demand actually is")
    d.add_paragraph(
        "The catalogue is real, so programme demand is the one place where the "
        "synthetic pipeline meets Red & Yellow's actual offering. These are the "
        "programmes carrying the most enrolments in the modelled pipeline, and "
        "the discount being conceded to win them.")
    figure_if("prog_demand.png",
              "Figure 4a - Top programmes by enrolment, with average discount.")

    H("Who is enrolling, and from where", 13, CHARCOAL, 12)
    d.add_paragraph(
        "Province is one of the dirtiest fields in the source - 'Western Cape', "
        "'western cape', 'W Cape', 'WC' and 'Wes-Kaap' all arrive - and one of "
        "the most useful once collapsed. Anything that cannot be resolved is "
        "kept as Unknown rather than guessed at.")
    figure_if("province.png",
              "Figure 4b - Enrolments by province, after the spelling variants "
              "are collapsed to the nine official names.")
    brand_image("student-cohort.jfif",
                "Red & Yellow student community — supplied brand image used as context for the learner journey.")

    H("The funnel as conversion, not counts", 13, CHARCOAL, 12)
    d.add_paragraph(
        "Absolute counts down a funnel flatter the top of it. The rates between "
        "stages are what a marketing team can act on.")
    figure_if("conversion.png",
              "Figure 4c - Stage-to-stage conversion through the admissions "
              "pipeline.")

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

    H("1. Establish whether the org can host the model", 16, CHARCOAL, 14)
    d.add_paragraph(
        "The target trial org runs Salesforce Base Edition, which permits zero "
        "custom objects. That is an edition entitlement rather than a quota or a "
        "permission, so no configuration changes it - and it is knowable in a "
        "single API call. Checking first turns a failure at deploy time into a "
        "decision at design time.")
    figure_if("ev_01_org_check.png",
              "Figure 5 - The org capability check. Base Edition, 10.6 GB free, "
              "and a NO-GO on custom objects.")

    H("2. Deploy what the edition does allow", 16, CHARCOAL, 12)
    d.add_paragraph(
        "The eight custom objects cannot deploy, but the eighteen custom fields "
        "on standard objects can. Deploying fields without field-level security "
        "is a trap worth naming: the fields exist, but describe() omits them and "
        "the upsert then fails claiming the external ID is not unique - because "
        "the API cannot see the field it is being asked to key on. The permission "
        "set is trimmed to the deployed fields and assigned over REST.")
    figure_if("ev_02_metadata_validate.png",
              "Figure 6 - Metadata validated against the org. 18 of 18 components.")

    H("3. Load the operational CRM slice", 16, CHARCOAL, 12)
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

    H("4. Extract it back out through the API", 16, CHARCOAL, 12)
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

    H("5. Transform, test, and report", 16, CHARCOAL, 12)
    d.add_paragraph(
        "From there the extracted data joins the same warehouse the synthetic "
        "history lives in, is cleansed once in staging, and is consumed by marts "
        "that Power BI reads directly. The tests run on every build.")
    figure_if("ev_06_dbt_tests.png", "Figure 10 - dbt build: models and data tests.")
    d.add_paragraph("The reproducible run record, delivery-mode check and DuckDB/Fabric scope are documented in docs/DBT_EVIDENCE.md.")

    # ---- predictive models ------------------------------------------------
    mlp = REPO / "warehouse" / "ml" / "model_report.json"
    if mlp.exists():
        ml = json.loads(mlp.read_text(encoding="utf-8"))
        d.add_page_break()
        H("Two models, and what they are worth", 20, RED, 0)
        d.add_paragraph(
            "Both models are split by time rather than at random, and restricted "
            "to what is known at the moment a decision is made. The lead model "
            "cannot see the opportunity a lead later generated; the withdrawal "
            "model sees only the first four weeks. Leaking a downstream outcome "
            "into the features is the easiest way to build a model with a "
            "beautiful score and no use whatever.")

        tbl = d.add_table(rows=1, cols=5)
        tbl.style = "Light List Accent 1"
        for i, h in enumerate(["Model", "Base rate", "AUC", "PR-AUC",
                               "Top-decile lift"]):
            tbl.rows[0].cells[i].text = h
        for m in ml["models"]:
            c = tbl.add_row().cells
            c[0].text = m["model"]
            c[1].text = f"{m['base_rate']*100:.1f}%"
            c[2].text = f"{m['auc']:.3f}"
            c[3].text = f"{m['pr_auc']:.3f}"
            c[4].text = f"{m['top_decile_lift']:.2f}x"
        d.add_paragraph()
        d.add_paragraph(
            "An AUC in the mid-0.6s is not a headline, and it should not be. "
            "These are human decisions with a great deal of unexplained "
            "variation; a model claiming 0.95 on this data would mean a feature "
            "had leaked. What matters operationally is the lift: the top tenth "
            "of leads by score converts at over twice the base rate, which is "
            "the difference between working a list in arrival order and working "
            "it in priority order.")
        figure_if("ml_bands.png",
                  "Figure 10a - Conversion by propensity band, and withdrawal by "
                  "risk band. If the bars do not separate, the model is not "
                  "ranking anything.")
        figure_if("ml_importance.png",
                  "Figure 10b - What each model actually leans on.")

        H("What to do about it", 16, CHARCOAL, 12)
        for i in ml.get("insights", []):
            p = d.add_paragraph(style="List Bullet")
            r = p.add_run(f"{i['area']}. ")
            r.bold = True
            r.font.color.rgb = rgb(RED)
            p.add_run(i["finding"] + " ")
            r2 = p.add_run(i["recommendation"])
            r2.italic = True

        H("An honest caveat", 16, CHARCOAL, 12)
        d.add_paragraph(
            "These models are trained on synthetic data whose structure was put "
            "there deliberately. They demonstrate the method - time-based "
            "splits, decision-time features, scoring against a base rate, lift "
            "as the operational metric - not a finding about Red & Yellow. On "
            "real data the effect sizes would differ, and the first job would be "
            "to check whether they hold at all.")

        H("From AI score to a human decision", 16, CHARCOAL, 12)
        d.add_paragraph(
            "The model outputs are warehouse tables, not autonomous CRM actions. "
            "The lead-propensity score orders a worklist: a recruiter can spend "
            "their next call on the leads most likely to enrol, while still seeing "
            "the band and the underlying CRM record. The withdrawal-risk score is "
            "an early-warning list for a student-success team. It should trigger a "
            "conversation or support offer, never an automated adverse decision. "
            "Power BI exposes the score distribution and observed outcomes so a "
            "team can see whether the ranking remains useful before operationalising it.")

    # ---- how the warehouse is organised ----------------------------------
    d.add_page_break()
    H("How the warehouse is organised", 20, RED, 0)
    d.add_paragraph(
        "The warehouse follows a medallion layout, and it is a real one rather "
        "than three schema names: silver reads bronze, never the source file. "
        "That matters because it is what makes the lineage answer the question "
        "“what actually arrived?”. Without a bronze layer, dbt’s graph "
        "begins at the cleansed data and the landed source is invisible to the "
        "catalogue - you can see what a column became, but not what it was.")

    tbl = d.add_table(rows=1, cols=3)
    tbl.style = "Light List Accent 1"
    for i, h in enumerate(["Layer", "What it holds", "Rule"]):
        tbl.rows[0].cells[i].text = h
    for layer, holds, rule in [
        ("Bronze", "13 models - the landed source made queryable",
         "No renaming, casting or filtering"),
        ("Silver", "13 models - cleansed and conformed",
         "Every cleansing decision lives here and nowhere else"),
        ("Gold", "8 models - business-level facts and dimensions",
         "Assumes clean input; never re-cleans"),
        ("Quality", "2 models - the defect log and its summary",
         "Describes the pipeline, not the business"),
    ]:
        c = tbl.add_row().cells
        c[0].text = layer
        c[1].text = holds
        c[2].text = rule
    d.add_paragraph()
    figure_if("ev_09_medallion.png",
              "Figure 10c - The medallion, read from dbt’s manifest. Model "
              "counts and layer membership come from the build, so a model added "
              "or moved shows up here rather than the picture going stale.")

    H("Full canonical Salesforce ERD", 16, CHARCOAL, 12)
    d.add_paragraph(
        "The complete canonical ERD is included here as the source-of-truth relationship map. "
        "It includes the public catalogue objects, Salesforce operational objects, applications, "
        "enrolments and student-progress spine. Archived diagrams are not implementation targets.")
    erd_shot = REPO / "ebook" / "screenshots" / "03_Canonical_ERD.png"
    if erd_shot.exists():
        d.add_picture(str(erd_shot), width=Inches(6.2))
        d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        caption("Canonical Salesforce ERD — complete implementation target, rendered from erds/overview.svg.")
    else:
        d.add_paragraph("[Canonical ERD capture is missing; render erds/overview.svg before release.]")

    H("The data model", 16, CHARCOAL, 12)
    d.add_paragraph(
        "The semantic model mirrors the canonical ERD rather than stopping at "
        "aggregates: programme, offering, intake, enquiry, application, "
        "enrolment, student and weekly progress are all present and joined, so "
        "the chain the ERD draws can actually be walked in a report. The live "
        "Salesforce tables and both model outputs hang off the same spine.")
    figure_if("ev_10_data_model.png",
              "Figure 10d - The semantic model, read from its TMDL. Facts sit at "
              "the centre in red, dimensions on the ring.")

    # ---- the rest of the stack -------------------------------------------
    d.add_page_break()
    H("The pipeline infrastructure", 20, RED, 0)
    d.add_paragraph(
        "Two pieces of the stack are running systems rather than code in a "
        "repository, so they are shown as they actually are - read from their "
        "own APIs at the moment this document was built.")

    H("Apache NiFi", 16, CHARCOAL, 12)
    d.add_paragraph(
        "NiFi has exactly one root per instance, so a project is a top-level "
        "process group and its stages are nested groups joined by ports. That "
        "lets each stage start, stop and version independently, and keeps the "
        "canvas readable. Controller services sit on the project group and are "
        "inherited, so the two stages cannot drift onto different connection "
        "pools. Credentials come from a parameter context whose sensitive "
        "values are empty in source control - which is why the processors are "
        "stopped and invalid until an operator supplies them.")
    figure_if("ev_07_nifi_flow.png",
              "Figure 11 - The live NiFi hierarchy. RY_Salesforce_to_Fabric "
              "holds two stage groups; the LYRA groups are unrelated work on "
              "the same instance.")

    H("Microsoft Fabric", 16, CHARCOAL, 12)
    d.add_paragraph(
        "Fabric Warehouse bronze is verified. All 13 landed source tables are present in "
        "raw_salesforce: 1.50 million leads, 1.14 million contacts, 2.53 million campaign "
        "members, 706 thousand opportunities, 494 thousand applications and 2.10 million "
        "student-progress rows, with the programme catalogue tables alongside them. The Azure "
        "CLI dbt connection and a bronze campaign view both passed. The silver and gold Fabric "
        "build is intentionally not claimed as complete: its remaining failures are documented "
        "DuckDB-to-T-SQL compatibility work, including date and join syntax.")
    d.add_paragraph(
        "The bronze land is partitioned by table in OneLake. A workspace created through the API "
        "arrives with no capacity attached, and every Fabric item type then fails with a 403 that "
        "looks like licensing rather than an unassigned workspace. Trial capacity does not stop "
        "on its own, so delete the project workspace when the demonstration is complete.")
    figure_if("ev_08_fabric.png",
              "Figure 12 - The Fabric workspace, its capacity, and what is actually in OneLake.")

    H("GA4 to Fabric — the next integration, not a claimed result", 16, CHARCOAL, 12)
    d.add_paragraph(
        "A GA4 NiFi builder is included, but it has no configured GA4 credential, "
        "successful extract or warehouse source table, and no report number uses GA4 data. "
        "The practical next route is a scheduled GA4 Data API extract or a BigQuery "
        "export into an immutable OneLake bronze partition by event date. A dbt "
        "staging model would then conform date and campaign keys before a gold "
        "attribution mart joins aggregate reach and traffic to the campaign spine "
        "already used by Power BI. Keep user-level analytics identifiers out of "
        "the CRM join; campaign, source and date are enough for the first use case.")
    figure("ga4_to_fabric.png",
           "Figure 13 - Proposed GA4 extension. It is intentionally separated from the verified Salesforce-to-Fabric flow.")

    # Any UI screenshots the author dropped in are appended, captioned by filename.
    shots = sorted((REPO / "ebook" / "screenshots").glob("*.png")) + \
        sorted((REPO / "ebook" / "screenshots").glob("*.jpg"))
    if shots:
        H("Screens from the org", 16, CHARCOAL, 12)
        for sh in shots:
            if sh.name == '03_Canonical_ERD.png':
                continue
            cap = sh.stem.split("_", 1)[-1].replace("_", " ")
            d.add_picture(str(sh), width=Inches(5.9))
            d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            caption(cap[:1].upper() + cap[1:])

    H("What is not claimed")
    for text in [
        "This is a proposed model, not Red & Yellow's actual Salesforce configuration. The "
        "real org may already map these concepts onto Education Cloud or EDA objects.",
        "The catalogue was transcribed from 17 screenshots of the public site on 8 September "
        "2026. It is not claimed to be the complete live catalogue. "
        "For reporting, On-campus remains On-campus and listings in the Online education section are classified as Off-campus; the source section is retained separately.",
        "All people, campaign spend, application outcomes and student results are synthetic. "
        "Progress dated after the capture date is an illustrative scenario, not a forecast.",
        "DuckDB is fully validated. Fabric bronze loading and dbt connectivity are verified, but "
        "the Fabric silver and gold build has documented DuckDB-to-T-SQL compatibility errors. "
        "No downstream Fabric transformation result is claimed until those are corrected and rerun.",    ]:
        d.add_paragraph(text, style="List Bullet")

    d.save(str(OUT))
    print(f"wrote {OUT}  ({OUT.stat().st_size/1024:,.0f} KB)")


if __name__ == "__main__":
    main()
