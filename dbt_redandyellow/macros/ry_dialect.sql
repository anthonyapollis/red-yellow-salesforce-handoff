{#- Small dialect shims keep the model graph portable across DuckDB, Fabric and BigQuery. -#}
{% macro ry_date_diff_days(start_col, end_col) %}
  {{ return(adapter.dispatch('ry_date_diff_days', 'redandyellow')(start_col, end_col)) }}
{% endmacro %}
{% macro default__ry_date_diff_days(start_col, end_col) %}
  date_diff('day', {{ start_col }}, {{ end_col }})
{% endmacro %}
{% macro bigquery__ry_date_diff_days(start_col, end_col) %}
  date_diff({{ end_col }}, {{ start_col }}, day)
{% endmacro %}
{% macro fabric__ry_date_diff_days(start_col, end_col) %}
  datediff(day, {{ start_col }}, {{ end_col }})
{% endmacro %}
{% macro ry_date_spine(start_literal, end_literal) %}
  {{ return(adapter.dispatch('ry_date_spine', 'redandyellow')(start_literal, end_literal)) }}
{% endmacro %}
{% macro default__ry_date_spine(start_literal, end_literal) %}
  select cast(range as date) as date_day
  from range(date '{{ start_literal }}', date '{{ end_literal }}', interval 1 day)
{% endmacro %}
{% macro bigquery__ry_date_spine(start_literal, end_literal) %}
  select date_day
  from unnest(generate_date_array(date '{{ start_literal }}', date '{{ end_literal }}')) as date_day
{% endmacro %}
{% macro fabric__ry_date_spine(start_literal, end_literal) %}
  with days as (
    select cast('{{ start_literal }}' as date) as date_day
    union all
    select dateadd(day, 1, date_day)
    from days
    where date_day < cast('{{ end_literal }}' as date)
  )
  select date_day from days
{% endmacro %}
{% macro ry_date_key(date_col) %}
  {{ return(adapter.dispatch('ry_date_key', 'redandyellow')(date_col)) }}
{% endmacro %}
{% macro default__ry_date_key(date_col) %}
  cast(strftime({{ date_col }}, '%Y%m%d') as integer)
{% endmacro %}
{% macro bigquery__ry_date_key(date_col) %}
  cast(format_date('%Y%m%d', {{ date_col }}) as int64)
{% endmacro %}
{% macro fabric__ry_date_key(date_col) %}
  cast(convert(varchar(8), {{ date_col }}, 112) as int)
{% endmacro %}
{% macro ry_month_name(date_col) %}
  {{ return(adapter.dispatch('ry_month_name', 'redandyellow')(date_col)) }}
{% endmacro %}
{% macro default__ry_month_name(date_col) %}
  strftime({{ date_col }}, '%B')
{% endmacro %}
{% macro bigquery__ry_month_name(date_col) %}
  format_date('%B', {{ date_col }})
{% endmacro %}
{% macro fabric__ry_month_name(date_col) %}
  datename(month, {{ date_col }})
{% endmacro %}
{% macro ry_week_start(date_col) %}
  {{ return(adapter.dispatch('ry_week_start', 'redandyellow')(date_col)) }}
{% endmacro %}
{% macro default__ry_week_start(date_col) %}
  date_trunc('week', {{ date_col }})
{% endmacro %}
{% macro bigquery__ry_week_start(date_col) %}
  date_trunc({{ date_col }}, week(monday))
{% endmacro %}
{% macro fabric__ry_week_start(date_col) %}
  dateadd(day, 1 - datepart(weekday, {{ date_col }}), cast({{ date_col }} as date))
{% endmacro %}
{% macro ry_month_start(date_col) %}
  {{ return(adapter.dispatch('ry_month_start', 'redandyellow')(date_col)) }}
{% endmacro %}
{% macro default__ry_month_start(date_col) %}
  date_trunc('month', {{ date_col }})
{% endmacro %}
{% macro bigquery__ry_month_start(date_col) %}
  date_trunc({{ date_col }}, month)
{% endmacro %}
{% macro fabric__ry_month_start(date_col) %}
  datefromparts(year({{ date_col }}), month({{ date_col }}), 1)
{% endmacro %}
{% macro ry_is_weekend(date_col) %}
  {{ return(adapter.dispatch('ry_is_weekend', 'redandyellow')(date_col)) }}
{% endmacro %}
{% macro default__ry_is_weekend(date_col) %}
  case when extract(dow from {{ date_col }}) in (0, 6) then 1 else 0 end
{% endmacro %}
{% macro bigquery__ry_is_weekend(date_col) %}
  case when extract(dayofweek from {{ date_col }}) in (1, 7) then 1 else 0 end
{% endmacro %}
{% macro fabric__ry_is_weekend(date_col) %}
  case when datepart(weekday, {{ date_col }}) in (1, 7) then 1 else 0 end
{% endmacro %}
{% macro ry_iso_week(date_col) %}
  {{ return(adapter.dispatch('ry_iso_week', 'redandyellow')(date_col)) }}
{% endmacro %}
{% macro default__ry_iso_week(date_col) %}
  extract(week from {{ date_col }})
{% endmacro %}
{% macro bigquery__ry_iso_week(date_col) %}
  extract(isoweek from {{ date_col }})
{% endmacro %}
{% macro fabric__ry_iso_week(date_col) %}
  datepart(iso_week, {{ date_col }})
{% endmacro %}
