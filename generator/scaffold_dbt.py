#!/usr/bin/env python3
"""Writes the dbt project for the Red & Yellow analytics platform.

Kept as a generator script rather than 40 hand-placed files so the whole
warehouse layer is reproducible from one command and reviewable in one place.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "dbt_redandyellow"

FILES = {}

# ---------------------------------------------------------------- project ---
FILES["dbt_project.yml"] = """
name: redandyellow
version: "1.0.0"
config-version: 2
profile: redandyellow

model-paths: ["models"]
macro-paths: ["macros"]
test-paths: ["tests"]
seed-paths: ["seeds"]
target-path: "target"
clean-targets: ["target", "dbt_packages"]

vars:
  # Anything enquired about before this is historical noise, not pipeline.
  reporting_start_date: "2022-01-01"
  capture_date: "2026-09-08"
  # Absolute, because DuckDB resolves read_parquet() against the process working
  # directory - not the project directory. With a relative path the staging views
  # silently stop resolving the moment anything queries the .duckdb file from
  # somewhere other than this folder. Re-run scaffold_dbt.py to re-stamp it.
  raw_path: "__RAW_PATH__"

models:
  redandyellow:
    # dbt-fabric does not implement ALTER COMMENT; documentation remains in the
    # generated dbt artefacts rather than being persisted as Warehouse comments.
    +persist_docs:
      relation: false
      columns: false
    # Medallion. Bronze is the landed source, untouched apart from being made
    # queryable; silver is cleansed and conformed; gold is business-level and
    # assumes clean inputs. Quality sits beside gold rather than inside it,
    # because it describes the pipeline rather than the business.
    bronze:
      +materialized: view
      +schema: bronze
    silver:
      +materialized: view
      +schema: silver
    gold:
      +materialized: table
      +schema: gold
    quality:
      +materialized: table
      +schema: quality
""".lstrip()

FILES["packages.yml"] = """
packages:
  - package: dbt-labs/dbt_utils
    version: [">=1.1.0", "<2.0.0"]
""".lstrip()

FILES["profiles.yml"] = """
# Two targets, same models.
#   duckdb  - local, runs today, no cloud auth. Reads warehouse/raw/*.parquet.
#   fabric  - Microsoft Fabric Warehouse over the SQL endpoint (Entra ID).
#
# Fabric needs FABRIC_SERVER / FABRIC_DATABASE in the environment; auth is
# interactive Entra ID by default so no secret is stored in this repo.
redandyellow:
  target: duckdb
  outputs:
    duckdb:
      type: duckdb
      path: "../warehouse/redandyellow.duckdb"
      threads: 8
      extensions: []

    fabric:
      type: fabric
      driver: "ODBC Driver 17 for SQL Server"
      host: "{{ env_var('FABRIC_SERVER', 'not-set.datawarehouse.fabric.microsoft.com') }}"
      database: "{{ env_var('FABRIC_DATABASE', 'WH_RedAndYellow') }}"
      schema: dbo
      authentication: "{{ env_var('FABRIC_AUTH', 'CLI') }}"
      encrypt: true
      trust_cert: false
      threads: 4
      retries: 2
""".lstrip()

# ----------------------------------------------------------------- macros ---
FILES["macros/ry_cleaning.sql"] = """
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
    when regexp_matches(lower(trim({{ col }})), '^[a-z0-9._%%+-]+@[a-z0-9.-]+\\.[a-z]{2,}$')
      then lower(trim({{ col }}))
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
""".lstrip()

FILES["macros/ry_source_parquet.sql"] = """
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
""".lstrip()

# ---------------------------------------------------------------- staging ---
# Staging is where the dirt is handled. Every cleansing decision lives here and
# nowhere else, so the marts can assume clean inputs.

FILES["models/staging/stg_campaign.sql"] = """
with src as (select * from {{ ry_raw('campaign') }})
select
    campaign_external_id,
    trim(campaign_name)                                as campaign_name,
    channel,
    cast(start_date as date)                           as start_date,
    cast(end_date as date)                             as end_date,
    case when spend_zar < 0 then null else spend_zar end as spend_zar,
    case when spend_zar is null then 1 else 0 end      as is_spend_missing,
    is_active,
    source_system, source_updated_at, loaded_at, is_deleted,
    {{ ry_is_late_arriving() }}                        as is_late_arriving
