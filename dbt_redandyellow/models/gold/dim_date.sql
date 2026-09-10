{{ config(materialized='table') }}
with days as (
    {{ ry_date_spine('2022-01-01', '2028-12-31') }}
)
select
    date_day,
    {{ ry_date_key('date_day') }} as date_key,
    extract(year from date_day)      as calendar_year,
    extract(month from date_day)     as calendar_month,
    {{ ry_month_name('date_day') }}         as month_name,
    extract(quarter from date_day)   as calendar_quarter,
    {{ ry_iso_week('date_day') }}      as iso_week,
    {{ ry_week_start('date_day') }}     as week_start,
    {{ ry_month_start('date_day') }}    as month_start,
    {{ ry_is_weekend('date_day') }} as is_weekend,
    -- SA academic intake rhythm: Feb and Jul are the two big starts.
    case when extract(month from date_day) in (1, 2) then 'Semester 1'
         when extract(month from date_day) in (7, 8) then 'Semester 2'
         else 'Off-cycle' end as intake_season
from days
