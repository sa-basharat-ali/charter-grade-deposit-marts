-- the sweep: keep $250K at the partner, place the rest in $250K slices across program banks in
-- priority order, skipping any bank the customer has opted out of.
with eligible as (
    select h.holder_key, h.as_of, h.balance, p.bank_code,
           row_number() over (partition by h.holder_key, h.partner_bank, h.as_of
                              order by p.priority)                        as slot
    from {{ ref('int_holder_balance') }} h
    cross join {{ source('raw', 'program_banks') }} p
    where h.balance > 250000
      and not exists (select 1 from {{ source('raw', 'sweep_optouts') }} o
                      where o.depositor_id = h.depositor_id and o.bank_code = p.bank_code)
)
select holder_key, as_of, bank_code, slot,
       min(250000.0, max(0.0, balance - 250000.0 * slot))                 as amount
from eligible
where balance - 250000.0 * slot > 0
