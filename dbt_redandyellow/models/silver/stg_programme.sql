{#- Real catalogue data. Cleansed for whitespace only - never invented. #}
with src as (select * from {{ ref('br_programme') }})
select
    "RY_External_ID__c"      as programme_external_id,
    trim("Title__c")         as programme_title,
    "Category__c"            as category,
    nullif(trim(coalesce({{ ry_text('"Credential_Text__c"') }}, '')), '') as credential_text,
    nullif(trim(coalesce({{ ry_text('"Listed_Body__c"') }}, '')), '')     as listed_body
from src
