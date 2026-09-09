with src as (select * from {{ ref('br_campaign') }})
select
    campaign_external_id,
    trim(campaign_name)                                as campaign_name,
    channel,
    cast(start_date as date)                           as start_date,
    cast(end_date as date)                             as end_date,
    case when spend_zar < 0 then null else spend_zar end as spend_zar,
    case when spend_zar is null then 1 else 0 end      as is_spend_missing,
    is_active,
    source_system, source_updated_at, loaded_at, is_deleted,
    {{ ry_is_late_arriving() }}                        as is_late_arriving
from src
where not is_deleted
