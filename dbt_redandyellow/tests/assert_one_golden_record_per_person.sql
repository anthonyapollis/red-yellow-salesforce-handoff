select person_key, sum(is_golden_record) as golden_records
from {{ ref('stg_contact') }}
group by person_key
having sum(is_golden_record) <> 1
