#!/usr/bin/env python3
"""Captures the infrastructure - NiFi, Fabric, and the architecture - as figures.

The Salesforce steps already have evidence figures; these cover the rest of the
stack. Like those, they are read from live APIs at build time rather than
screenshotted once, so the ebook shows the pipeline as it stands on the day it
is generated.

Real UI screenshots still belong in ebook/screenshots/ - these figures prove the
state, a screenshot shows the interface. Both are worth having.

    python capture_infra.py
"""
from __future__ import annotations

import os
import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = pathlib.Path(__file__).resolve().parent.parent
FIG = REPO / "ebook" / "figures"

sys.path.insert(0, str(REPO / "reporting"))
from capture_evidence import terminal_figure  # noqa: E402

NIFI_BASE = "https://localhost:8443/nifi-api"
NIFI_USER_DEFAULT = "e73f9c96-ef04-4181-a2c3-7a573cc7a24d"


def nifi_password():
    pw = os.environ.get("NIFI_PASSWORD", "").strip()
    if pw:
        return pw
    # Kept outside the repository on purpose.
    f = pathlib.Path("C:/Apache/NIFI_LOGIN.txt")
    if f.exists():
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("password:"):
                return line.split(":", 1)[1].strip()
    return ""


def nifi_text():
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    pw = nifi_password()
    if not pw:
        raise RuntimeError("no NiFi password available")
    user = os.environ.get("NIFI_USER") or NIFI_USER_DEFAULT

    s = requests.Session()
    s.verify = False
    r = s.post(NIFI_BASE + "/access/token",
               data={"username": user, "password": pw},
               headers={"Content-Type": "application/x-www-form-urlencoded"},
               timeout=30)
    r.raise_for_status()
    s.headers["Authorization"] = "Bearer " + r.text

    lines = []

    def walk(gid, depth=0, name=None):
        f = s.get(NIFI_BASE + "/flow/process-groups/" + gid, timeout=60)
        f.raise_for_status()
        pgf = f.json()["processGroupFlow"]
        flow = pgf["flow"]
        nm = name or pgf["breadcrumb"]["breadcrumb"]["name"]
        pad = "    " * depth
        lines.append("{}{}   ({} processors, {} groups, {} connections)".format(
            pad, nm, len(flow["processors"]), len(flow["processGroups"]),
            len(flow["connections"])))
        for pr in sorted(flow["processors"], key=lambda x: x["component"]["name"]):
            c = pr["component"]
            state = c.get("state", "")
            lines.append("{}  - {:<28}{}".format(pad, c["name"], state))
        for g in sorted(flow["processGroups"], key=lambda x: x["component"]["name"]):
            walk(g["id"], depth + 1, g["component"]["name"])

    root = s.get(NIFI_BASE + "/flow/process-groups/root",
                 timeout=60).json()["processGroupFlow"]["id"]
    walk(root)
    return "\n".join(lines)


def fabric_text():
    import requests
    sys.path.insert(0, str(REPO / "fabric"))
    from deploy_fabric import (token, FABRIC_API, FABRIC_SCOPE,
                               ONELAKE, ONELAKE_SCOPE)
    from azure.identity import DefaultAzureCredential

    cred = DefaultAzureCredential(exclude_managed_identity_credential=True)
    H = {"Authorization": "Bearer " + token(cred, FABRIC_SCOPE)}

    wss = requests.get(FABRIC_API + "/workspaces", headers=H, timeout=90).json()["value"]
    ws = next(w for w in wss if w["displayName"] == "WS_RedAndYellow")
    items = requests.get("{}/workspaces/{}/items".format(FABRIC_API, ws["id"]),
                         headers=H, timeout=90).json()["value"]
    caps = {c["id"]: c for c in requests.get(FABRIC_API + "/capacities",
                                             headers=H, timeout=90).json()["value"]}
    cap = caps.get(ws.get("capacityId"), {})

    lines = ["workspace   " + ws["displayName"],
             "id          " + ws["id"],
             "capacity    {}   sku={}   state={}".format(
                 cap.get("displayName", "(none)"), cap.get("sku", "-"),
                 cap.get("state", "-")),
             ""]
    for it in items:
        lines.append("  item      {:<26}{}".format(it["displayName"], it["type"]))

    H2 = {"Authorization": "Bearer " + token(cred, ONELAKE_SCOPE)}
    r = requests.get(ONELAKE + "/WS_RedAndYellow",
                     params={"resource": "filesystem", "recursive": "true",
                             "directory": "LH_RedAndYellow.Lakehouse/Files/bronze"},
                     headers=H2, timeout=180)
    paths = [x for x in r.json().get("paths", []) if not x.get("isDirectory")]
    total = sum(int(x.get("contentLength", 0)) for x in paths)
    lines += ["", "OneLake bronze: {} parquet files, {:.0f} MB".format(
        len(paths), total / 1024 / 1024)]
    for x in sorted(paths, key=lambda y: -int(y.get("contentLength", 0))):
        lines.append("  {:>8.1f} MB  {}".format(
            int(x["contentLength"]) / 1024 / 1024, x["name"].split("/")[-1]))
    return "\n".join(lines)


