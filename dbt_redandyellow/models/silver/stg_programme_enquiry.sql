with src as (select * from {{ ref('br_programme_enquiry') }})
select
    enquiry_external_id,
    contact_external_id,
    offering_external_id,
    cast(enquiry_date as date) as enquiry_date,
    channel,
    status,
    source_system, source_updated_at, loaded_at,
    {{ ry_is_late_arriving() }} as is_late_arriving
from src
where {{ ry_is_false('is_deleted') }}
