{#- Real catalogue data. Cleansed for whitespace only - never invented. #}
with src as (select * from {{ ry_raw('programme') }})
select
    "RY_External_ID__c"      as programme_external_id,
    trim("Title__c")         as programme_title,
    "Category__c"            as category,
    nullif(trim(coalesce(cast("Credential_Text__c" as varchar), '')), '') as credential_text,
    nullif(trim(coalesce(cast("Listed_Body__c" as varchar), '')), '')     as listed_body
from src
