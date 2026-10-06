"""python3 run.py  -- stdlib only (sqlite3). Builds the world, runs the models in dependency
order the way dbt would, runs the tests, then prints the findings."""
import pathlib
import re
import sqlite3
import time

import world as W

T0 = time.time()
ROOT = pathlib.Path(__file__).parent
REF = re.compile(r"\{\{\s*ref\('(\w+)'\)\s*\}\}")
SRC = re.compile(r"\{\{\s*source\('raw',\s*'(\w+)'\)\s*\}\}")


def compile_sql(sql):
    return SRC.sub(r"raw_\1", REF.sub(r"\1", sql))


def money(x):
    if abs(x) >= 1e9:
        return f"${x / 1e9:,.2f}B"
    return f"${x / 1e6:,.1f}M" if abs(x) >= 1e6 else f"${x / 1e3:,.0f}K"


# 1. load the world ---------------------------------------------------------------------------
db = sqlite3.connect(":memory:")
for name, rows in W.build().items():
    cols = list(rows[0])
    db.execute(f"create table {name} ({', '.join(cols)})")
    db.executemany(f"insert into {name} values ({', '.join('?' * len(cols))})", [tuple(r[c] for c in cols) for r in rows])

# 2. run models in dependency order -----------------------------------------------------------
models = {p.stem: p.read_text() for p in sorted(ROOT.glob("models/**/*.sql"))}
done, order = set(), []
while len(done) < len(models):
    for m, sql in models.items():
        if m not in done and set(REF.findall(sql)) <= done:
            db.execute(f"create table {m} as {compile_sql(sql)}")
            done.add(m)
            order.append(m)
for t in sorted(ROOT.glob("tests/*.sql")):
    bad = db.execute(compile_sql(t.read_text())).fetchall()
    assert not bad, f"test failed: {t.stem} {bad[:3]}"
n_tests = len(list(ROOT.glob("tests/*.sql")))
q = lambda sql, *a: db.execute(sql, a).fetchall()

QE = "2026-06-30"
print("=" * 82)
print("Charter-grade deposit marts: one question, four grains (synthetic)")
print("=" * 82)
print(f"models built in order: {' -> '.join(order)}")
print(f"{n_tests} tests passed")
[(n_dep,)], [(n_acc,)] = q("select count(*) from raw_depositors"), q("select count(*) from raw_accounts")
print(f"{n_dep:,} business depositors, {n_acc:,} accounts, {len(W.QUARTERS)} quarter ends")

# 3. finding 1: the uninsured ladder ----------------------------------------------------------
print(f"\n1. 'HOW MUCH OF OUR DEPOSITS IS UNINSURED?'  as of {QE}")
dep, acc, hold, swept, owner = q("select deposits, account_no_sweep, holder_no_sweep, holder_swept, owner_swept "
                                 "from mart_uninsured_estimate where as_of = ?", QE)[0]
# ground truth adds what the platform can't see: deposits customers hold directly at a program bank
truth_extra = q("""
    with pos as (select insured_owner_key, ownership_category, bank_code, sum(amount) amt
                 from fct_bank_position where as_of = ? group by 1, 2, 3),
         direct as (select 'E' || depositor_id k, bank_code, balance from truth_direct_holdings where as_of = ?)
    select sum(max(0, p.amt + d.balance - 250000) - max(0, p.amt - 250000))
    from pos p join direct d on d.k = p.insured_owner_key and d.bank_code = p.bank_code""", QE, QE)[0][0] or 0
truth = owner + truth_extra
print(f"   deposits {money(dep)}")
for label, v in [("per account, no sweep", acc), ("per account holder, no sweep", hold),
                 ("per account holder, after the sweep (what the sweep engine believes)", swept),
                 ("per insured owner, after the sweep (12 CFR 330 grain)", owner),
                 ("true, adding deposits held directly at program banks", truth)]:
    print(f"   {money(v):>9}  {v / dep * 100:5.1f}%   {label}")
print(f"   the sweep-engine number understates the true figure by {money(truth - swept)} ({(truth / swept - 1) * 100:.0f}%)")

