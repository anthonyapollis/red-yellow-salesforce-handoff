{#- Same person added to the same campaign twice is deduped on the natural key. #}
with src as (select * from {{ ref('br_campaign_member') }}),

deduped as (
    select *,
        row_number() over (
            partition by campaign_external_id,
                         coalesce(lead_external_id, contact_external_id)
            order by first_responded_date, campaign_member_external_id
        ) as member_seq
    from src
    where {{ ry_is_false('is_deleted') }}
)

select
    campaign_member_external_id,
    campaign_external_id,
    lead_external_id,
    contact_external_id,
    response_status,
    cast(first_responded_date as date) as first_responded_date,
    case when response_status in ('Clicked', 'Responded') then 1 else 0 end as is_engaged,
    case when member_seq = 1 then 1 else 0 end as is_unique_membership,
    source_system, source_updated_at, loaded_at,
    {{ ry_is_late_arriving() }} as is_late_arriving
from deduped
