with src as (select * from {{ ref('br_student') }})
select
    student_external_id,
    contact_external_id,
    student_number,
    cast(enrolled_first_date as date) as enrolled_first_date,
    source_system, source_updated_at, loaded_at,
    {{ ry_is_late_arriving() }} as is_late_arriving
from src
where not is_deleted
