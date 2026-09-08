{#
  The failure this guards against is silent: if spend were joined before
  aggregation, total spend in the fact would exceed total spend in the
  dimension. Comparing the two totals catches it immediately.
#}
with fact as (select sum(spend_zar) as s from {{ ref('fct_campaign_performance') }}),
     dim  as (select sum(spend_zar) as s from {{ ref('dim_campaign') }})
select fact.s as fact_spend, dim.s as dim_spend
from fact cross join dim
where abs(coalesce(fact.s, 0) - coalesce(dim.s, 0)) > 1