# 4. finding 2: the sole-prop grain ------------------------------------------------------------
print("\n2. THE SWEEP ALLOCATES BY ACCOUNT HOLDER; THE FDIC INSURES BY OWNER")
rows = q("""
    with h as (select holder_key, insured_owner_key, ownership_category, bank_code, sum(amount) amt
               from fct_bank_position where as_of = ? group by 1, 2, 3, 4),
         o as (select insured_owner_key, ownership_category, bank_code, count(*) holders, sum(amt) amt,
                      sum(max(0, amt - 250000)) holder_unins
               from h group by 1, 2, 3)
    select count(distinct insured_owner_key), sum(max(0, amt - 250000) - holder_unins)
    from o where holders > 1 and max(0, amt - 250000) > holder_unins""", QE)[0]
print(f"   {rows[0]:,} founders whose sole proprietorship and personal account each got their own $250K at the same bank")
print(f"   coverage shown that doesn't exist: {money(rows[1])}")
sp = q("select count(*) from raw_depositors where entity_type = 'sole_prop'")[0][0]
print(f"   ({sp:,} sole proprietorships in the book; each is insured as its owner, with the owner's personal accounts)")

# 5. finding 3: direct holdings at program banks ------------------------------------------------
print("\n3. A DEPOSIT THE PLATFORM NEVER SEES")
n_direct = q("select count(distinct depositor_id) from truth_direct_holdings where as_of = ?", QE)[0][0]
n_told = q("select count(*) from raw_sweep_optouts")[0][0]
hit = q("""
    with pos as (select insured_owner_key, bank_code, sum(amount) amt from fct_bank_position
                 where as_of = ? and ownership_category = 'business' group by 1, 2)
    select count(*) from pos p join truth_direct_holdings d
      on 'E' || d.depositor_id = p.insured_owner_key and d.bank_code = p.bank_code and d.as_of = ?""", QE, QE)[0][0]
print(f"   {n_direct} customers also bank directly at one of the program banks; {n_told} told us and that bank is skipped")
print(f"   {hit} of the rest had money swept into the same bank anyway: {money(truth_extra)} shown as insured that isn't")

# 6. finding 4: type 1 vs type 2 history ------------------------------------------------------
print("\n4. A TYPE 1 DIMENSION REWRITES THE MIGRATION")
print(f"   deposits by partner bank, each quarter end      {'type 2 (as it was)':>26}   {'type 1 (bank today)':>26}")
for qe in W.QUARTERS[:4]:
    t2 = dict(q("select partner_bank, sum(ledger_balance) from fct_balance_quarter_end where as_of = ? group by 1", qe))
    t1 = dict(q("""select c.bank_code, sum(b.ledger_balance) from raw_balances b join dim_account_current c using (account_id)
                   where b.as_of = ? group by 1""", qe))
    fmt = lambda m: "  ".join(f"{k} {money(m.get(k, 0)):>8}" for k in ("LEGACY", "PA", "PB"))
    print(f"   {qe}  {fmt(t2)}   |   {fmt(t1)}")
moved = q("""select sum(b.ledger_balance) from raw_balances b join dim_account_current c using (account_id)
             join fct_balance_quarter_end f on f.account_id = b.account_id and f.as_of = b.as_of
             where b.as_of = ? and c.bank_code != f.partner_bank""", W.QUARTERS[0])[0][0]
print(f"   at {W.QUARTERS[0]}, the type 1 view puts {money(moved)} of LEGACY deposits on the new partners")

# 7. the other grain: concentration ----------------------------------------------------------
print("\n5. THE GRAIN THAT'S RIGHT FOR INSURANCE IS WRONG FOR CONCENTRATION")
for key, label in [("insured_owner_key", "insured owner"), ("relationship_key", "founder"),
                   ("investor_key", "lead investor's portfolio")]:
    vals = [v for (v,) in q(f"select sum(ledger_balance) s from fct_balance_quarter_end where as_of = ? group by {key} order by s desc", QE)]
    print(f"   top 10 by {label:<26} {money(sum(vals[:10])):>9}  ({sum(vals[:10]) / dep * 100:4.1f}% of deposits)   "
          f"largest single key {sum(vals[:1]) / dep * 100:4.1f}%")
n_backed = q("select count(*) from raw_depositors where lead_investor_id is not null")[0][0]
print(f"   ({n_backed:,} venture-backed depositors; their cash can leave together when one investor says so)")

print(f"\nran in {time.time() - T0:.1f}s")
