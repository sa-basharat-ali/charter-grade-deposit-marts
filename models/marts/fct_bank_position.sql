-- grain: insured owner x ownership category x bank x quarter end, split by where it came from.
with owners as (
    select distinct holder_key, insured_owner_key, ownership_category, relationship_key
    from {{ ref('stg_accounts') }}
),
swept as (
    select holder_key, as_of, sum(amount) as swept from {{ ref('int_sweep_slots') }}
    group by holder_key, as_of
),
at_partner as (
    select h.holder_key, h.as_of, h.partner_bank as bank_code,
           h.balance - coalesce(s.swept, 0)                               as amount, 'partner' as placed
    from {{ ref('int_holder_balance') }} h
    left join swept s on s.holder_key = h.holder_key and s.as_of = h.as_of
),
at_program as (
    select holder_key, as_of, bank_code, amount, 'sweep' as placed from {{ ref('int_sweep_slots') }}
)
select o.insured_owner_key, o.ownership_category, o.relationship_key, x.holder_key,
       x.as_of, x.bank_code, x.placed, x.amount
from (select * from at_partner union all select * from at_program) x
join owners o on o.holder_key = x.holder_key
