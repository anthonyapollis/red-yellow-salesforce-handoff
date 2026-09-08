{#-
  On DuckDB the raw layer is read straight off Parquet, so the same models run
  with no ingestion step. On Fabric the raw layer is real tables that NiFi has
  already landed, so we resolve to a normal source().
#}
{% macro ry_raw(table_name) %}
  {%- if target.type == 'duckdb' -%}
    read_parquet('{{ var("raw_path", "../warehouse/raw") }}/{{ table_name }}.parquet')
  {%- else -%}
    {{ source('raw_salesforce', table_name) }}
  {%- endif -%}
{% endmacro %}
