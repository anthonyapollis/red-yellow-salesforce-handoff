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
