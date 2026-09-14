{#-
  The catalogue, flattened: programme identity + how it is delivered.
  Intakes are counted in a subquery, NOT joined directly - joining the intake
  table here would silently fan this dimension out to one row per intake and
  quietly multiply every downstream fact that joins it.
#}
with intake_counts as (
    select offering_external_id, count(*) as dated_intake_count
    from {{ ref('stg_intake') }}
    group by offering_external_id
)
select
    o.offering_external_id,
    o.programme_external_id,
    p.programme_title,
    p.category,
    p.listed_body,
    o.offering_title,
    o.catalogue_section,
    o.delivery_mode,
    o.study_pace,
    o.duration_value,
    o.duration_unit,
    o.advertised_fee_zar,
    o.price_status,
    o.is_price_on_enquiry,
    o.source_url,
    o.observed_date,
    coalesce(ic.dated_intake_count, 0) as dated_intake_count
from {{ ref('stg_programme_offering') }} o
left join {{ ref('stg_programme') }} p on p.programme_external_id = o.programme_external_id
left join intake_counts ic on ic.offering_external_id = o.offering_external_id
