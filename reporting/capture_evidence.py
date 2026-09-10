#!/usr/bin/env python3
"""Captures evidence of each pipeline step as figures for the ebook.

Screenshots of a UI go stale the moment anything changes and cannot be
regenerated. These figures are rendered from live command output and live org
queries at build time, so the document always shows what the pipeline actually
did on the day it was built, not what it did once in a screenshot someone took.

Any real UI screenshots you drop into ebook/screenshots/ are picked up by
build_ebook.py and captioned by filename, so the two can sit side by side.

    python capture_evidence.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parent.parent
FIG = REPO / "ebook" / "figures"
SHOTS = REPO / "ebook" / "screenshots"
PY = sys.executable

TERM_BG = "#14171C"
TERM_FG = "#D6DEE7"
TERM_ACCENT = "#7FD1B9"
TERM_WARN = "#E39B16"
TERM_ERR = "#E4635A"


def terminal_figure(title, text, name, max_lines=34):
    """Render captured output as a terminal-styled figure."""
    lines = text.rstrip().splitlines()
    if len(lines) > max_lines:
        keep = max_lines - 1
        lines = lines[:keep] + [f"... ({len(text.splitlines()) - keep} more lines)"]
    if not lines:
        lines = ["(no output)"]

    h = max(1.6, 0.235 * len(lines) + 0.85)
    fig, ax = plt.subplots(figsize=(9.2, h))
    fig.patch.set_facecolor(TERM_BG)
    ax.set_facecolor(TERM_BG)
    ax.axis("off")

    ax.text(0.012, 0.985, title, transform=ax.transAxes, va="top", ha="left",
            fontsize=8.5, color=TERM_ACCENT, family="DejaVu Sans Mono", weight="bold")

    y = 0.985 - (1.05 / len(lines) if len(lines) < 6 else 0.075)
    step = 0.92 / max(len(lines), 1)
    for i, ln in enumerate(lines):
        low = ln.lower()
        colour = TERM_FG
        if any(w in low for w in ("error", "failed", "no-go", "rejected")):
            colour = TERM_ERR
        elif any(w in low for w in ("success", "pass", "verdict: go", "deployed",
                                    "imported", "connected", "visible")):
            colour = TERM_ACCENT
        elif any(w in low for w in ("warning", "skipped", "note:")):
            colour = TERM_WARN
        ax.text(0.012, y - i * step, ln[:118], transform=ax.transAxes, va="top",
                ha="left", fontsize=7.1, color=colour, family="DejaVu Sans Mono")

    fig.tight_layout(pad=0.35)
    out = FIG / name
    fig.savefig(out, dpi=200, facecolor=TERM_BG)
    plt.close(fig)
    print(f"  {name:<34}{len(lines):>4} lines")
    return out


def run(cmd):
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=600)
    return (r.stdout or "") + (r.stderr or "")


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    if not (SHOTS / "README.md").exists():
        (SHOTS / "README.md").write_text(
            "# Screenshots\n\n"
            "Drop UI screenshots here and build_ebook.py embeds them, captioned "
            "from the filename. Use a leading number to control order and "
            "underscores for the caption, e.g.\n\n"
            "    01_External_Client_App_client_credentials_flow.png\n"
            "    02_Permission_set_assignment.png\n"
            "    03_Contacts_loaded_in_Salesforce.png\n", encoding="utf-8")

    print("capturing evidence figures\n")

    # 1. Org capability check - live
    terminal_figure("$ python salesforce/check_org.py",
                    run([PY, "salesforce/check_org.py"]),
                    "ev_01_org_check.png")

    # 2. Metadata validation against the org - live, writes nothing
    terminal_figure("$ python salesforce/deploy_metadata.py --check-only --standard-only",
                    run([PY, "salesforce/deploy_metadata.py",
                         "--check-only", "--standard-only"]),
                    "ev_02_metadata_validate.png")

    # 3. What the import actually wrote
    log_path = REPO / "run_results" / "import_log.json"
    if log_path.exists():
        import collections
        log = json.loads(log_path.read_text(encoding="utf-8"))
        c = collections.Counter((r["object"], r["operation"]) for r in log)
        lines = ["object          operation     records", "-" * 40]
        for (o, op), n in sorted(c.items()):
            lines.append(f"{o:<16}{op:<14}{n:>7}")
        lines += ["-" * 40, f"{'TOTAL':<30}{len(log):>7}",
                  "", "upserted on RY_External_ID__c - re-running updates,",
                  "it does not duplicate."]
        terminal_figure("run_results/import_log.json", "\n".join(lines),
                        "ev_03_import_result.png")

    # 4. Live counts in the org, queried through the API
    terminal_figure("$ python salesforce/verify_org_counts.py",
                    run([PY, "salesforce/verify_org_counts.py"]),
                    "ev_04_org_counts.png")

    # 5. Extraction back out through the API
    man = REPO / "warehouse" / "salesforce_raw" / "_extract_manifest.json"
    if man.exists():
        m = json.loads(man.read_text(encoding="utf-8"))
        lines = [f"extracted_at  {m['extracted_at']}",
                 f"instance      {m['instance']}",
                 f"mode          {m['mode']}", "",
                 f"{'object':<16}{'rows':>8}{'pages':>7}  watermark", "-" * 62]
        for o in m["objects"]:
            lines.append(f"{o['object']:<16}{o['rows']:>8}{o.get('pages', 0):>7}  "
                         f"{o.get('watermark', '')}")
        lines += ["-" * 62, f"{'TOTAL':<16}{m['total_records']:>8} records"]
        terminal_figure("warehouse/salesforce_raw/_extract_manifest.json",
                        "\n".join(lines), "ev_05_extraction.png")

    # 6. dbt build - the tests, from the last run's artefacts
    rr = REPO / "dbt_redandyellow" / "target" / "run_results.json"
    if rr.exists():
        d = json.loads(rr.read_text(encoding="utf-8"))
        res = d.get("results", [])
        import collections
        st = collections.Counter(r["status"] for r in res)
        tests = [r for r in res if r["unique_id"].startswith("test.")]
        lines = [f"dbt {d.get('metadata', {}).get('dbt_version', '')}"
                 f"   elapsed {d.get('elapsed_time', 0):.1f}s", "",
                 f"nodes run     {len(res)}",
                 f"data tests    {len(tests)}", ""]
        for k, v in st.most_common():
            lines.append(f"  {k:<12}{v:>5}")
        failed = [r for r in res if r["status"] not in ("success", "pass")]
        lines += ["", "FAILURES: none" if not failed
                  else f"FAILURES: {len(failed)}"]
        terminal_figure("dbt build - models and data tests", "\n".join(lines),
                        "ev_06_dbt_tests.png")

    print(f"\n  figures in {FIG}")
    print(f"  drop UI screenshots in {SHOTS}")


if __name__ == "__main__":
    main()
