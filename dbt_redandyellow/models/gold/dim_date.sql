{{ config(materialized='table') }}
{#- Every engine-specific date expression goes through a ry_* dialect macro, so
    this one model builds on DuckDB, Fabric and BigQuery. #}
with days as (
    {{ ry_date_spine('2022-01-01', '2028-12-31') }}
)
select
    date_day,
    {{ ry_date_key('date_day') }}      as date_key,
    {{ ry_year('date_day') }}          as calendar_year,
    {{ ry_month('date_day') }}         as calendar_month,
    {{ ry_month_name('date_day') }}    as month_name,
    {{ ry_quarter('date_day') }}       as calendar_quarter,
    {{ ry_iso_week('date_day') }}      as iso_week,
    {{ ry_week_start('date_day') }}    as week_start,
    {{ ry_month_start('date_day') }}   as month_start,
    {{ ry_is_weekend('date_day') }}    as is_weekend,
    -- SA academic intake rhythm: Feb and Jul are the two big starts.
    case when {{ ry_month('date_day') }} in (1, 2) then 'Semester 1'
         when {{ ry_month('date_day') }} in (7, 8) then 'Semester 2'
         else 'Off-cycle' end as intake_season
from days
