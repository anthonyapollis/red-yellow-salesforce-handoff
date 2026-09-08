{{ config(materialized='table') }}
with days as (
    select cast(range as date) as date_day
    from range(date '2022-01-01', date '2028-12-31', interval 1 day)
)
select
    date_day,
    cast(strftime(date_day, '%Y%m%d') as integer) as date_key,
    extract(year from date_day)      as calendar_year,
    extract(month from date_day)     as calendar_month,
    strftime(date_day, '%B')         as month_name,
    extract(quarter from date_day)   as calendar_quarter,
    extract(week from date_day)      as iso_week,
    date_trunc('week', date_day)     as week_start,
    date_trunc('month', date_day)    as month_start,
    case when extract(dow from date_day) in (0, 6) then 1 else 0 end as is_weekend,
    -- SA academic intake rhythm: Feb and Jul are the two big starts.
    case when extract(month from date_day) in (1, 2) then 'Semester 1'
         when extract(month from date_day) in (7, 8) then 'Semester 2'
         else 'Off-cycle' end as intake_season
from days
