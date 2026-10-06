-- sweeping moves money between banks; it never creates or loses any
select a.as_of, a.total, b.placed_total
from (select as_of, sum(ledger_balance) as total from {{ ref('fct_balance_quarter_end') }} group by as_of) a
join (select as_of, sum(amount) as placed_total from {{ ref('fct_bank_position') }} group by as_of) b using (as_of)
where abs(a.total - b.placed_total) > 0.01
