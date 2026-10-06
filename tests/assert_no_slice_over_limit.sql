select * from {{ ref('int_sweep_slots') }} where amount > 250000 or amount <= 0
