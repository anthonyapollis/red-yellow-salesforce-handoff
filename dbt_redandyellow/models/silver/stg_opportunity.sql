with src as (select * from {{ ref('br_opportunity') }})
select
    opportunity_external_id,
    contact_external_id,
    intake_external_id,
    primary_campaign_external_id,
    stage_name,
    -- A negative expected value is a data-entry defect, not a refund.
    case when expected_value_zar < 0 then null else expected_value_zar end as expected_value_zar,
    case when expected_value_zar < 0 then 1 else 0 end as is_value_negative,
    cast(created_date as date) as created_date,
    cast(close_date as date)   as close_date,
    is_won,
    case when stage_name in ('Closed Won', 'Closed Lost') then 1 else 0 end as is_closed,
    {{ ry_date_diff_days('cast(created_date as date)', 'cast(close_date as date)') }} as days_to_close,
    source_system, source_updated_at, loaded_at,
    {{ ry_is_late_arriving() }} as is_late_arriving
from src
where {{ ry_is_false('is_deleted') }}