def _row_count(default="11.5M"):
    """Row count from the ground-truth manifest, formatted for a caption."""
    import json
    m = REPO / "warehouse" / "_truth" / "defects.json"
    if not m.exists():
        return default
    try:
        return "{:.1f}M".format(json.loads(m.read_text())["total_rows"] / 1e6)
    except Exception:
        return default


def _counts():
    """The numbers printed inside the architecture boxes, read from artefacts.

    These were hardcoded and had drifted badly - the figure claimed 23 models
    and a 5-page report when there were 36 and 6. A wrong number rendered into
    a PNG is the worst kind: no grep of the docs will ever find it.
    """
    import json
    c = {}

    man = REPO / "dbt_redandyellow" / "target" / "manifest.json"
    if man.exists():
        try:
            m = json.loads(man.read_text(encoding="utf-8"))
            c["models"] = sum(1 for n in m["nodes"].values()
                              if n.get("resource_type") == "model")
            c["tests"] = sum(1 for n in m["nodes"].values()
                             if n.get("resource_type") == "test")
        except Exception:
            pass

    rj = REPO / "powerbi" / "RedAndYellow.Report" / "report.json"
    if rj.exists():
        try:
            r = json.loads(rj.read_text(encoding="utf-8"))
            c["pages"] = len(r["sections"])
            c["visuals"] = sum(len(s["visualContainers"]) for s in r["sections"])
        except Exception:
            pass

    log = REPO / "run_results" / "import_log.json"
    if log.exists():
        try:
            c["sf"] = len(json.loads(log.read_text(encoding="utf-8")))
        except Exception:
            pass

    return c


def architecture_figure():
    """Draw the pipeline, so the reader sees the shape before the detail."""
    fig, ax = plt.subplots(figsize=(9.4, 3.0))
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 34)
    ax.axis("off")

    c = _counts()
    boxes = [
        (1, "Salesforce\nCRM",
         "{:,} records\n4 objects".format(c.get("sf", 1091)), "#F52635"),
        (20.5, "NiFi + REST\nextract", "incremental on\nSystemModstamp", "#E39B16"),
        (40, "OneLake\nbronze", "13 files\n242 MB", "#007C83"),
        (59.5, "dbt\nwarehouse",
         "{} models\n{} tests".format(c.get("models", 36), c.get("tests", 51)),
         "#008C45"),
        (79, "Power BI\n+ Excel",
         "{} pages\n{} visuals".format(c.get("pages", 6), c.get("visuals", 72)),
         "#7D3C6A"),
    ]
    for x, title, sub, col in boxes:
        ax.add_patch(plt.Rectangle((x, 9), 17.5, 16, facecolor="#FFFFFF",
                                   edgecolor=col, linewidth=2.0, zorder=2))
        ax.add_patch(plt.Rectangle((x, 22.6), 17.5, 2.4, facecolor=col,
                                   edgecolor=col, linewidth=0, zorder=3))
        ax.text(x + 8.75, 18.8, title, ha="center", va="center", fontsize=9.0,
                color="#1D1D1B", weight="bold", zorder=4)
        ax.text(x + 8.75, 12.6, sub, ha="center", va="center", fontsize=7.2,
                color="#60646B", zorder=4)
        if x < 79:
            ax.annotate("", xy=(x + 19.3, 17), xytext=(x + 17.8, 17),
                        arrowprops=dict(arrowstyle="-|>", color="#8C857C", lw=1.6))

    # Read the row count rather than hardcoding it: the figure outlived the
    # number once already, and a caption that disagrees with the data is worse
    # than one that omits it.
    ax.text(50, 4.0,
            f"{_row_count()} synthetic rows in the warehouse   ·   the CRM holds "
            "the operational slice   ·   every row carries its source and load time",
            ha="center", fontsize=7.4, color="#60646B")
    fig.tight_layout(pad=0.3)
    out = FIG / "ev_00_architecture.png"
    fig.savefig(out, dpi=200, facecolor="#FFFFFF")
    plt.close(fig)
    print("  {:<34}drawn".format("ev_00_architecture.png"))


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    print("capturing infrastructure figures\n")

    architecture_figure()

    for label, fn, name in [
        ("Apache NiFi - live process-group hierarchy", nifi_text,
         "ev_07_nifi_flow.png"),
        ("Microsoft Fabric - WS_RedAndYellow (live)", fabric_text,
         "ev_08_fabric.png"),
    ]:
        try:
            terminal_figure(label, fn(), name, max_lines=42)
        except Exception as e:
            # Say so rather than leaving a gap the ebook silently fills.
            print("  {:<34}SKIPPED: {}".format(name, e))

    print("\n  figures in {}".format(FIG))


if __name__ == "__main__":
    main()
