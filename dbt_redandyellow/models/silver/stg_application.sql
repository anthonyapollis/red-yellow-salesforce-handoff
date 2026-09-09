with src as (select * from {{ ref('br_application') }})
select
    application_external_id,
    opportunity_external_id,
    contact_external_id,
    intake_external_id,
    cast(submitted_date as date) as submitted_date,
    cast(decision_date as date)  as decision_date,
    status,
    -- Decided before submitted: keep the row, flag the impossibility.
    case when decision_date < submitted_date then 1 else 0 end as is_date_inverted,
    case when decision_date >= submitted_date
         then date_diff('day', cast(submitted_date as date), cast(decision_date as date))
         end as days_to_decision,
    case when status = 'Accepted' then 1 else 0 end as is_accepted,
    source_system, source_updated_at, loaded_at,
    {{ ry_is_late_arriving() }} as is_late_arriving
from src
where not is_deleted
