-- the same question, "how much of our deposits are uninsured?", answered at four grains
with by_account as (
    select as_of, sum(max(0, ledger_balance - 250000)) as v
    from {{ ref('fct_balance_quarter_end') }} group by as_of
),
by_holder_no_sweep as (
    select as_of, sum(max(0, balance - 250000)) as v
    from {{ ref('int_holder_balance') }} group by as_of
),
by_holder_swept as (
    select as_of, sum(max(0, amt - 250000)) as v
    from (select holder_key, as_of, bank_code, sum(amount) as amt
          from {{ ref('fct_bank_position') }} group by 1, 2, 3)
    group by as_of
),
by_insured_owner as (
    select as_of, sum(max(0, amt - 250000)) as v
    from (select insured_owner_key, ownership_category, as_of, bank_code, sum(amount) as amt
          from {{ ref('fct_bank_position') }} group by 1, 2, 3, 4)
    group by as_of
),
total as (
    select as_of, sum(ledger_balance) as deposits from {{ ref('fct_balance_quarter_end') }} group by as_of
)
select t.as_of, t.deposits,
       a.v as account_no_sweep, h.v as holder_no_sweep, s.v as holder_swept, o.v as owner_swept
from total t
join by_account a using (as_of)
join by_holder_no_sweep h using (as_of)
join by_holder_swept s using (as_of)
join by_insured_owner o using (as_of)
