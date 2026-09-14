{#- Weekly academic health, with the at-risk definition applied consistently. #}
select
    p.progress_external_id,
    p.enrolment_external_id,
    e.student_external_id,
    e.intake_external_id,
    d.programme_title,
    d.delivery_mode,
    p.week_start,
    p.week_number,
    p.attendance_pct,
    p.assessment_average_pct,
    p.overdue_assignments,
    p.risk_band,
    p.is_attendance_missing,
    e.status as enrolment_status,
    case when p.attendance_pct < 55 or p.assessment_average_pct < 50
              or p.overdue_assignments >= 3
         then 1 else 0 end as is_at_risk,
    avg(p.attendance_pct) over (
        partition by p.enrolment_external_id
        order by p.week_number
        rows between 3 preceding and current row
    ) as attendance_4wk_avg
from {{ ref('stg_student_progress') }} p
join {{ ref('stg_enrolment') }} e on e.enrolment_external_id = p.enrolment_external_id
left join {{ ref('stg_intake') }} i on i.intake_external_id = e.intake_external_id
left join {{ ref('dim_offering') }} d on d.offering_external_id = i.offering_external_id
