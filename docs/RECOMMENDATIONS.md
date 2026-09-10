# Recommendations and solutions

This register translates the Red & Yellow analytics signals into actions. The people and campaign outcomes are synthetic; the operating method and controls are the deliverable.

| Area | Signal | Solution | Owner | Success measure |
|---|---|---|---|---|
| Acquisition | Channel response, enrolment rate and revenue per member diverge. | Test budget toward the strongest channel and set a stop rule for spend without response. | Marketing | ROAS, spend per response and revenue per member |
| Admissions | Priority propensity leads convert at a higher rate than lower bands. | Route Priority leads to a named human queue within 24 hours; keep Low-band leads in automated nurture. | Admissions | Response SLA, conversion rate and top-band lift |
| Student success | First-month attendance below 65% is associated with higher withdrawal. | Trigger a week-4 support conversation, log the intervention and compare against the prior cohort. | Student success | Week-4 attendance and withdrawal rate |
| CRM quality | Blank-only filters, duplicate people and missing contact fields weaken follow-up. | Require external IDs, email and campaign membership at capture; send exceptions to a daily queue. | CRM + Data | Email completeness, duplicate rate and issue SLA |
| Catalogue | Enquire-for-price offerings do not have a defensible numeric fee. | Keep the fee null with a price status; add a value only when verified from the public source. | Data stewardship | No unknown price reported as zero |
| Platform | Bronze is verified; Fabric silver/gold execution and GA4 remain gated. | Finish DuckDB-to-T-SQL compatibility work, rerun dbt in Fabric, then add GA4 as a separate dated bronze source. | Data engineering | Passing Fabric run and reconciled GA4 campaign mart |

## 90-day implementation

1. **Days 0-30 - Stabilise.** Confirm CRM field rules, remove blank-bound slicers, assign the Priority queue and baseline the KPI cards.
2. **Days 31-60 - Test.** Run channel and follow-up holdouts, log student-support interventions and keep spend and cohort definitions fixed.
3. **Days 61-90 - Scale.** Promote only interventions that beat baseline, publish the weekly action list and monitor model drift by delivery mode and channel.

Model scores order a human worklist. They must not make automated adverse decisions. Record the intervention and outcome so each recommendation can be challenged and improved.
