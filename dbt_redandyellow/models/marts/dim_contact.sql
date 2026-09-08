{#- One row per human. Duplicates collapse onto the golden record. #}
select
    c.contact_external_id,
    c.person_key,
    c.first_name,
    c.last_name,
    coalesce(c.first_name, '') || ' ' || coalesce(c.last_name, '') as full_name,
    c.email,
    c.phone_e164,
    c.province,
    c.city,
    c.created_date,
    c.person_record_count,
    case when c.person_record_count > 1 then 1 else 0 end as has_duplicates,
    case when c.converted_from_lead_id is not null then 'Converted Lead'
         else 'Direct' end as acquisition_path,
    c.is_email_invalid,
    c.is_late_arriving
from {{ ref('stg_contact') }} c
where c.is_golden_record = 1
