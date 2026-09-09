with src as (select * from {{ ref('br_programme_offering') }})
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
