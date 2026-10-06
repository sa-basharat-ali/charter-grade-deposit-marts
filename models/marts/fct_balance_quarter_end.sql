-- grain: account x quarter end. The partner bank is the one the account was at ON that date.
select
    b.account_id,
    b.as_of,
    b.ledger_balance,
    s.bank_code                                                           as partner_bank,
    a.holder_key,
    a.insured_owner_key,
    a.ownership_category,
    a.relationship_key,
    a.investor_key,
    a.depositor_id
from {{ source('raw', 'balances') }} b
join {{ ref('stg_accounts') }} a on a.account_id = b.account_id
join {{ ref('dim_account_scd2') }} s
  on s.account_id = b.account_id and b.as_of >= s.valid_from and b.as_of < s.valid_to
