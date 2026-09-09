#!/usr/bin/env python3
"""Trains two models on the warehouse, and scores the population.

The two questions a marketing and admissions team actually ask:

  1. Which enquiries are worth chasing?      lead -> enrolment propensity
  2. Which students are about to drop out?   early-weeks withdrawal risk

Both are deliberately honest about what they can and cannot know:

  * Features are restricted to what is available AT DECISION TIME. The lead
    model cannot see the opportunity that a lead later generated, and the
    withdrawal model sees only the first four weeks of a student's progress.
    Leaking a downstream outcome into the features is the easiest way to build
    a model with a beautiful AUC and no use whatsoever.
  * The split is by time, not at random. A random split lets the model learn
    from the future; a marketing team scoring next month's leads does not have
    that luxury.
  * Metrics are reported against a baseline. An AUC means little without
    knowing what guessing the base rate would have achieved.

    python train_models.py
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             roc_auc_score)

import lightgbm as lgb

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "warehouse" / "redandyellow.duckdb"
OUT = REPO / "warehouse" / "ml"
PBI = REPO / "powerbi" / "data"
SEED = 20260909

CAT_LEAD = ["lead_source", "province", "channel", "created_month"]
CAT_RISK = ["programme_title", "delivery_mode", "category", "enrolment_status"]


def fit_score(train, test, features, cats, target, name, n_leaves=48):
    """Train LightGBM, report against a base-rate baseline, return the model."""
    for c in cats:
        train[c] = train[c].astype("category")
        test[c] = test[c].astype("category").cat.set_categories(
            train[c].cat.categories)

    m = lgb.LGBMClassifier(
        n_estimators=400, learning_rate=0.05, num_leaves=n_leaves,
        min_child_samples=60, subsample=0.9, subsample_freq=1,
        colsample_bytree=0.9, reg_lambda=1.0, random_state=SEED, verbosity=-1)
    m.fit(train[features], train[target],
          eval_set=[(test[features], test[target])],
          eval_metric="auc",
          callbacks=[lgb.early_stopping(40, verbose=False)])

    p = m.predict_proba(test[features])[:, 1]
    base = float(train[target].mean())
    auc = roc_auc_score(test[target], p)
    ap = average_precision_score(test[target], p)
    brier = brier_score_loss(test[target], p)

    # Lift in the top decile is the number a marketing team can act on.
    k = max(int(len(p) * 0.10), 1)
    top = np.argsort(-p)[:k]
    lift = float(test[target].values[top].mean() / base) if base else float("nan")

    imp = (pd.DataFrame({"feature": features, "gain": m.booster_.feature_importance("gain")})
           .sort_values("gain", ascending=False).reset_index(drop=True))
    imp["share"] = (imp["gain"] / imp["gain"].sum()).round(4)

    print(f"\n  {name}")
    print(f"    train {len(train):,}   test {len(test):,}   base rate {base:.3f}")
    print(f"    AUC {auc:.3f}   PR-AUC {ap:.3f}   Brier {brier:.4f}")
    print(f"    top-decile lift {lift:.2f}x  (random would be 1.00x)")
    print(f"    top features: " + ", ".join(imp['feature'].head(4)))

    return m, {"model": name, "train_rows": len(train), "test_rows": len(test),
               "base_rate": round(base, 4), "auc": round(float(auc), 4),
               "pr_auc": round(float(ap), 4), "brier": round(float(brier), 4),
               "top_decile_lift": round(lift, 3),
               "features": imp.to_dict("records")}


def main():
    if not DB.exists():
        raise SystemExit(f"warehouse not built ({DB})")
    OUT.mkdir(parents=True, exist_ok=True)
    PBI.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB), read_only=True)
    report = {"seed": SEED, "models": []}

    # ---------------------------------------------------------------- 1 ----
    # Lead -> enrolment. Everything here is known the day the lead arrives.
    print("\nbuilding lead propensity dataset...")
    leads = con.sql("""
        select
            l.lead_external_id,
            l.lead_source,
            l.province,
            coalesce(c.channel, 'None')                    as channel,
            cast(strftime(l.created_date, '%m') as integer) as created_month,
            extract(year from l.created_date)              as created_year,
            l.created_date,
            case when s.email is not null then 1 else 0 end as has_email,
            case when s.phone_e164 is not null then 1 else 0 end as has_phone,
            case when l.campaign_external_id is not null then 1 else 0 end as from_campaign,
            coalesce(c.spend_zar, 0)                       as campaign_spend,
            l.reached_enrolment                            as target
        from main_gold.fct_lead_conversion l
        join main_silver.stg_lead s using (lead_external_id)
        left join main_gold.dim_campaign c
               on c.campaign_external_id = l.campaign_external_id
        where l.created_date is not null
    """).df()
    leads["created_month"] = leads["created_month"].astype(str)

    # Time split: train on 2022-2025, test on 2026. No peeking forward.
    cut = pd.Timestamp("2026-01-01")
    tr = leads[pd.to_datetime(leads["created_date"]) < cut].copy()
    te = leads[pd.to_datetime(leads["created_date"]) >= cut].copy()
    feats = CAT_LEAD + ["created_year", "has_email", "has_phone",
                        "from_campaign", "campaign_spend"]
    m1, r1 = fit_score(tr, te, feats, CAT_LEAD, "target",
                       "Lead to enrolment propensity")
    report["models"].append(r1)

    # Score everyone, so the CRM can be prioritised rather than worked in order.
    allx = leads.copy()
    for c in CAT_LEAD:
        allx[c] = allx[c].astype("category").cat.set_categories(tr[c].cat.categories)
    leads["propensity"] = m1.predict_proba(allx[feats])[:, 1]
    leads["propensity_band"] = pd.qcut(
        leads["propensity"], [0, .5, .8, .95, 1.0],
        labels=["Low", "Medium", "High", "Priority"], duplicates="drop")
    scored = leads[["lead_external_id", "lead_source", "province", "channel",
                    "created_date", "target", "propensity", "propensity_band"]]
    scored.to_parquet(OUT / "lead_propensity.parquet", index=False)
    scored.to_parquet(PBI / "ml_lead_propensity.parquet", index=False,
                      compression="zstd")

    # ---------------------------------------------------------------- 2 ----
    # Withdrawal risk from the first four weeks only.
    print("\nbuilding withdrawal risk dataset...")
    risk = con.sql("""
        with early as (
            select enrolment_external_id,
                   avg(attendance_pct)            as att_1_4,
                   min(attendance_pct)            as att_min,
                   avg(assessment_average_pct)    as ass_1_4,
                   sum(overdue_assignments)       as overdue_1_4,
                   max(week_number)               as weeks_seen
            from main_gold.fct_student_progress_weekly
            where week_number <= 4
            group by 1
        )
        select e.enrolment_external_id,
               e.att_1_4, e.att_min, e.ass_1_4, e.overdue_1_4,
               en.agreed_fee_zar,
               d.programme_title, d.delivery_mode, d.category,
               en.status                                   as enrolment_status,
               case when en.status = 'Withdrawn' then 1 else 0 end as target,
               en.enrolled_date
        from early e
        join main_silver.stg_enrolment en using (enrolment_external_id)
        left join main_silver.stg_intake i on i.intake_external_id = en.intake_external_id
        left join main_gold.dim_offering d on d.offering_external_id = i.offering_external_id
        where e.weeks_seen >= 3
    """).df()

    cut2 = risk["enrolled_date"].quantile(0.75)
    tr2 = risk[risk["enrolled_date"] < cut2].copy()
    te2 = risk[risk["enrolled_date"] >= cut2].copy()
    feats2 = ["att_1_4", "att_min", "ass_1_4", "overdue_1_4",
              "agreed_fee_zar"] + CAT_RISK[:-1]
    m2, r2 = fit_score(tr2, te2, feats2, CAT_RISK[:-1], "target",
                       "Withdrawal risk from weeks 1-4", n_leaves=31)
    report["models"].append(r2)

    allr = risk.copy()
    for c in CAT_RISK[:-1]:
        allr[c] = allr[c].astype("category").cat.set_categories(tr2[c].cat.categories)
    risk["withdrawal_risk"] = m2.predict_proba(allr[feats2])[:, 1]
    risk["risk_band"] = pd.cut(risk["withdrawal_risk"], [-0.01, .1, .25, .5, 1.0],
                               labels=["Low", "Watch", "Elevated", "Intervene"])
    out2 = risk[["enrolment_external_id", "programme_title", "delivery_mode",
                 "att_1_4", "ass_1_4", "overdue_1_4", "enrolment_status",
                 "target", "withdrawal_risk", "risk_band"]]
    out2.to_parquet(OUT / "withdrawal_risk.parquet", index=False)
    out2.to_parquet(PBI / "ml_withdrawal_risk.parquet", index=False,
                    compression="zstd")

    # ---------------------------------------------------------------- 3 ----
    # Insights worth acting on, derived rather than asserted.
    ins = []
    band = scored.groupby("propensity_band", observed=True)["target"].agg(["count", "mean"])
    if "Priority" in band.index and "Low" in band.index:
        pr, lo = band.loc["Priority"], band.loc["Low"]
        ins.append({
            "area": "Marketing",
            "finding": f"The top 5% of leads by propensity convert at "
                       f"{pr['mean']*100:.1f}%, against {lo['mean']*100:.1f}% "
                       f"in the bottom half - a {pr['mean']/max(lo['mean'],1e-9):.0f}x "
                       f"difference.",
            "recommendation": "Route the Priority band to human follow-up within "
                              "24 hours and leave the Low band to automated "
                              "nurture. The same team covers more pipeline "
                              "without more headcount."})

    src = (scored.groupby("lead_source", observed=True)["target"]
           .agg(["count", "mean"]).sort_values("mean", ascending=False))
    if len(src) > 1:
        best, worst = src.index[0], src.index[-1]
        ins.append({
            "area": "Channel mix",
            "finding": f"{best} converts at {src.loc[best,'mean']*100:.1f}% "
                       f"versus {worst} at {src.loc[worst,'mean']*100:.1f}%, "
                       f"on {src.loc[worst,'count']:,.0f} leads.",
            "recommendation": f"Rebalance spend toward {best}, and either fix "
                              f"the qualification criteria on {worst} or stop "
                              f"paying for it."})

    hi = risk[risk["risk_band"].isin(["Elevated", "Intervene"])]
    if len(hi):
        ins.append({
            "area": "Retention",
            "finding": f"{len(hi):,} enrolments ({len(hi)/len(risk)*100:.1f}%) "
                       f"are flagged Elevated or Intervene from weeks 1-4 alone, "
                       f"and they withdraw at {hi['target'].mean()*100:.1f}% "
                       f"against {risk['target'].mean()*100:.1f}% overall.",
            "recommendation": "Trigger outreach at week 4 rather than at the "
                              "first missed assessment. The signal is present "
                              "before the student is far enough behind to "
                              "recover from."})

    att = risk.groupby(pd.cut(risk["att_1_4"], [0, 50, 65, 80, 100]),
                       observed=True)["target"].mean()
    if len(att.dropna()) > 1:
        ins.append({
            "area": "Early warning",
            "finding": "Withdrawal rate by weeks 1-4 attendance: " +
                       ", ".join(f"{str(k)} {v*100:.1f}%" for k, v in att.items()),
            "recommendation": "Attendance below 65% in the first month is the "
                              "single clearest trigger. It needs no model to "
                              "act on - the model only tells you how much of "
                              "the remaining risk it explains."})

    report["insights"] = ins
    (OUT / "model_report.json").write_text(json.dumps(report, indent=2),
                                           encoding="utf-8")

    print("\ninsights")
    for i in ins:
        print(f"  [{i['area']}] {i['finding']}")

    print(f"\n  scored files in {OUT} and {PBI}")
    print(f"  report {OUT / 'model_report.json'}")


if __name__ == "__main__":
    main()
