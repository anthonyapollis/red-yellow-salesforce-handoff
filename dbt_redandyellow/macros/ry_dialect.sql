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
  {#- generate_series, not range: DuckDB's range() excludes its end value, so the
      original spine silently stopped at 2028-12-30 - one day short of the 2,557
      the Fabric and BigQuery branches return. It only surfaced when the two
      engines' dim_date row counts were compared. #}
  select cast(generate_series as date) as date_day
  from generate_series(date '{{ start_literal }}', date '{{ end_literal }}', interval 1 day)
{% endmacro %}
{% macro bigquery__ry_date_spine(start_literal, end_literal) %}
  select date_day
  from unnest(generate_date_array(date '{{ start_literal }}', date '{{ end_literal }}')) as date_day
{% endmacro %}
{% macro fabric__ry_date_spine(start_literal, end_literal) %}
  {#- Not a recursive CTE: the Fabric Warehouse rejects them outright ("Recursive
      CTEs are unsupported in this version of Synapse SQL"), so the earlier
      spine could never have built there. generate_series returns the same
      2,557 days, verified against the Warehouse. #}
  select dateadd(day, value, cast('{{ start_literal }}' as date)) as date_day
  from generate_series(0, datediff(day, cast('{{ start_literal }}' as date),
                                        cast('{{ end_literal }}' as date)))
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
  {#- datename returns nvarchar(30), and a Fabric Warehouse TABLE rejects nvarchar
      columns outright ("not supported in this edition") - it only fails once the
      model is materialised, never as a view. varchar keeps it storable. #}
  cast(datename(month, {{ date_col }}) as varchar(20))
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
  dateadd(day, -(((datepart(weekday, {{ date_col }}) + @@datefirst - 1) % 7 + 6) % 7),
          cast({{ date_col }} as date))
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
  case when (datepart(weekday, {{ date_col }}) + @@datefirst - 1) % 7 in (0, 6)
       then 1 else 0 end
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

{#- Added the first time dbt ran against the Fabric Warehouse. T-SQL has no
    boolean type, no EXTRACT and no STRING type; each of these idioms failed
    there while passing silently on DuckDB. #}
{% macro ry_is_true(col) %}
  {{ return(adapter.dispatch('ry_is_true', 'redandyellow')(col)) }}
{% endmacro %}
{% macro default__ry_is_true(col) %}{{ col }}{% endmacro %}
{% macro fabric__ry_is_true(col) %}{{ col }} = 1{% endmacro %}
{% macro ry_is_false(col) %}
  {{ return(adapter.dispatch('ry_is_false', 'redandyellow')(col)) }}
{% endmacro %}
{% macro default__ry_is_false(col) %}not {{ col }}{% endmacro %}
{% macro fabric__ry_is_false(col) %}{{ col }} = 0{% endmacro %}
{% macro ry_year(date_col) %}
  {{ return(adapter.dispatch('ry_year', 'redandyellow')(date_col)) }}
{% endmacro %}
{% macro default__ry_year(date_col) %}extract(year from {{ date_col }}){% endmacro %}
{% macro fabric__ry_year(date_col) %}datepart(year, {{ date_col }}){% endmacro %}
{% macro ry_month(date_col) %}
  {{ return(adapter.dispatch('ry_month', 'redandyellow')(date_col)) }}
{% endmacro %}
{% macro default__ry_month(date_col) %}extract(month from {{ date_col }}){% endmacro %}
{% macro fabric__ry_month(date_col) %}datepart(month, {{ date_col }}){% endmacro %}
{% macro ry_quarter(date_col) %}
  {{ return(adapter.dispatch('ry_quarter', 'redandyellow')(date_col)) }}
{% endmacro %}
{% macro default__ry_quarter(date_col) %}extract(quarter from {{ date_col }}){% endmacro %}
{% macro fabric__ry_quarter(date_col) %}datepart(quarter, {{ date_col }}){% endmacro %}
{% macro ry_text(col) %}
  {{ return(adapter.dispatch('ry_text', 'redandyellow')(col)) }}
{% endmacro %}
{% macro default__ry_text(col) %}cast({{ col }} as varchar){% endmacro %}
{% macro bigquery__ry_text(col) %}cast({{ col }} as string){% endmacro %}
{% macro fabric__ry_text(col) %}cast({{ col }} as varchar(4000)){% endmacro %}
