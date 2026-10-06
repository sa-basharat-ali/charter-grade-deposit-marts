# Charter-grade deposit marts

```
python3 run.py      # stdlib only (sqlite3), about 3 seconds
```

A synthetic startup-banking fintech getting ready to become a bank. Deposits sit at partner banks;
balances above $250K are swept in $250K slices across 19 program banks so a customer sees up to
$5M of FDIC coverage. Partway through the history, every account on a legacy partner bank migrates
to one of two new ones. 12,000 business depositors, 25,373 accounts, seven quarter ends. Fixed
seed, no real company, bank or customer.

The models are written the way a dbt project is: `models/staging`, `models/marts`, `{{ ref() }}`
and `{{ source() }}`, singular tests in `tests/`, and a `schema.yml` that states each model's grain.
`run.py` compiles the refs, builds the models in dependency order in SQLite, runs the four tests and
prints the findings.

Once a bank passes $1B in assets, its Call Report carries an estimate of uninsured deposits
(Schedule RC-O, Memorandum item 2). Every finding below is a way that number, or the marts behind
it, comes out wrong.

## Five findings

### 1. "How much of our deposits is uninsured?" has five answers

As of 2026-06-30, on $6.78B of deposits:

| grain | uninsured | share |
|---|---|---|
| per account, ignoring the sweep | $4.38B | 64.6% |
| per account holder, ignoring the sweep | $4.94B | 72.9% |
| per account holder, after the sweep (what the sweep engine believes) | $1.12B | 16.6% |
| per insured owner, after the sweep (the 12 CFR 330 grain) | $1.13B | 16.6% |
| true, adding deposits held directly at program banks | $1.16B | 17.1% |

An AI analyst asked this question against the balance table writes the first query and answers 65%.
The right one is the fourth, and even that misses $33.9M the platform can't see.

### 2. The sweep allocates by account holder; the FDIC insures by owner

A sole proprietorship is insured as its owner, together with the owner's personal accounts at the
same bank. The sweep engine treats the business and the person as two holders, so each keeps its
own $250K at the partner and fills the same program banks first. 43 founders end up over the limit
at a bank the sweep says is covered: $3.3M of coverage shown that doesn't exist.

### 3. A deposit the platform never sees

136 customers also bank directly at one of the program banks. 51 said so, and that bank is skipped.
For 58 of the rest, the sweep put money into the same bank anyway: $30.6M shown as insured that
isn't. No model can fix this from the data it has; the fix is asking customers, and the mart should
say the gap exists (`known_gap` in `schema.yml`).

### 4. A type 1 dimension rewrites the migration

| quarter end | type 2: LEGACY / PA / PB | type 1 (bank today): LEGACY / PA / PB |
|---|---|---|
| 2024-12-31 | $5.69B / $0 / $0 | $32.2M / $2.89B / $2.77B |
| 2025-03-31 | $2.99B / $1.56B / $1.47B | $10.9M / $3.09B / $2.93B |
| 2025-06-30 | $0 / $3.23B / $3.08B | $0 / $3.23B / $3.08B |

Join history to the current-state dimension and $5.66B of pre-migration deposits move onto banks
that didn't hold them yet. The only deposits left on LEGACY are accounts that closed before they
moved. A charter adds a third bank to this history, so the dimension has to be type 2 now.

### 5. The grain that's right for insurance is wrong for concentration

| grain | top 10 hold | largest single key |
|---|---|---|
| insured owner | 6.5% | 1.2% |
| founder | 6.5% | 1.2% |
| lead investor's portfolio | 39.0% | 14.4% |

The size of the investor number comes from my assumption about how concentrated lead investors are
(a Zipf curve over 400 investors), so read it as a shape, not a forecast. The point holds at any
setting: no customer-level grain can show that one investor's portfolio may move its cash on the
same day.

## The part I got wrong

I first built concentration on the founder, on the theory that one person behind several entities
is "one customer." It moved the top-10 share from 6.5% to 6.5%. Founders rarely run more than one
cash-heavy company at once. The grain that moves together is the investor, which is what a 2023
bank run looked like, and it only showed up once I modeled it.

## Files

| | |
|---|---|
| `world.py` | depositors, founders, investors, accounts, the migration, balances, opt-outs, hidden direct deposits |
| `models/staging/stg_accounts.sql` | one account, four keys: holder, insured owner, founder, investor |
| `models/marts/dim_account_scd2.sql` / `dim_account_current.sql` | type 2 and type 1 partner-bank history |
| `models/marts/fct_balance_quarter_end.sql` | account x quarter end, bank as of that date |
| `models/marts/int_sweep_slots.sql` | the sweep, in SQL, with opt-outs |
| `models/marts/fct_bank_position.sql` | owner x category x bank x quarter end |
| `models/marts/mart_uninsured_estimate.sql` | the same question at four grains |
| `models/schema.yml` | the grain of every model, and the one metric definition to use |
| `tests/` | one bank per balance, the sweep conserves money, no slice over $250K, unique accounts |
| `run.py` | compiles refs, builds in order, runs tests, prints findings |

Syed Ahmed Basharat Ali · sabasharat.ali@gmail.com · basharat.net
