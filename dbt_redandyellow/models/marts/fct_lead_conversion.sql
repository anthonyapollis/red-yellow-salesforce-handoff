select
    l.lead_external_id,
    l.lead_source,
    l.lead_status,
    l.province,
    l.campaign_external_id,
    l.created_date,
    l.is_converted,
    c.contact_external_id,
    c.created_date as contact_created_date,
    case when c.contact_external_id is not null
         then date_diff('day', l.created_date, c.created_date) end as days_to_convert,
    case when o.opportunity_external_id is not null then 1 else 0 end as reached_opportunity,
    case when e.enrolment_external_id is not null then 1 else 0 end as reached_enrolment
from {{ ref('stg_lead') }} l
left join {{ ref('stg_contact') }} c
       on c.converted_from_lead_id = l.lead_external_id and c.is_golden_record = 1
left join {{ ref('stg_opportunity') }} o using (contact_external_id)
left join {{ ref('stg_application') }} a using (opportunity_external_id)
left join {{ ref('stg_enrolment') }} e using (application_external_id)
