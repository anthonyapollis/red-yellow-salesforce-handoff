{#- One row per opportunity, carrying the whole enquiry-to-enrolment journey. #}
select
    o.opportunity_external_id,
    o.contact_external_id,
    c.province,
    c.acquisition_path,
    o.primary_campaign_external_id,
    o.intake_external_id,
    i.offering_external_id,
    d.programme_title,
    d.category,
    d.delivery_mode,
    d.advertised_fee_zar,
    o.stage_name,
    o.created_date       as opportunity_created_date,
    o.close_date,
    o.days_to_close,
    o.expected_value_zar,
    o.is_won,
    a.application_external_id,
    a.submitted_date,
    a.decision_date,
    a.status             as application_status,
    a.days_to_decision,
    a.is_date_inverted,
    e.enrolment_external_id,
    e.enrolled_date,
    e.agreed_fee_zar,
    e.status             as enrolment_status,
    case when e.enrolment_external_id is not null then 1 else 0 end as is_enrolled,
    case when e.agreed_fee_zar is not null and d.advertised_fee_zar > 0
         then round(100.0 * (d.advertised_fee_zar - e.agreed_fee_zar)
                    / d.advertised_fee_zar, 2) end as discount_pct
from {{ ref('stg_opportunity') }} o
left join {{ ref('dim_contact') }} c  using (contact_external_id)
left join {{ ref('stg_intake') }} i   using (intake_external_id)
left join {{ ref('dim_offering') }} d using (offering_external_id)
left join {{ ref('stg_application') }} a using (opportunity_external_id)
left join {{ ref('stg_enrolment') }} e using (application_external_id)
