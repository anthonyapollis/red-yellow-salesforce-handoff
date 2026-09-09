with src as (select * from {{ ref('br_intake') }})
select
    "RY_External_ID__c" as intake_external_id,
    "Offering_Key"      as offering_external_id,
    cast("Start_Date__c" as date) as start_date
from src
