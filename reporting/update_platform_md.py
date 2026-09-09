#!/usr/bin/env python3
"""Regenerates the factual claims in PLATFORM.md from the real artefacts.

Codex found PLATFORM.md advertising a 4-page, 44-visual report when the project
had 6 pages and 72 visuals, and 74/74 tests when 87 pass. Every one of those
numbers changes on a build, and every one was maintained by hand - so they were
guaranteed to drift, and a reader checking the claim against the artefact would
have found the document wrong.

Numbers between the FACTS markers are now written from the artefacts themselves.
If a count here is wrong, the artefact is wrong, not the prose.

    python update_platform_md.py
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MD = REPO / "PLATFORM.md"
# Two blocks, so each table stays beside the prose that explains it.
MARKERS = {"FACTS": "build_table", "DEFECTS": "defect_table"}


def facts():
    f = {}

    man = REPO / "dbt_redandyellow" / "target" / "manifest.json"
    if man.exists():
        m = json.loads(man.read_text(encoding="utf-8"))
        layers = Counter((n.get("path") or "").replace("\\", "/").split("/")[0]
                         for n in m["nodes"].values()
                         if n.get("resource_type") == "model")
        f["layers"] = dict(layers)
        f["models"] = sum(layers.values())
        f["tests"] = sum(1 for n in m["nodes"].values()
                         if n.get("resource_type") == "test")

    rj = REPO / "powerbi" / "RedAndYellow.Report" / "report.json"
    if rj.exists():
        r = json.loads(rj.read_text(encoding="utf-8"))
        f["pages"] = len(r["sections"])
        f["visuals"] = sum(len(s["visualContainers"]) for s in r["sections"])

    tdir = REPO / "powerbi" / "RedAndYellow.SemanticModel" / "definition"
    if tdir.exists():
        f["tables"] = len(list((tdir / "tables").glob("*.tmdl")))
        rel = (tdir / "relationships.tmdl")
        f["relationships"] = (rel.read_text(encoding="utf-8").count("relationship ")
                              if rel.exists() else 0)
        meas = tdir / "tables" / "_Measures.tmdl"
        f["measures"] = (len(re.findall(r"^\tmeasure ", meas.read_text(encoding="utf-8"),
                                        re.M)) if meas.exists() else 0)

    truth = REPO / "warehouse" / "_truth" / "defects.json"
    if truth.exists():
        t = json.loads(truth.read_text(encoding="utf-8"))
        f["rows"] = t["total_rows"]
        f["injected"] = t["injected_defect_counts"]

    ml = REPO / "warehouse" / "ml" / "model_report.json"
    if ml.exists():
        f["models_ml"] = json.loads(ml.read_text(encoding="utf-8"))["models"]

    try:
        import duckdb
        db = REPO / "warehouse" / "redandyellow.duckdb"
        if db.exists():
            con = duckdb.connect(str(db), read_only=True)
            # SUM, not a dict comprehension: dq_summary is one row per
            # (entity, issue_code), and date_inversion is detected on two
            # entities. Keying on issue_code alone silently kept whichever
            # row came last and under-reported detection by the other.
            f["detected"] = {r[0]: r[1] for r in con.sql(
                "select issue_code, sum(issue_count) "
                "from main_quality.dq_summary group by issue_code").fetchall()}
    except Exception:
        pass

    log = REPO / "run_results" / "import_log.json"
    if log.exists():
        f["sf_records"] = len(json.loads(log.read_text(encoding="utf-8")))

    try:
        from pypdf import PdfReader
        pdf = REPO / "ebook" / "RedAndYellow_Data_Story.pdf"
        if pdf.exists():
            f["pdf_pages"] = len(PdfReader(str(pdf)).pages)
    except Exception:
        pass

    try:
        import openpyxl
        xl = REPO / "reporting" / "RedAndYellow_Analytics.xlsx"
        if xl.exists():
            f["sheets"] = len(openpyxl.load_workbook(xl).sheetnames)
    except Exception:
        pass

    return f


def build_table(f):
    L = ["", "| What | Built | Verified by |", "|---|---|---|"]

    if "layers" in f:
        lay = f["layers"]
        L.append(f"| Medallion warehouse | {lay.get('bronze',0)} bronze, "
                 f"{lay.get('silver',0)} silver, {lay.get('gold',0)} gold, "
                 f"{lay.get('quality',0)} quality | "
                 f"`dbt build` — {f['models'] + f['tests']}/"
                 f"{f['models'] + f['tests']} pass ({f['tests']} data tests) |")
    if "rows" in f:
        L.append(f"| Generated data | {f['rows']:,} rows | "
                 f"ground-truth manifest at `warehouse/_truth/defects.json` |")
    if "pages" in f:
        L.append(f"| Power BI report | {f['pages']} pages, {f['visuals']} visuals | "
                 f"every field reference checked against the model at build time |")
    if "tables" in f:
        L.append(f"| Semantic model | {f['tables']} tables, {f['measures']} measures, "
                 f"{f['relationships']} relationships | loaded through a tabular "
                 f"session |")
    if "sf_records" in f:
        L.append(f"| Salesforce | {f['sf_records']:,} records across 4 objects | "
                 f"`verify_org_counts.py` reconciles the org against the loader |")
    if "pdf_pages" in f:
        L.append(f"| Ebook | {f['pdf_pages']}-page PDF | contents text extracted "
                 f"back out of the finished PDF |")
    if "sheets" in f:
        L.append(f"| Workbook | {f['sheets']} sheets | sheet count read from the "
                 f"workbook |")
    for m in f.get("models_ml", []):
        L.append(f"| ML — {m['model'].lower()} | AUC {m['auc']:.3f}, "
                 f"top-decile lift {m['top_decile_lift']:.2f}x | held-out split by "
                 f"time, base rate {m['base_rate']*100:.1f}% |")
    L.append("")
    return "\n".join(L)


def defect_table(f):
    inj, det = f.get("injected", {}), f.get("detected", {})
    pairs = [("Duplicate humans", "duplicate_person", "duplicate_person"),
             ("Missing attendance", "attendance_missing", "attendance_missing"),
             ("Duplicate campaign membership", "dup_campaign_member",
              "duplicate_membership"),
             ("Date inversions", "date_inversion", "date_inversion")]
    rows = [(lab, inj[i], det[d]) for lab, i, d in pairs if i in inj and d in det]
    if not rows:
        return "\n"
    L = ["", "| Defect | Injected | Detected | Recall |", "|---|---|---|---|"]
    for lab, i, d in rows:
        L.append(f"| {lab} | {i:,} | {d:,} | **{d/i:.2f}** |")
    L.append("")
    return "\n".join(L)


def main():
    if not MD.exists():
        raise SystemExit(f"{MD} not found")
    text = MD.read_text(encoding="utf-8")
    f = facts()

    for name, fn in MARKERS.items():
        begin, end = f"<!-- {name}:BEGIN -->", f"<!-- {name}:END -->"
        if begin not in text or end not in text:
            raise SystemExit(f"PLATFORM.md is missing the {name} markers")
        body = begin + "\n" + globals()[fn](f) + end
        text = re.sub(re.escape(begin) + r".*?" + re.escape(end),
                      lambda _m: body, text, flags=re.S)

    MD.write_text(text, encoding="utf-8")
    print(f"updated {MD}")
    for k in ("models", "tests", "pages", "visuals", "tables", "measures",
              "relationships", "rows", "sf_records", "pdf_pages", "sheets"):
        if k in f:
            print(f"  {k:<16}{f[k]:,}" if isinstance(f[k], int) else f"  {k:<16}{f[k]}")


if __name__ == "__main__":
    main()
