-- type 1: the partner bank an account is at today. Fine for routing, wrong for history.
select account_id, bank_code
from (
    select account_id, bank_code,
           row_number() over (partition by account_id order by effective_at desc) as rn
    from {{ source('raw', 'bank_events') }}
)
where rn = 1
