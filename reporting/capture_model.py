#!/usr/bin/env python3
"""Draws the dbt medallion lineage and the Power BI data model.

Both are read from real artefacts - dbt's manifest.json and the semantic model's
TMDL - rather than drawn by hand, so a model added or a relationship removed
shows up here on the next build instead of the picture quietly going stale.

    python capture_model.py
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

REPO = Path(__file__).resolve().parent.parent
FIG = REPO / "ebook" / "figures"
MANIFEST = REPO / "dbt_redandyellow" / "target" / "manifest.json"
TMDL = REPO / "powerbi" / "RedAndYellow.SemanticModel" / "definition"

LAYERS = [
    ("bronze", "Bronze", "#E39B16", "landed exactly as it arrived"),
    ("silver", "Silver", "#707A84", "cleansed and conformed"),
    ("gold", "Gold", "#FFB71B", "business-level, assumes clean input"),
    ("quality", "Quality", "#007C83", "describes the pipeline, not the business"),
]
CHARCOAL, SLATE, PAPER = "#1D1D1B", "#60646B", "#FFFFFF"


def medallion_figure():
    if not MANIFEST.exists():
        print("  medallion: no manifest - run dbt build first")
        return
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))

    by_layer = defaultdict(list)
    for uid, n in man.get("nodes", {}).items():
        if n.get("resource_type") != "model":
            continue
        path = (n.get("path") or "").replace("\\", "/")
        layer = path.split("/")[0] if "/" in path else "other"
        by_layer[layer].append(n["name"])
    tests = sum(1 for n in man.get("nodes", {}).values()
                if n.get("resource_type") == "test")

    fig, ax = plt.subplots(figsize=(9.4, 4.3))
    fig.patch.set_facecolor(PAPER)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 46)
    ax.axis("off")

    x, w = 1.5, 22.5
    for i, (key, label, colour, blurb) in enumerate(LAYERS):
        names = sorted(by_layer.get(key, []))
        left = x + i * (w + 2.0)
        ax.add_patch(FancyBboxPatch((left, 5), w, 33,
                                    boxstyle="round,pad=0.3,rounding_size=1.2",
                                    facecolor=PAPER, edgecolor=colour, lw=2, zorder=2))
        ax.add_patch(FancyBboxPatch((left, 33.2), w, 4.8,
                                    boxstyle="round,pad=0.3,rounding_size=1.2",
                                    facecolor=colour, edgecolor=colour, lw=0, zorder=3))
        ax.text(left + w / 2, 35.6, f"{label}   ({len(names)})", ha="center",
                va="center", fontsize=10.5, weight="bold", color=PAPER, zorder=4)
        ax.text(left + w / 2, 31.2, blurb, ha="center", va="center", fontsize=6.8,
                color=SLATE, style="italic", zorder=4)

        shown = names[:11]
        for j, nm in enumerate(shown):
            ax.text(left + 1.2, 28.4 - j * 2.15, nm[:26], ha="left", va="center",
                    fontsize=6.6, color=CHARCOAL, family="DejaVu Sans Mono", zorder=4)
        if len(names) > len(shown):
            ax.text(left + 1.2, 28.4 - len(shown) * 2.15,
                    f"... {len(names) - len(shown)} more", ha="left", va="center",
                    fontsize=6.4, color=SLATE, style="italic", zorder=4)

        if i < len(LAYERS) - 1:
            ax.add_patch(FancyArrowPatch((left + w + 0.2, 21), (left + w + 1.8, 21),
                                         arrowstyle="-|>", mutation_scale=13,
                                         color="#8C857C", lw=1.6, zorder=5))

    ax.text(50, 1.8,
            f"{sum(len(v) for v in by_layer.values())} models   ·   {tests} data tests   "
            f"·   every silver model reads bronze, never the source file",
            ha="center", fontsize=7.6, color=SLATE)
    fig.tight_layout(pad=0.3)
    fig.savefig(FIG / "ev_09_medallion.png", dpi=200, facecolor=PAPER)
    plt.close(fig)
    print(f"  {'ev_09_medallion.png':<30}"
          + "  ".join(f"{k}={len(v)}" for k, v in sorted(by_layer.items())))


def data_model_figure():
    rel_file = TMDL / "relationships.tmdl"
    if not rel_file.exists():
        print("  data model: no relationships.tmdl - run build_pbip.py first")
        return
    text = rel_file.read_text(encoding="utf-8")
    rels = []
    for m in re.finditer(r"fromColumn:\s*(\S+)\.(\S+)\s*\n\s*toColumn:\s*(\S+)\.(\S+)",
                         text):
        rels.append((m.group(1), m.group(3)))

    # Degree decides the layout: the most-referenced tables sit in the middle.
    deg = defaultdict(int)
    for a, b in rels:
        deg[a] += 1
        deg[b] += 1
    dims = sorted({b for _, b in rels}, key=lambda t: -deg[t])
    facts = sorted({a for a, _ in rels}, key=lambda t: -deg[a])

    import math
    fig, ax = plt.subplots(figsize=(9.4, 6.0))
    fig.patch.set_facecolor(PAPER)
    ax.set_xlim(-1.35, 1.35)
    ax.set_ylim(-1.2, 1.2)
    ax.axis("off")

    pos = {}
    for i, t in enumerate(dims):
        a = 2 * math.pi * i / max(len(dims), 1)
        pos[t] = (0.92 * math.cos(a), 0.86 * math.sin(a))
    for i, t in enumerate(facts):
        a = 2 * math.pi * i / max(len(facts), 1) + math.pi / len(max(facts, key=len))
        pos[t] = (0.36 * math.cos(a), 0.34 * math.sin(a))

    for a, b in rels:
        if a in pos and b in pos:
            ax.annotate("", xy=pos[b], xytext=pos[a],
                        arrowprops=dict(arrowstyle="-|>", color="#C3CBD4", lw=1.0,
                                        shrinkA=16, shrinkB=16,
                                        connectionstyle="arc3,rad=0.06"))

    for t, (px, py) in pos.items():
        is_fact = t in facts
        colour = "#F52635" if is_fact else ("#007C83" if t.startswith(("dim_", "sf_"))
                                            else "#008C45")
        label = t.replace("fct_", "").replace("dim_", "").replace("ml_", "")[:20]
        ax.add_patch(FancyBboxPatch((px - 0.145, py - 0.038), 0.29, 0.076,
                                    boxstyle="round,pad=0.012,rounding_size=0.02",
                                    facecolor=PAPER, edgecolor=colour, lw=1.5, zorder=3))
        ax.text(px, py, label, ha="center", va="center", fontsize=6.6,
                color=CHARCOAL, zorder=4)

    ax.text(0, -1.14,
            f"{len(pos)} tables   ·   {len(rels)} relationships   ·   "
            f"facts in red at the centre, dimensions on the ring",
            ha="center", fontsize=7.4, color=SLATE)
    fig.tight_layout(pad=0.2)
    fig.savefig(FIG / "ev_10_data_model.png", dpi=200, facecolor=PAPER)
    plt.close(fig)
    print(f"  {'ev_10_data_model.png':<30}{len(pos)} tables, {len(rels)} relationships")


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    print("drawing model figures\n")
    medallion_figure()
    data_model_figure()
    print(f"\n  figures in {FIG}")


if __name__ == "__main__":
    main()
