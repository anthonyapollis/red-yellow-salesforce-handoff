{#-
  Every quality defect the pipeline detected, as one row per issue, so the
  Power BI data-quality page and the scoring script read from the same place.
  Issue codes match the keys in warehouse/_truth/defects.json.
#}
select 'lead' as entity, lead_external_id as record_id,
       'email_invalid' as issue_code, 'Email failed format validation' as issue_description
from {{ ref('stg_lead') }} where is_email_invalid = 1
union all
select 'contact', contact_external_id, 'email_invalid', 'Email failed format validation'
from {{ ref('stg_contact') }} where is_email_invalid = 1
union all
select 'contact', contact_external_id, 'duplicate_person', 'Duplicate human on person_key'
from {{ ref('stg_contact') }} where is_golden_record = 0
union all
select 'contact', contact_external_id, 'phone_unparseable', 'Phone could not be normalised to E.164'
from {{ ref('stg_contact') }} where phone_e164 is null
union all
select 'contact', contact_external_id, 'province_unknown', 'Province did not map to an official name'
from {{ ref('stg_contact') }} where province = 'Unknown'
union all
select 'campaign_member', campaign_member_external_id, 'duplicate_membership',
       'Same member on the same campaign more than once'
from {{ ref('stg_campaign_member') }} where is_unique_membership = 0
union all
select 'opportunity', opportunity_external_id, 'negative_value', 'Expected value was negative'
from {{ ref('stg_opportunity') }} where is_value_negative = 1
union all
select 'application', application_external_id, 'date_inversion', 'Decision date precedes submission'
from {{ ref('stg_application') }} where is_date_inverted = 1
union all
{#-
  Date inversion is injected into TWO tables, and for a long time only the
  application half was detected - so the ground-truth score reported 0.64
  recall against an injection rate that should be caught almost entirely.
  An enrolment dated before its own application was submitted is the same
  defect, and it needs the join because the two dates live in two tables.
#}
select 'enrolment', e.enrolment_external_id, 'date_inversion',
       'Enrolled before the application was submitted'
from {{ ref('stg_enrolment') }} e
join {{ ref('stg_application') }} a
  on a.application_external_id = e.application_external_id
where e.enrolled_date < a.submitted_date
union all
{#-
  A null fee is only a defect when the catalogue actually advertised a price.
  Offerings priced "Enquire" legitimately carry no amount, and reporting those
  as missing data would flag the catalogue's most careful decision as an error.
#}
select 'enrolment', e.enrolment_external_id, 'fee_missing',
       'Agreed fee is null although the offering has an advertised price'
from {{ ref('stg_enrolment') }} e
join {{ ref('stg_intake') }} i on i.intake_external_id = e.intake_external_id
join {{ ref('dim_offering') }} d on d.offering_external_id = i.offering_external_id
where e.is_fee_missing = 1 and d.advertised_fee_zar is not null
union all
select 'student_progress', progress_external_id, 'attendance_missing', 'Attendance not recorded'
from {{ ref('stg_student_progress') }} where is_attendance_missing = 1
union all
select 'campaign', campaign_external_id, 'late_arriving', 'source_updated_at after loaded_at'
from {{ ref('stg_campaign') }} where is_late_arriving = 1
union all
select 'lead', lead_external_id, 'late_arriving', 'source_updated_at after loaded_at'
from {{ ref('stg_lead') }} where is_late_arriving = 1
