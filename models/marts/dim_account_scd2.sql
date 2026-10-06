-- type 2: one row per account per partner bank it has lived at
select
    account_id,
    bank_code,
    effective_at                                                          as valid_from,
    coalesce(lead(effective_at) over (partition by account_id order by effective_at),
             '9999-12-31')                                                as valid_to
from {{ source('raw', 'bank_events') }}
