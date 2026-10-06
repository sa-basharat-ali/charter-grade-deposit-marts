-- every quarter-end balance lands on exactly one partner bank row
select (select count(*) from {{ source('raw', 'balances') }}) - (select count(*) from {{ ref('fct_balance_quarter_end') }}) as diff
where diff != 0