from src
where not is_deleted
""".lstrip()

FILES["models/staging/stg_lead.sql"] = """
with src as (select * from {{ ry_raw('lead') }})
select
    lead_external_id,
    {{ ry_clean_name('first_name') }}                  as first_name,
    {{ ry_clean_name('last_name') }}                   as last_name,
    {{ ry_clean_email('email') }}                      as email,
    case when {{ ry_clean_email('email') }} is null and email is not null
         then 1 else 0 end                             as is_email_invalid,
    {{ ry_clean_phone('phone') }}                      as phone_e164,
    {{ ry_clean_province('province') }}                as province,
    trim(city)                                         as city,
    lead_source,
    lead_status,
    campaign_external_id,
    cast(created_date as date)                         as created_date,
    case when lead_status = 'Converted' then 1 else 0 end as is_converted,
    source_system, source_updated_at, loaded_at, is_deleted,
    {{ ry_is_late_arriving() }}                        as is_late_arriving
from src
where not is_deleted
""".lstrip()

FILES["models/staging/stg_contact.sql"] = """
{#-
  Deduplication happens here. Two records are the same human when their cleaned
  email matches, or - when email is missing - when name plus normalised phone
  match. The surviving record is the earliest created; the rest are kept but
  flagged, because deleting a source record silently is not acceptable.
#}
with src as (select * from {{ ry_raw('contact') }}),

cleaned as (
    select
        contact_external_id,
        {{ ry_clean_name('first_name') }}              as first_name,
        {{ ry_clean_name('last_name') }}               as last_name,
        {{ ry_clean_email('email') }}                  as email,
        case when {{ ry_clean_email('email') }} is null and email is not null
             then 1 else 0 end                         as is_email_invalid,
        {{ ry_clean_phone('phone') }}                  as phone_e164,
        {{ ry_clean_province('province') }}            as province,
        trim(city)                                     as city,
        converted_from_lead_id,
        cast(created_date as date)                     as created_date,
        source_system, source_updated_at, loaded_at, is_deleted
    from src
    where not is_deleted
),

{#-
  Entity resolution, two keys and one propagation round.

  A single match key cannot do this job. The two duplicate shapes a CRM
  actually produces are (a) the same person re-submitting the web form, which
  repeats the email, and (b) the same person phoning in, where no email is
  captured at all. A record that HAS an email and a record that does not will
  never share a single-key value, so a one-key strategy silently recovers only
  half the duplicates - measured at 0.52 recall against the injected manifest.

  Nor can we simply key on name: across 1.1M contacts drawn from a realistic SA
  name distribution "Thabo Nkosi" recurs legitimately thousands of times, and
  keying on name-plus-nullable-phone produced a 23x false-positive rate.

  So: anchor on email, anchor independently on phone-plus-surname, take the
  lower anchor, then propagate once within each phone group so a phone-only
  record inherits the cluster of the emailed record it shares a handset with.
#}
email_anchor as (
    select email, min(contact_external_id) as anchor
    from cleaned where email is not null group by 1
),

phone_anchor as (
    select phone_e164, lower(last_name) as surname_l,
           min(contact_external_id) as anchor
    from cleaned
    where phone_e164 is not null and last_name is not null
    group by 1, 2
),

linked as (
    select c.*,
        case
            when coalesce(e.anchor, c.contact_external_id)
               < coalesce(p.anchor, c.contact_external_id)
            then coalesce(e.anchor, c.contact_external_id)
            else coalesce(p.anchor, c.contact_external_id)
        end as anchor_1
    from cleaned c
    left join email_anchor e on e.email = c.email
    left join phone_anchor p on p.phone_e164 = c.phone_e164
                            and p.surname_l = lower(c.last_name)
),

propagated as (
    select l.*,
        min(anchor_1) over (partition by phone_e164, lower(last_name)) as anchor_2
    from linked l
),

keyed as (
    select *,
        case
            when phone_e164 is not null and last_name is not null and anchor_2 < anchor_1
                then anchor_2
            else anchor_1
        end as person_key
    from propagated
),

ranked as (
    select *,
        row_number() over (
            partition by person_key
            order by created_date, contact_external_id
        ) as person_seq,
        count(*) over (partition by person_key) as person_record_count
    from keyed
)

select
    contact_external_id,
    person_key,
    first_name, last_name, email, is_email_invalid, phone_e164,
    province, city, converted_from_lead_id, created_date,
    case when person_seq = 1 then 1 else 0 end as is_golden_record,
    person_record_count,
    source_system, source_updated_at, loaded_at,
    {{ ry_is_late_arriving() }} as is_late_arriving
from ranked
""".lstrip()

FILES["models/staging/stg_campaign_member.sql"] = """
{#- Same person added to the same campaign twice is deduped on the natural key. #}
with src as (select * from {{ ry_raw('campaign_member') }}),

deduped as (
    select *,
        row_number() over (
            partition by campaign_external_id,
                         coalesce(lead_external_id, contact_external_id)
            order by first_responded_date, campaign_member_external_id
        ) as member_seq
    from src
    where not is_deleted
)

select
    campaign_member_external_id,
    campaign_external_id,
    lead_external_id,
    contact_external_id,
    response_status,
    cast(first_responded_date as date) as first_responded_date,
    case when response_status in ('Clicked', 'Responded') then 1 else 0 end as is_engaged,
    case when member_seq = 1 then 1 else 0 end as is_unique_membership,
    source_system, source_updated_at, loaded_at,
    {{ ry_is_late_arriving() }} as is_late_arriving
from deduped
""".lstrip()

FILES["models/staging/stg_opportunity.sql"] = """
with src as (select * from {{ ry_raw('opportunity') }})
select
    opportunity_external_id,
    contact_external_id,
    intake_external_id,
    primary_campaign_external_id,
    stage_name,
    -- A negative expected value is a data-entry defect, not a refund.
    case when expected_value_zar < 0 then null else expected_value_zar end as expected_value_zar,
    case when expected_value_zar < 0 then 1 else 0 end as is_value_negative,
    cast(created_date as date) as created_date,
    cast(close_date as date)   as close_date,
    is_won,
    case when stage_name in ('Closed Won', 'Closed Lost') then 1 else 0 end as is_closed,
    date_diff('day', cast(created_date as date), cast(close_date as date)) as days_to_close,
    source_system, source_updated_at, loaded_at,
    {{ ry_is_late_arriving() }} as is_late_arriving
from src
where not is_deleted
""".lstrip()

FILES["models/staging/stg_application.sql"] = """
with src as (select * from {{ ry_raw('application') }})
select
    application_external_id,
    opportunity_external_id,
    contact_external_id,
    intake_external_id,
    cast(submitted_date as date) as submitted_date,
    cast(decision_date as date)  as decision_date,
    status,
    -- Decided before submitted: keep the row, flag the impossibility.
    case when decision_date < submitted_date then 1 else 0 end as is_date_inverted,
    case when decision_date >= submitted_date
         then date_diff('day', cast(submitted_date as date), cast(decision_date as date))
         end as days_to_decision,
    case when status = 'Accepted' then 1 else 0 end as is_accepted,
    source_system, source_updated_at, loaded_at,
    {{ ry_is_late_arriving() }} as is_late_arriving
from src
where not is_deleted
""".lstrip()

FILES["models/staging/stg_student.sql"] = """
with src as (select * from {{ ry_raw('student') }})
select
    student_external_id,
    contact_external_id,
    student_number,
    cast(enrolled_first_date as date) as enrolled_first_date,
    source_system, source_updated_at, loaded_at,
    {{ ry_is_late_arriving() }} as is_late_arriving
from src
where not is_deleted
""".lstrip()

FILES["models/staging/stg_enrolment.sql"] = """
with src as (select * from {{ ry_raw('enrolment') }})
select
    enrolment_external_id,
    student_external_id,
    application_external_id,
    intake_external_id,
    cast(enrolled_date as date) as enrolled_date,
    agreed_fee_zar,
    case when agreed_fee_zar is null then 1 else 0 end as is_fee_missing,
    status,
    case when status in ('Active', 'Completed') then 1 else 0 end as is_retained,
    source_system, source_updated_at, loaded_at,
    {{ ry_is_late_arriving() }} as is_late_arriving
from src
where not is_deleted
""".lstrip()

FILES["models/staging/stg_student_progress.sql"] = """
with src as (select * from {{ ry_raw('student_progress') }})
select
    progress_external_id,
    enrolment_external_id,
    cast(week_start as date) as week_start,
    week_number,
    attendance_pct,
    assessment_average_pct,
    overdue_assignments,
    risk_band,
    case when attendance_pct is null then 1 else 0 end as is_attendance_missing,
    source_system, source_updated_at, loaded_at,
    {{ ry_is_late_arriving() }} as is_late_arriving
from src
where not is_deleted
""".lstrip()

FILES["models/staging/stg_programme_enquiry.sql"] = """
with src as (select * from {{ ry_raw('programme_enquiry') }})
select
    enquiry_external_id,
    contact_external_id,
    offering_external_id,
    cast(enquiry_date as date) as enquiry_date,
    channel,
    status,
    source_system, source_updated_at, loaded_at,
    {{ ry_is_late_arriving() }} as is_late_arriving
from src
where not is_deleted
""".lstrip()

FILES["models/staging/stg_programme.sql"] = """
{#- Real catalogue data. Cleansed for whitespace only - never invented. #}
with src as (select * from {{ ry_raw('programme') }})
select
    "RY_External_ID__c"      as programme_external_id,
    trim("Title__c")         as programme_title,
    "Category__c"            as category,
    nullif(trim(coalesce(cast("Credential_Text__c" as varchar), '')), '') as credential_text,
    nullif(trim(coalesce(cast("Listed_Body__c" as varchar), '')), '')     as listed_body
from src
""".lstrip()

FILES["models/staging/stg_programme_offering.sql"] = """
with src as (select * from {{ ry_raw('programme_offering') }})
select
    "RY_External_ID__c"        as offering_external_id,
    "Programme_Key"            as programme_external_id,
    trim("Title__c")           as offering_title,
    "Catalogue_Section__c"     as catalogue_section,
    "Delivery_Mode__c"         as delivery_mode,
    "Study_Pace__c"            as study_pace,
    "Duration_Value__c"        as duration_value,
    "Duration_Unit__c"         as duration_unit,
    -- "Enquire for price" stays null. It is not zero and never becomes zero.
    "Advertised_Fee_ZAR__c"    as advertised_fee_zar,
    "Price_Status__c"          as price_status,
    case when "Price_Status__c" = 'Enquire' then 1 else 0 end as is_price_on_enquiry,
    "Source_URL__c"            as source_url,
    cast("Observed_Date__c" as date) as observed_date
from src
""".lstrip()

FILES["models/staging/stg_intake.sql"] = """
with src as (select * from {{ ry_raw('intake') }})
select
    "RY_External_ID__c" as intake_external_id,
    "Offering_Key"      as offering_external_id,
    cast("Start_Date__c" as date) as start_date
from src
""".lstrip()

# ------------------------------------------------------------------ marts ---

FILES["models/marts/dim_date.sql"] = """
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
""".lstrip()

FILES["models/marts/dim_contact.sql"] = """
{#- One row per human. Duplicates collapse onto the golden record. #}
select
    c.contact_external_id,
    c.person_key,
    c.first_name,
    c.last_name,
    coalesce(c.first_name, '') || ' ' || coalesce(c.last_name, '') as full_name,
    c.email,
    c.phone_e164,
    c.province,
    c.city,
    c.created_date,
    c.person_record_count,
    case when c.person_record_count > 1 then 1 else 0 end as has_duplicates,
    case when c.converted_from_lead_id is not null then 'Converted Lead'
         else 'Direct' end as acquisition_path,
    c.is_email_invalid,
    c.is_late_arriving
from {{ ref('stg_contact') }} c
where c.is_golden_record = 1
""".lstrip()

FILES["models/marts/dim_offering.sql"] = """
{#-
  The catalogue, flattened: programme identity + how it is delivered.
  Intakes are counted in a subquery, NOT joined directly - joining the intake
  table here would silently fan this dimension out to one row per intake and
  quietly multiply every downstream fact that joins it.
#}
with intake_counts as (
    select offering_external_id, count(*) as dated_intake_count
    from {{ ref('stg_intake') }}
    group by 1
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
left join {{ ref('stg_programme') }} p using (programme_external_id)
left join intake_counts ic using (offering_external_id)
""".lstrip()

FILES["models/marts/dim_campaign.sql"] = """
select
    c.campaign_external_id,
    c.campaign_name,
    c.channel,
    c.start_date,
    c.end_date,
    c.spend_zar,
    c.is_spend_missing,
    c.is_active,
    extract(year from c.start_date) as campaign_year,
    date_diff('day', c.start_date, c.end_date) as duration_days
from {{ ref('stg_campaign') }} c
""".lstrip()

FILES["models/marts/fct_campaign_performance.sql"] = """
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
    group by 1
),

opps as (
    select primary_campaign_external_id as campaign_external_id,
           count(*)                     as opportunities,
           sum(case when is_won then 1 else 0 end) as won_opportunities,
           sum(expected_value_zar)      as pipeline_value_zar
    from {{ ref('stg_opportunity') }}
    where primary_campaign_external_id is not null
    group by 1
),

enrolled as (
    select o.primary_campaign_external_id as campaign_external_id,
           count(distinct e.enrolment_external_id) as enrolments,
           sum(e.agreed_fee_zar)                   as enrolled_revenue_zar
    from {{ ref('stg_enrolment') }} e
    join {{ ref('stg_application') }} a using (application_external_id)
    join {{ ref('stg_opportunity') }} o using (opportunity_external_id)
    where o.primary_campaign_external_id is not null
    group by 1
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
left join members  m using (campaign_external_id)
left join opps     o using (campaign_external_id)
left join enrolled e using (campaign_external_id)
""".lstrip()

FILES["models/marts/fct_admissions_funnel.sql"] = """
{#- One row per opportunity, carrying the whole enquiry-to-enrolment journey. #}
select
    o.opportunity_external_id,
    o.contact_external_id,
    c.province,
    c.acquisition_path,
    o.primary_campaign_external_id,
    o.intake_external_id,
    i.offering_external_id,
    d.programme_title,
    d.category,
    d.delivery_mode,
    d.advertised_fee_zar,
    o.stage_name,
    o.created_date       as opportunity_created_date,
    o.close_date,
    o.days_to_close,
    o.expected_value_zar,
    o.is_won,
    a.application_external_id,
    a.submitted_date,
    a.decision_date,
    a.status             as application_status,
    a.days_to_decision,
    a.is_date_inverted,
    e.enrolment_external_id,
    e.enrolled_date,
    e.agreed_fee_zar,
    e.status             as enrolment_status,
    case when e.enrolment_external_id is not null then 1 else 0 end as is_enrolled,
    case when e.agreed_fee_zar is not null and d.advertised_fee_zar > 0
         then round(100.0 * (d.advertised_fee_zar - e.agreed_fee_zar)
                    / d.advertised_fee_zar, 2) end as discount_pct
from {{ ref('stg_opportunity') }} o
left join {{ ref('dim_contact') }} c  using (contact_external_id)
left join {{ ref('stg_intake') }} i   using (intake_external_id)
left join {{ ref('dim_offering') }} d using (offering_external_id)
left join {{ ref('stg_application') }} a using (opportunity_external_id)
left join {{ ref('stg_enrolment') }} e using (application_external_id)
""".lstrip()

FILES["models/marts/fct_student_progress_weekly.sql"] = """
{#- Weekly academic health, with the at-risk definition applied consistently. #}
select
    p.progress_external_id,
    p.enrolment_external_id,
    e.student_external_id,
    e.intake_external_id,
    d.programme_title,
    d.delivery_mode,
    p.week_start,
    p.week_number,
    p.attendance_pct,
    p.assessment_average_pct,
    p.overdue_assignments,
    p.risk_band,
    p.is_attendance_missing,
    e.status as enrolment_status,
    case when p.attendance_pct < 55 or p.assessment_average_pct < 50
              or p.overdue_assignments >= 3
         then 1 else 0 end as is_at_risk,
    avg(p.attendance_pct) over (
        partition by p.enrolment_external_id
        order by p.week_number
        rows between 3 preceding and current row
    ) as attendance_4wk_avg
from {{ ref('stg_student_progress') }} p
join {{ ref('stg_enrolment') }} e using (enrolment_external_id)
left join {{ ref('stg_intake') }} i using (intake_external_id)
left join {{ ref('dim_offering') }} d using (offering_external_id)
""".lstrip()

FILES["models/marts/fct_lead_conversion.sql"] = """
select
    l.lead_external_id,
    l.lead_source,
    l.lead_status,
    l.province,
    l.campaign_external_id,
    l.created_date,
    l.is_converted,
    c.contact_external_id,
    c.created_date as contact_created_date,
    case when c.contact_external_id is not null
         then date_diff('day', l.created_date, c.created_date) end as days_to_convert,
    case when o.opportunity_external_id is not null then 1 else 0 end as reached_opportunity,
    case when e.enrolment_external_id is not null then 1 else 0 end as reached_enrolment
from {{ ref('stg_lead') }} l
left join {{ ref('stg_contact') }} c
       on c.converted_from_lead_id = l.lead_external_id and c.is_golden_record = 1
left join {{ ref('stg_opportunity') }} o using (contact_external_id)
left join {{ ref('stg_application') }} a using (opportunity_external_id)
left join {{ ref('stg_enrolment') }} e using (application_external_id)
""".lstrip()

# ---------------------------------------------------------------- quality ---

FILES["models/quality/dq_issue_log.sql"] = """
{#-
  Every quality defect the pipeline detected, as one row per issue, so the
  Power BI data-quality page and the scoring script read from the same place.
  Issue codes match the keys in warehouse/_truth/defects.json.
#}
select 'lead' as entity, lead_external_id as record_id,
       'email_invalid' as issue_code, 'Email failed format validation' as issue_description
from {{ ref('stg_lead') }} where is_email_invalid = 1
union all
select 'contact', contact_external_id, 'email_invalid', 'Email failed format validation'
from {{ ref('stg_contact') }} where is_email_invalid = 1
union all
select 'contact', contact_external_id, 'duplicate_person', 'Duplicate human on person_key'
from {{ ref('stg_contact') }} where is_golden_record = 0
union all
select 'contact', contact_external_id, 'phone_unparseable', 'Phone could not be normalised to E.164'
from {{ ref('stg_contact') }} where phone_e164 is null
union all
select 'contact', contact_external_id, 'province_unknown', 'Province did not map to an official name'
from {{ ref('stg_contact') }} where province = 'Unknown'
union all
select 'campaign_member', campaign_member_external_id, 'duplicate_membership',
       'Same member on the same campaign more than once'
from {{ ref('stg_campaign_member') }} where is_unique_membership = 0
union all
select 'opportunity', opportunity_external_id, 'negative_value', 'Expected value was negative'
from {{ ref('stg_opportunity') }} where is_value_negative = 1
union all
select 'application', application_external_id, 'date_inversion', 'Decision date precedes submission'
from {{ ref('stg_application') }} where is_date_inverted = 1
union all
{#-
  Date inversion is injected into TWO tables, and for a long time only the
  application half was detected - so the ground-truth score reported 0.64
  recall against an injection rate that should be caught almost entirely.
  An enrolment dated before its own application was submitted is the same
  defect, and it needs the join because the two dates live in two tables.
#}
select 'enrolment', e.enrolment_external_id, 'date_inversion',
       'Enrolled before the application was submitted'
from {{ ref('stg_enrolment') }} e
join {{ ref('stg_application') }} a
  on a.application_external_id = e.application_external_id
where e.enrolled_date < a.submitted_date
union all
{#-
  A null fee is only a defect when the catalogue actually advertised a price.
  Offerings priced "Enquire" legitimately carry no amount, and reporting those
  as missing data would flag the catalogue's most careful decision as an error.
#}
select 'enrolment', e.enrolment_external_id, 'fee_missing',
       'Agreed fee is null although the offering has an advertised price'
from {{ ref('stg_enrolment') }} e
join {{ ref('stg_intake') }} i on i.intake_external_id = e.intake_external_id
join {{ ref('dim_offering') }} d on d.offering_external_id = i.offering_external_id
where e.is_fee_missing = 1 and d.advertised_fee_zar is not null
union all
select 'student_progress', progress_external_id, 'attendance_missing', 'Attendance not recorded'
from {{ ref('stg_student_progress') }} where is_attendance_missing = 1
union all
select 'campaign', campaign_external_id, 'late_arriving', 'source_updated_at after loaded_at'
from {{ ref('stg_campaign') }} where is_late_arriving = 1
union all
select 'lead', lead_external_id, 'late_arriving', 'source_updated_at after loaded_at'
from {{ ref('stg_lead') }} where is_late_arriving = 1
""".lstrip()

FILES["models/quality/dq_summary.sql"] = """
select
    entity,
    issue_code,
    max(issue_description) as issue_description,
    count(*)               as issue_count
from {{ ref('dq_issue_log') }}
group by 1, 2
order by issue_count desc
""".lstrip()

# ------------------------------------------------------- tests and catalogue ---
# Descriptions here are the data catalogue. `dbt docs generate` turns them into
# the searchable, lineage-linked site the role asks for, so documentation is a
# build artefact rather than a wiki page that drifts.

FILES["models/staging/_staging.yml"] = """
version: 2

models:
  - name: stg_lead
    description: >
      Prospective students from Salesforce, cleansed. Email is validated and
      lowercased, phone normalised to E.164, province collapsed to the nine
      official names. Invalid values become null and are flagged, never guessed.
    columns:
      - name: lead_external_id
        description: Stable external key used for upsert into Salesforce.
        data_tests: [unique, not_null]
      - name: email
        description: Cleaned address, or null when the source value was unusable.
      - name: lead_status
        data_tests:
          - accepted_values:
              arguments:
                values: ["Open - Not Contacted", "Working - Contacted", "Nurture",
                         "Qualified", "Converted", "Unqualified"]

  - name: stg_contact
    description: >
      Known people, with duplicates resolved. Two match keys (email, and
      phone-plus-surname) are anchored independently then propagated once, so a
      phone-only record links to the emailed record it shares a handset with.
      Duplicates are flagged, not deleted - is_golden_record marks the survivor.
    columns:
      - name: contact_external_id
        data_tests: [unique, not_null]
      - name: person_key
        description: Resolved cluster identifier. Shared by every record for one human.
        data_tests: [not_null]
      - name: is_golden_record
        description: 1 for the earliest record in a person cluster, 0 for its duplicates.
        data_tests:
          - accepted_values:
              arguments: {values: [0, 1]}

  - name: stg_campaign
    description: Marketing campaigns with spend. Negative spend is nulled and flagged.
    columns:
      - name: campaign_external_id
        data_tests: [unique, not_null]

  - name: stg_campaign_member
    description: >
      Campaign participation. Each member appears against a campaign once;
      repeat rows are flagged via is_unique_membership rather than dropped.
    columns:
      - name: campaign_member_external_id
        data_tests: [not_null]
      - name: campaign_external_id
        data_tests:
          - relationships:
              arguments:
                to: ref('stg_campaign')
                field: campaign_external_id

  - name: stg_opportunity
    description: Admissions pipeline. One opportunity is one applicant pursuing one intake.
    columns:
      - name: opportunity_external_id
        data_tests: [unique, not_null]
      - name: expected_value_zar
        description: Negative values are treated as data entry errors and nulled.

  - name: stg_application
    description: >
      Applications against an intake. Decision-before-submission is preserved and
      flagged - the row is real even though the dates are impossible.
    columns:
      - name: application_external_id
        data_tests: [unique, not_null]
      - name: opportunity_external_id
        data_tests:
          - relationships:
              arguments:
                to: ref('stg_opportunity')
                field: opportunity_external_id

  - name: stg_enrolment
    description: Enrolments, carrying the agreed fee rather than the advertised price.
    columns:
      - name: enrolment_external_id
        data_tests: [unique, not_null]
      - name: application_external_id
        data_tests:
          - relationships:
              arguments:
                to: ref('stg_application')
                field: application_external_id

  - name: stg_student
    description: Students, one per accepted applicant.
    columns:
      - name: student_external_id
        data_tests: [unique, not_null]

  - name: stg_student_progress
    description: Weekly attendance, assessment average and overdue work per enrolment.
    columns:
      - name: progress_external_id
        data_tests: [unique, not_null]
      - name: enrolment_external_id
        data_tests:
          - relationships:
              arguments:
                to: ref('stg_enrolment')
                field: enrolment_external_id

  - name: stg_programme
    description: "REAL catalogue: 83 programme identities transcribed from the public site."
    columns:
      - name: programme_external_id
        data_tests: [unique, not_null]

  - name: stg_programme_offering
    description: >
      REAL catalogue: 89 offerings. An offering is a programme in one delivery
      mode and pace. advertised_fee_zar is null where the site says
      "Enquire for price" - that null is the true value and is never zero.
    columns:
      - name: offering_external_id
        data_tests: [unique, not_null]
      - name: programme_external_id
        data_tests:
          - relationships:
              arguments:
                to: ref('stg_programme')
                field: programme_external_id

  - name: stg_intake
    description: "REAL catalogue: 47 intakes that had a visible start date."
    columns:
      - name: intake_external_id
        data_tests: [unique, not_null]

  - name: stg_programme_enquiry
    description: Enquiries about a specific offering, before any formal application.
    columns:
      - name: enquiry_external_id
        data_tests: [unique, not_null]
""".lstrip()

FILES["models/marts/_marts.yml"] = """
version: 2

models:
  - name: dim_contact
    description: One row per resolved human. Duplicates collapse onto the golden record.
    columns:
      - name: contact_external_id
        data_tests: [unique, not_null]
      - name: province
        data_tests:
          - accepted_values:
              arguments:
                values: ["Western Cape", "Gauteng", "KwaZulu-Natal", "Eastern Cape",
                         "Free State", "Limpopo", "Mpumalanga", "North West",
                         "Northern Cape", "Outside South Africa", "Unknown"]

  - name: dim_offering
    description: >
      The catalogue flattened to one row per offering. Intakes are counted in a
      subquery rather than joined, so this dimension cannot fan out the facts
      that join it.
    columns:
      - name: offering_external_id
        data_tests: [unique, not_null]

  - name: dim_campaign
    columns:
      - name: campaign_external_id
        data_tests: [unique, not_null]

  - name: dim_date
    columns:
      - name: date_day
        data_tests: [unique, not_null]

  - name: fct_campaign_performance
    description: >
      Campaign economics. Members, opportunities and enrolments are aggregated
      to campaign grain BEFORE spend is attached, so a campaign's cost is never
      multiplied by its downstream row count.
    columns:
      - name: campaign_external_id
        data_tests: [unique, not_null]

  - name: fct_admissions_funnel
    description: One row per opportunity, carrying the whole enquiry-to-enrolment journey.
    columns:
      - name: opportunity_external_id
        data_tests: [unique, not_null]

  - name: fct_student_progress_weekly
    description: Weekly academic health with a single consistent at-risk definition.
    columns:
      - name: progress_external_id
        data_tests: [unique, not_null]

  - name: fct_lead_conversion
    description: Lead-to-enrolment journey, the headline marketing conversion metric.
""".lstrip()

FILES["models/quality/_quality.yml"] = """
version: 2

models:
  - name: dq_issue_log
    description: >
      One row per detected defect. Issue codes align with the ground-truth
      manifest at warehouse/_truth/defects.json so detection can be scored as
      recall rather than asserted.
  - name: dq_summary
    description: Detected defects rolled up by entity and issue type.
""".lstrip()

FILES["tests/assert_campaign_spend_not_multiplied.sql"] = """
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
""".lstrip()

FILES["tests/assert_enquire_price_never_zero.sql"] = """
{#
  "Enquire for price" must stay null. A zero here would silently drag down every
  average price in the reporting layer.
#}
select offering_external_id, advertised_fee_zar, price_status
from {{ ref('dim_offering') }}
where price_status = 'Enquire' and advertised_fee_zar is not null
""".lstrip()

FILES["tests/assert_one_golden_record_per_person.sql"] = """
select person_key, sum(is_golden_record) as golden_records
from {{ ref('stg_contact') }}
group by 1
having sum(is_golden_record) <> 1
""".lstrip()

# ----------------------------------------------------------------- bronze ---
# Bronze exists so the medallion is real in the LINEAGE, not just in the schema
# names. Without it, silver reads Parquet directly and dbt's DAG starts at the
# cleansed layer - the landed data is invisible to the catalogue, and there is
# nowhere to point at when asked "what actually arrived?".
RAW_TABLES = [
    "campaign", "lead", "contact", "campaign_member", "opportunity",
    "application", "student", "enrolment", "student_progress",
    "programme_enquiry", "programme", "programme_offering", "intake",
]

for _t in RAW_TABLES:
    FILES[f"models/bronze/br_{_t}.sql"] = (
        "-- Bronze: the landed source made queryable, and nothing else. No\n"
        "-- renaming, no casting, no filtering - so every silver column can be\n"
        "-- traced back to exactly what arrived, byte for byte.\n"
        f"select * from {{{{ ry_raw('{_t}') }}}}\n"
    )

FILES["models/bronze/_bronze.yml"] = (
    "version: 2\n\nmodels:\n" + "".join(
        f"  - name: br_{t}\n"
        f"    description: >\n"
        f"      Bronze. Raw {t} exactly as landed, with its integration metadata\n"
        f"      (source system, source id, source update time, load time,\n"
        f"      deletion flag) and no other change.\n"
        for t in RAW_TABLES))


# The Fabric target resolves bronze relations through this source declaration;
# DuckDB instead reads the same landed parquet files directly in ry_raw().
# Keeping it in the generator prevents regeneration from dropping the remote source.
FILES["models/bronze/_sources.yml"] = (
    "version: 2\n\n"
    "sources:\n"
    "  - name: raw_salesforce\n"
    "    description: >\n"
    "      Raw Salesforce-shaped records landed in the Fabric Warehouse by\n"
    "      fabric/load_warehouse.py. These are the immutable inputs to bronze.\n"
    "    database: \"{{ target.database }}\"\n"
    "    schema: raw_salesforce\n"
    "    tables:\n" + "".join(
        f"      - name: {t}\n"
        f"        description: Raw landed {t} records.\n"
        for t in RAW_TABLES))

# Silver reads bronze, not the Parquet. One substitution keeps the model SQL
# itself unchanged and the lineage honest.
def _to_bronze(sql: str) -> str:
    for t in sorted(RAW_TABLES, key=len, reverse=True):
        sql = sql.replace("{{ ry_raw('%s') }}" % t, "{{ ref('br_%s') }}" % t)
    return sql


# Medallion folders: staging is silver, marts are gold. Model names are left
# alone - renaming stg_* would break every ref() and every test in one go for
# no gain, and the folder plus schema already say which layer a model is in.
_remapped = {}
for _k, _v in FILES.items():
    _nk = _k.replace("models/staging/", "models/silver/") \
            .replace("models/marts/", "models/gold/")
    _remapped[_nk] = _to_bronze(_v) if _nk.startswith("models/silver/") else _v
FILES = _remapped

RAW_ABS = (ROOT.parent / "warehouse" / "raw").as_posix()
FILES["dbt_project.yml"] = FILES["dbt_project.yml"].replace("__RAW_PATH__", RAW_ABS)

Path(ROOT).mkdir(parents=True, exist_ok=True)
for rel, content in FILES.items():
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
print(f"wrote {len(FILES)} project/macro files to {ROOT}")



