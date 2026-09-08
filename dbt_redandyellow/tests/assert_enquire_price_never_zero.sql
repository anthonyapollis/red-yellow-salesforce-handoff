{#
  "Enquire for price" must stay null. A zero here would silently drag down every
  average price in the reporting layer.
#}
select offering_external_id, advertised_fee_zar, price_status
from {{ ref('dim_offering') }}
where price_status = 'Enquire' and advertised_fee_zar is not null
