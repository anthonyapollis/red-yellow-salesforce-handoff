#!/usr/bin/env python3
"""Builds a referentially complete Salesforce load from the generated warehouse.

Why this exists, and why it is not "load the 9.4 million rows":

Salesforce charges data storage per record at roughly 2 KB. A Developer Edition
org has ~5 MB of data storage - about 10,000 records total, across every object.
An Enterprise trial has more, but nothing close to millions. Pushing the full
dataset into the CRM is not a scale problem to engineer around; it is not
possible, and an org that hit its storage ceiling mid-load would leave a
half-populated pipeline with dangling foreign keys.

So the architecture splits the way the job advert describes it:

    Salesforce  = the operational CRM slice. Thousands of records, referentially
                  complete, safe to demo and safe to re-upsert.
    Fabric      = the analytics warehouse. All 9.4M rows, where the volume,
                  the history and the data-quality work actually live.

This script cuts the CRM slice. It starts from contacts, then follows the graph
outward so every foreign key it emits resolves to a record in the same load.

On dirtiness: Salesforce validates Email fields and would reject a malformed
address at insert, so emails are written cleaned (invalid ones become blank -
which is itself the honest representation of an unusable address). Name casing,
whitespace, phone-format drift and missing values are written through as-is,
because Salesforce accepts them and they are exactly the mess a real CRM holds.

    python prepare_crm_load.py --budget 25000
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "warehouse" / "redandyellow.duckdb"
OUT = REPO / "data" / "crm_load"

# Proportions of the record budget. Progress rows are capped hard because they
# fan out per enrolment per week and would otherwise eat the whole allowance.
MIX = {
    "Account": 0.010,
    "Campaign": 0.020,
    "Lead": 0.170,
    "Contact": 0.170,
    "CampaignMember": 0.180,
    "Opportunity": 0.130,
    "RY_Programme_Enquiry__c": 0.080,
    "RY_Application__c": 0.090,
    "RY_Student__c": 0.035,
    "RY_Enrolment__c": 0.035,
    "RY_Student_Progress__c": 0.080,
}

HEADERS = {
    "Account": ["RY_External_ID__c", "Name"],
    "Campaign": ["RY_External_ID__c", "Name", "IsActive", "StartDate",
                 "RY_Channel__c", "RY_Spend_ZAR__c"],
    "Contact": ["RY_External_ID__c", "FirstName", "LastName", "Email", "Account_Key"],
    "Lead": ["RY_External_ID__c", "FirstName", "LastName", "Company", "Email",
             "RY_Sample_Status__c"],
    "CampaignMember": ["RY_External_ID__c", "Campaign_Key", "Contact_Key", "Lead_Key"],
    "Opportunity": ["RY_External_ID__c", "Name", "Account_Key", "Applicant_Key",
                    "Campaign_Key", "Intake_Key", "CloseDate", "RY_Sample_Stage__c",
                    "RY_Expected_Value_ZAR__c"],
    "RY_Programme_Enquiry__c": ["RY_External_ID__c", "Contact_Key", "Lead_Key",
                                "Offering_Key", "Enquiry_Date__c", "Channel__c", "Status__c"],
    "RY_Application__c": ["RY_External_ID__c", "Contact_Key", "Intake_Key",
                          "Opportunity_Key", "Submitted_Date__c", "Status__c",
                          "Decision_Date__c"],
    "RY_Student__c": ["RY_External_ID__c", "Contact_Key", "Student_Number__c"],
    "RY_Enrolment__c": ["RY_External_ID__c", "Student_Key", "Application_Key",
                        "Enrolled_Date__c", "Status__c", "Agreed_Fee_ZAR__c"],
    "RY_Student_Progress__c": ["RY_External_ID__c", "Enrolment_Key", "Week_Start__c",
                               "Attendance_Pct__c", "Assessment_Average_Pct__c",
                               "Overdue_Assignments__c", "Risk_Band__c"],
}

# Employers and sponsors that fund staff study - gives Account something real to be.
SPONSORS = [
    "Woolworths Holdings", "Discovery Limited", "Capitec Bank", "Takealot Group",
    "Nando's Group", "Investec", "MultiChoice", "Shoprite Holdings", "Sanlam",
    "Old Mutual", "Vodacom", "Standard Bank", "Clicks Group", "Tiger Brands",
    "Distell", "Mediclinic", "Bidvest", "Pick n Pay", "Nedbank", "Telkom",
    "Momentum Metropolitan", "Aspen Pharmacare", "Dis-Chem", "Massmart",
    "Cape Union Mart",
]


def w(df: pd.DataFrame, name: str) -> int:
    """Write one object CSV with exactly the columns the import plan expects."""
    OUT.mkdir(parents=True, exist_ok=True)
    cols = HEADERS[name]
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    df = df[cols]
    # Salesforce reads an empty cell as null; NaN would upsert the string "nan".
    df.to_csv(OUT / f"{name}.csv", index=False, na_rep="")
    print(f"  {name:<26} {len(df):>8,} rows")
    return len(df)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--budget", type=int, default=2_400,
                    help="Total Salesforce records to emit. Default 2,400 (~4.7 MB) fits a "
                         "Developer Edition org's 5 MB ceiling. Raise it only for an org "
                         "you have confirmed has the storage.")
    args = ap.parse_args()

    if not DB.exists():
        raise SystemExit(f"warehouse not built - run generate.py then dbt run first ({DB})")

    n = {k: max(int(args.budget * v), 1) for k, v in MIX.items()}
    con = duckdb.connect(str(DB), read_only=True)
    print(f"\nCutting a {args.budget:,}-record CRM slice from the warehouse")
    print(f"output: {OUT}\n")
    total = 0

    # -- Accounts: sponsoring employers -------------------------------------
    acc = pd.DataFrame({
        "RY_External_ID__c": [f"RY-ACC-{i:04d}" for i in range(1, len(SPONSORS) + 1)],
        "Name": SPONSORS,
    })
    total += w(acc, "Account")

    # -- Campaigns ----------------------------------------------------------
    camp = con.sql(f"""
        select campaign_external_id as "RY_External_ID__c",
               campaign_name        as "Name",
               is_active            as "IsActive",
               start_date           as "StartDate",
               channel              as "RY_Channel__c",
               spend_zar            as "RY_Spend_ZAR__c"
        from main_marts.dim_campaign
        order by start_date desc
        limit {n['Campaign']}
    """).df()
    total += w(camp.copy(), "Campaign")
    camp_ids = set(camp["RY_External_ID__c"])

    # -- Contacts -----------------------------------------------------------
    # Raw names and casing are kept; only the email is cleaned, because
    # Salesforce rejects a malformed address outright.
    con_df = con.sql(f"""
        select c.contact_external_id as "RY_External_ID__c",
               r.first_name          as "FirstName",
               r.last_name           as "LastName",
               c.email               as "Email"
        from main_marts.dim_contact c
        join read_parquet('{(REPO / "warehouse" / "raw" / "contact.parquet").as_posix()}') r
          on r.contact_external_id = c.contact_external_id
        order by c.created_date desc
        limit {n['Contact']}
    """).df()
    con_df["LastName"] = con_df["LastName"].fillna("Unknown").replace("", "Unknown")
    con_df["Account_Key"] = [acc["RY_External_ID__c"].iloc[i % len(acc)] if i % 3 == 0 else ""
                             for i in range(len(con_df))]
    total += w(con_df.copy(), "Contact")
    contact_ids = set(con_df["RY_External_ID__c"])

    # -- Leads --------------------------------------------------------------
    lead = con.sql(f"""
        select l.lead_external_id as "RY_External_ID__c",
               r.first_name       as "FirstName",
               r.last_name        as "LastName",
               l.email            as "Email",
               l.lead_status      as "RY_Sample_Status__c"
        from main_staging.stg_lead l
        join read_parquet('{(REPO / "warehouse" / "raw" / "lead.parquet").as_posix()}') r
          on r.lead_external_id = l.lead_external_id
        order by l.created_date desc
        limit {n['Lead']}
    """).df()
    lead["LastName"] = lead["LastName"].fillna("Unknown").replace("", "Unknown")
    # Company is required on Lead. These are individual students, so the honest
    # value is a marker, not an invented employer.
    lead["Company"] = "[Individual Applicant]"
    total += w(lead.copy(), "Lead")
    lead_ids = set(lead["RY_External_ID__c"])

    # -- Opportunities: only for contacts already in the load ---------------
    opp = con.sql(f"""
        select f.opportunity_external_id       as "RY_External_ID__c",
               f.programme_title || ' - ' || coalesce(f.stage_name, 'Enquiry') as "Name",
               f.contact_external_id           as "Applicant_Key",
               f.primary_campaign_external_id  as "Campaign_Key",
               f.intake_external_id            as "Intake_Key",
               f.close_date                    as "CloseDate",
               f.stage_name                    as "RY_Sample_Stage__c",
               f.expected_value_zar            as "RY_Expected_Value_ZAR__c"
        from main_marts.fct_admissions_funnel f
        where f.contact_external_id in ({','.join(repr(x) for x in contact_ids)})
        order by f.opportunity_created_date desc
        limit {n['Opportunity']}
    """).df()
    opp["Campaign_Key"] = opp["Campaign_Key"].where(opp["Campaign_Key"].isin(camp_ids), "")
    opp["Name"] = opp["Name"].fillna("Programme Enquiry")
    total += w(opp.copy(), "Opportunity")
    opp_ids = set(opp["RY_External_ID__c"])

    # -- Campaign members: both ends must already be in the load ------------
    cm = con.sql(f"""
        select campaign_member_external_id as "RY_External_ID__c",
               campaign_external_id        as "Campaign_Key",
               contact_external_id         as "Contact_Key",
               lead_external_id            as "Lead_Key"
        from main_staging.stg_campaign_member
        where is_unique_membership = 1
          and campaign_external_id in ({','.join(repr(x) for x in camp_ids)})
          and (contact_external_id in ({','.join(repr(x) for x in contact_ids)})
            or lead_external_id in ({','.join(repr(x) for x in lead_ids)}))
        limit {n['CampaignMember']}
    """).df()
    cm["Contact_Key"] = cm["Contact_Key"].where(cm["Contact_Key"].isin(contact_ids), "")
    cm["Lead_Key"] = cm["Lead_Key"].where(cm["Lead_Key"].isin(lead_ids), "")
    total += w(cm.copy(), "CampaignMember")

    # -- Enquiries ----------------------------------------------------------
    enq = con.sql(f"""
        select enquiry_external_id  as "RY_External_ID__c",
               contact_external_id  as "Contact_Key",
               offering_external_id as "Offering_Key",
               enquiry_date         as "Enquiry_Date__c",
               channel              as "Channel__c",
               status               as "Status__c"
        from main_staging.stg_programme_enquiry
        where contact_external_id in ({','.join(repr(x) for x in contact_ids)})
        limit {n['RY_Programme_Enquiry__c']}
    """).df()
    total += w(enq.copy(), "RY_Programme_Enquiry__c")

    # -- Applications -> Students -> Enrolments -> Progress ------------------
    app = con.sql(f"""
        select application_external_id as "RY_External_ID__c",
               contact_external_id     as "Contact_Key",
               intake_external_id      as "Intake_Key",
               opportunity_external_id as "Opportunity_Key",
               submitted_date          as "Submitted_Date__c",
               status                  as "Status__c",
               decision_date           as "Decision_Date__c"
        from main_staging.stg_application
        where opportunity_external_id in ({','.join(repr(x) for x in opp_ids)})
        limit {n['RY_Application__c']}
    """).df()
    total += w(app.copy(), "RY_Application__c")
    app_ids = set(app["RY_External_ID__c"])

    stu = con.sql(f"""
        select s.student_external_id as "RY_External_ID__c",
               s.contact_external_id as "Contact_Key",
               s.student_number      as "Student_Number__c"
        from main_staging.stg_student s
        join main_staging.stg_enrolment e
          on e.student_external_id = s.student_external_id
        where e.application_external_id in ({','.join(repr(x) for x in app_ids)})
        limit {n['RY_Student__c']}
    """).df()
    total += w(stu.copy(), "RY_Student__c")
    stu_ids = set(stu["RY_External_ID__c"])

    enr = con.sql(f"""
        select enrolment_external_id   as "RY_External_ID__c",
               student_external_id     as "Student_Key",
               application_external_id as "Application_Key",
               enrolled_date           as "Enrolled_Date__c",
               status                  as "Status__c",
               agreed_fee_zar          as "Agreed_Fee_ZAR__c"
        from main_staging.stg_enrolment
        where student_external_id in ({','.join(repr(x) for x in stu_ids)})
          and application_external_id in ({','.join(repr(x) for x in app_ids)})
        limit {n['RY_Enrolment__c']}
    """).df()
    total += w(enr.copy(), "RY_Enrolment__c")
    enr_ids = set(enr["RY_External_ID__c"])

    prog = con.sql(f"""
        select progress_external_id   as "RY_External_ID__c",
               enrolment_external_id  as "Enrolment_Key",
               week_start             as "Week_Start__c",
               attendance_pct         as "Attendance_Pct__c",
               assessment_average_pct as "Assessment_Average_Pct__c",
               overdue_assignments    as "Overdue_Assignments__c",
               risk_band              as "Risk_Band__c"
        from main_staging.stg_student_progress
        where enrolment_external_id in ({','.join(repr(x) for x in enr_ids)})
        order by enrolment_external_id, week_number
        limit {n['RY_Student_Progress__c']}
    """).df()
    total += w(prog.copy(), "RY_Student_Progress__c")

    # -- import plan for this folder ----------------------------------------
    base = json.loads((REPO / "salesforce" / "import_plan.json").read_text(encoding="utf-8"))
    by_obj = {p["object"]: p for p in base}
    plan = []
    for obj in HEADERS:
        p = dict(by_obj.get(obj, {"object": obj, "external_id": "RY_External_ID__c",
                                  "references": {}, "required": []}))
        p["file"] = f"data/crm_load/{obj}.csv"
        p["group"] = "crm_load"
        plan.append(p)
    (OUT / "import_plan.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")

    print(f"\n  {'TOTAL':<26} {total:>8,} records")
    print(f"  storage estimate           ~{total * 2 / 1024:.1f} MB at 2 KB/record")
    print(f"\n  plan: {OUT / 'import_plan.json'}")
    print("\nNext: tools/import_salesforce.py --preflight  (reads org metadata, writes nothing)")


if __name__ == "__main__":
    main()
