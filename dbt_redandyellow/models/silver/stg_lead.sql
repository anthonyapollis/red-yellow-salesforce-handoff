with src as (select * from {{ ref('br_lead') }})
select
    lead_external_id,
    {{ ry_clean_name('first_name') }}                  as first_name,
    {{ ry_clean_name('last_name') }}                   as last_name,
    {{ ry_clean_email('email') }}                      as email,
    case when {{ ry_clean_email('email') }} is null and email is not null
         then 1 else 0 end                             as is_email_invalid,
    {{ ry_clean_phone('phone') }}                      as phone_e164,
    {{ ry_clean_province('province') }}                as province,
    trim(city)                                         as city,
    lead_source,
    lead_status,
    campaign_external_id,
    cast(created_date as date)                         as created_date,
    case when lead_status = 'Converted' then 1 else 0 end as is_converted,
    source_system, source_updated_at, loaded_at, is_deleted,
    {{ ry_is_late_arriving() }}                        as is_late_arriving
from src
where {{ ry_is_false('is_deleted') }}
