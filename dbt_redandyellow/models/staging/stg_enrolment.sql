with src as (select * from {{ ry_raw('enrolment') }})
select
    enrolment_external_id,
    student_external_id,
    application_external_id,
    intake_external_id,
    cast(enrolled_date as date) as enrolled_date,
    agreed_fee_zar,
    case when agreed_fee_zar is null then 1 else 0 end as is_fee_missing,
    status,
    case when status in ('Active', 'Completed') then 1 else 0 end as is_retained,
    source_system, source_updated_at, loaded_at,
    {{ ry_is_late_arriving() }} as is_late_arriving
from src
where not is_deleted
