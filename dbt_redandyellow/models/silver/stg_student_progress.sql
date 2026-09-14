with src as (select * from {{ ref('br_student_progress') }})
select
    progress_external_id,
    enrolment_external_id,
    cast(week_start as date) as week_start,
    week_number,
    attendance_pct,
    assessment_average_pct,
    overdue_assignments,
    risk_band,
    case when attendance_pct is null then 1 else 0 end as is_attendance_missing,
    source_system, source_updated_at, loaded_at,
    {{ ry_is_late_arriving() }} as is_late_arriving
from src
where {{ ry_is_false('is_deleted') }}
