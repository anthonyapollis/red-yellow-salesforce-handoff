select
    entity,
    issue_code,
    max(issue_description) as issue_description,
    count(*)               as issue_count
from {{ ref('dq_issue_log') }}
group by entity, issue_code
