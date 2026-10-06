-- grain: account holder x partner bank x quarter end. This is what the sweep engine sees.
select
    holder_key,
    min(depositor_id)                                                     as depositor_id,
    partner_bank,
    as_of,
    sum(ledger_balance)                                                   as balance
from {{ ref('fct_balance_quarter_end') }}
group by holder_key, partner_bank, as_of
