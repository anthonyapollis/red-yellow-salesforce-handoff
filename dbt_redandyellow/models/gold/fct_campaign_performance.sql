{#-
  Spend is joined ONCE at campaign grain. Aggregating members, opportunities
  and enrolments first, then attaching spend, is the only way to avoid
  multiplying a campaign's cost by its downstream row count - the mistake the
  ERD notes explicitly warn about.
#}
with members as (
    select campaign_external_id,
           count(*)               as members,
           sum(is_engaged)        as engaged_members
    from {{ ref('stg_campaign_member') }}
    where is_unique_membership = 1
    group by campaign_external_id
),

opps as (
    select primary_campaign_external_id as campaign_external_id,
           count(*)                     as opportunities,
           sum(case when {{ ry_is_true('is_won') }} then 1 else 0 end) as won_opportunities,
           sum(expected_value_zar)      as pipeline_value_zar
    from {{ ref('stg_opportunity') }}
    where primary_campaign_external_id is not null
    group by primary_campaign_external_id
),

enrolled as (
    select o.primary_campaign_external_id as campaign_external_id,
           count(distinct e.enrolment_external_id) as enrolments,
           sum(e.agreed_fee_zar)                   as enrolled_revenue_zar
    from {{ ref('stg_enrolment') }} e
    join {{ ref('stg_application') }} a on a.application_external_id = e.application_external_id
    join {{ ref('stg_opportunity') }} o on o.opportunity_external_id = a.opportunity_external_id
    where o.primary_campaign_external_id is not null
    group by o.primary_campaign_external_id
)

select
    c.campaign_external_id,
    c.campaign_name,
    c.channel,
    c.start_date,
    c.campaign_year,
    c.spend_zar,
    coalesce(m.members, 0)          as members,
    coalesce(m.engaged_members, 0)  as engaged_members,
    coalesce(o.opportunities, 0)    as opportunities,
    coalesce(o.won_opportunities, 0) as won_opportunities,
    coalesce(e.enrolments, 0)       as enrolments,
    o.pipeline_value_zar,
    e.enrolled_revenue_zar,
    case when coalesce(m.members, 0) > 0
         then round(100.0 * coalesce(o.opportunities, 0) / m.members, 2) end as member_to_opp_pct,
    case when coalesce(o.opportunities, 0) > 0
         then round(100.0 * coalesce(e.enrolments, 0) / o.opportunities, 2) end as opp_to_enrol_pct,
    case when c.spend_zar > 0 and coalesce(e.enrolments, 0) > 0
         then round(c.spend_zar / e.enrolments, 2) end as cost_per_enrolment_zar,
    case when c.spend_zar > 0 and e.enrolled_revenue_zar is not null
         then round(e.enrolled_revenue_zar / c.spend_zar, 2) end as roas
from {{ ref('dim_campaign') }} c
left join members  m on m.campaign_external_id = c.campaign_external_id
left join opps     o on o.campaign_external_id = c.campaign_external_id
left join enrolled e on e.campaign_external_id = c.campaign_external_id
