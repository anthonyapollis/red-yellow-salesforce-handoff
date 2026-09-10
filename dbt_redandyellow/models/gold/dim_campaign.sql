select
    c.campaign_external_id,
    c.campaign_name,
    c.channel,
    c.start_date,
    c.end_date,
    c.spend_zar,
    c.is_spend_missing,
    c.is_active,
    extract(year from c.start_date) as campaign_year,
    {{ ry_date_diff_days('c.start_date', 'c.end_date') }} as duration_days
from {{ ref('stg_campaign') }} c
