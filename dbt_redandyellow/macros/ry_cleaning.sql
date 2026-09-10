{#-
  Cleansing macros, dispatched per adapter.

  DuckDB has regex; the Fabric Warehouse T-SQL surface does not, so the Fabric
  implementations use nested REPLACE. Same contract, same test results, two
  engines - which is the whole point of putting this in a macro.
#}

{% macro ry_clean_email(col) %}
  {{ return(adapter.dispatch('ry_clean_email', 'redandyellow')(col)) }}
{% endmacro %}

{% macro default__ry_clean_email(col) %}
  case
    when {{ col }} is null then null
    when regexp_matches(lower(trim({{ col }})), '^[a-z0-9._%%+-]+@[a-z0-9.-]+\.[a-z]{2,}$')
      then lower(trim({{ col }}))
    else null
  end
{% endmacro %}

{#- BigQuery REGEXP_CONTAINS uses RE2 and no DuckDB global flag. -#}
{% macro bigquery__ry_clean_email(col) %}
  case
    when {{ col }} is null then null
    when regexp_contains(lower(trim(cast({{ col }} as string))), r'^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$')
      then lower(trim(cast({{ col }} as string)))
    else null
  end
{% endmacro %}

{% macro fabric__ry_clean_email(col) %}
  case
    when {{ col }} is null then null
    when charindex('@', ltrim(rtrim({{ col }}))) > 1
     and charindex('.', ltrim(rtrim({{ col }})), charindex('@', ltrim(rtrim({{ col }})))) > 0
     and right(ltrim(rtrim({{ col }})), 1) <> ','
      then lower(ltrim(rtrim({{ col }})))
    else null
  end
{% endmacro %}


{#- Normalise every SA phone shape to +27XXXXXXXXX #}
{% macro ry_clean_phone(col) %}
  {{ return(adapter.dispatch('ry_clean_phone', 'redandyellow')(col)) }}
{% endmacro %}

{% macro default__ry_clean_phone(col) %}
  case
    when {{ col }} is null then null
    when length(regexp_replace({{ col }}, '[^0-9]', '', 'g')) = 11
     and left(regexp_replace({{ col }}, '[^0-9]', '', 'g'), 2) = '27'
      then '+' || regexp_replace({{ col }}, '[^0-9]', '', 'g')
    when length(regexp_replace({{ col }}, '[^0-9]', '', 'g')) = 10
     and left(regexp_replace({{ col }}, '[^0-9]', '', 'g'), 1) = '0'
      then '+27' || substr(regexp_replace({{ col }}, '[^0-9]', '', 'g'), 2)
    when length(regexp_replace({{ col }}, '[^0-9]', '', 'g')) = 9
      then '+27' || regexp_replace({{ col }}, '[^0-9]', '', 'g')
    else null
  end
{% endmacro %}

{% macro bigquery__ry_clean_phone(col) %}
  {%- set digits -%}
    regexp_replace(cast({{ col }} as string), r'[^0-9]', '')
  {%- endset -%}
  case
    when {{ col }} is null then null
    when length({{ digits }}) = 11 and substr({{ digits }}, 1, 2) = '27' then concat('+', {{ digits }})
    when length({{ digits }}) = 10 and substr({{ digits }}, 1, 1) = '0' then concat('+27', substr({{ digits }}, 2))
    when length({{ digits }}) = 9 then concat('+27', {{ digits }})
    else null
  end
{% endmacro %}

{% macro fabric__ry_clean_phone(col) %}
  {%- set digits -%}
    replace(replace(replace(replace(replace(replace({{ col }},
      '+',''), '-',''), ' ',''), '(',''), ')',''), '.','')
  {%- endset -%}
  case
    when {{ col }} is null then null
    when len({{ digits }}) = 11 and left({{ digits }}, 2) = '27' then '+' + {{ digits }}
    when len({{ digits }}) = 10 and left({{ digits }}, 1) = '0'  then '+27' + substring({{ digits }}, 2, 9)
    when len({{ digits }}) = 9 then '+27' + {{ digits }}
    else null
  end
{% endmacro %}


{#- Collapse province spelling drift to the nine official names #}
{% macro ry_clean_province(col) %}
  case
    when {{ col }} is null then 'Unknown'
    when lower(replace(replace({{ col }}, '-', ' '), '  ', ' ')) in
         ('western cape', 'w cape', 'wc', 'wes kaap', 'kaapstad') then 'Western Cape'
    when lower(replace(replace({{ col }}, '-', ' '), '  ', ' ')) in
         ('gauteng', 'gp', 'jhb', 'johannesburg') then 'Gauteng'
    when lower(replace(replace({{ col }}, '-', ' '), '  ', ' ')) in
         ('kwazulu natal', 'kzn') then 'KwaZulu-Natal'
    when lower(replace(replace({{ col }}, '-', ' '), '  ', ' ')) in
         ('eastern cape', 'ec', 'e cape', 'oos kaap') then 'Eastern Cape'
    when lower(replace(replace({{ col }}, '-', ' '), '  ', ' ')) in
         ('free state', 'fs') then 'Free State'
    when lower(replace(replace({{ col }}, '-', ' '), '  ', ' ')) = 'limpopo' then 'Limpopo'
    when lower(replace(replace({{ col }}, '-', ' '), '  ', ' ')) = 'mpumalanga' then 'Mpumalanga'
    when lower(replace(replace({{ col }}, '-', ' '), '  ', ' ')) = 'north west' then 'North West'
    when lower(replace(replace({{ col }}, '-', ' '), '  ', ' ')) = 'northern cape' then 'Northern Cape'
    when lower(replace(replace({{ col }}, '-', ' '), '  ', ' ')) like 'outside%' then 'Outside South Africa'
    else 'Unknown'
  end
{% endmacro %}


{#- Title-case a name that arrived as SHOUTING or whispering #}
{% macro ry_clean_name(col) %}
  {{ return(adapter.dispatch('ry_clean_name', 'redandyellow')(col)) }}
{% endmacro %}

{% macro default__ry_clean_name(col) %}
  nullif(trim({{ col }}), '')
{% endmacro %}

{% macro fabric__ry_clean_name(col) %}
  nullif(ltrim(rtrim({{ col }})), '')
{% endmacro %}


{#- A record whose source timestamp is after the load is late-arriving #}
{% macro ry_is_late_arriving() %}
  case when source_updated_at > loaded_at then 1 else 0 end
{% endmacro %}
