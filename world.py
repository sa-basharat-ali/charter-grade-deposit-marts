"""A synthetic startup-banking fintech on its way to its own charter.

Business and personal deposit accounts sit at partner banks. Balances above $250K per account
holder are swept, in $250K slices, across a network of 19 program banks, so a customer can see up
to $5M of FDIC coverage. Partway through the history, every account on a legacy partner bank
migrates to one of two new partners.

What the platform can see goes into raw_* tables. What it can't (deposits customers hold directly
at a program bank) goes into truth_* tables, which only the scoring in run.py reads.

Fixed seed. No real company, bank, customer or balance.
"""
import math
import random
from datetime import date, timedelta

SEED = 2017  # the year a bank account for startups started to look like software
QUARTERS = ["2024-12-31", "2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"]
PROGRAM_BANKS = [f"PB{i:02d}" for i in range(1, 20)]  # 19 x $250K + $250K at the partner = $5M
MIGRATION_START, MIGRATION_END = date(2025, 1, 13), date(2025, 6, 20)


def d(s):
    return date.fromisoformat(s)


def build(n_depositors=12000):
    rng = random.Random(SEED)
    persons, depositors, accounts, events, balances, treasury = [], [], [], [], [], []
    optouts, truth_direct = [], []

    # people: founders, some of whom own several entities, some of whom bank personally here too
    n_persons = int(n_depositors * 0.86)
    for p in range(1, n_persons + 1):
        persons.append({"person_id": p})

    aid = 0
    # venture investors: a few lead a lot of rounds (Zipf), and their portfolio banks together
    inv_ids = list(range(1, 401))
    inv_w = [1 / k ** 1.15 for k in inv_ids]

    def open_account(owner, kind, opened, partner_now, scale):
        nonlocal aid
        aid += 1
        closed = None
        if rng.random() < 0.07:  # some customers leave
            closed = opened + timedelta(days=rng.randint(60, 700))
            if closed > d(QUARTERS[-1]):
                closed = None
        acct = {"account_id": aid, "depositor_id": owner if kind != "personal" else None,
                "person_id": owner if kind == "personal" else None, "account_type": kind,
                "opened_at": opened.isoformat(), "closed_at": closed.isoformat() if closed else None}
        accounts.append(acct)
        # bank history: legacy accounts opened before the migration move to a new partner
        if opened < MIGRATION_END and partner_now == "LEGACY":
            events.append({"account_id": aid, "bank_code": "LEGACY", "effective_at": opened.isoformat()})
        else:
            events.append({"account_id": aid, "bank_code": partner_now, "effective_at": opened.isoformat()})
        acct["_scale"] = scale
        return acct

    for dep in range(1, n_depositors + 1):
        r = rng.random()
        etype = "sole_prop" if r < 0.11 else ("llc" if r < 0.55 else "corporation")
        # 30% of entities belong to a founder who owns another one here
        owner = rng.randint(1, n_persons) if rng.random() < 0.3 else ((dep - 1) % n_persons) + 1
        opened = date(2022, 1, 1) + timedelta(days=rng.randint(0, 1550))
        # balance scale: most startups are small, a few just raised
        mu = 11.2 if etype == "sole_prop" else 12.4
        scale = math.exp(rng.gauss(mu, 1.55))
        backed = etype != "sole_prop" and rng.random() < (0.85 if scale > 1e6 else 0.35)
        investor = rng.choices(inv_ids, inv_w)[0] if backed else None
        depositors.append({"depositor_id": dep, "ein": f"{rng.randint(10, 99)}-{rng.randint(1000000, 9999999)}",
                           "entity_type": etype, "owner_person_id": owner, "lead_investor_id": investor,
                           "created_at": opened.isoformat()})
        partner = "LEGACY" if opened < MIGRATION_START or rng.random() < 0.25 else rng.choice(["PA", "PB"])
        n_acc = 1 + (rng.random() < 0.55) + (rng.random() < 0.25) + (rng.random() < 0.1)
        for k in range(n_acc):
            kind = "checking" if k == 0 or rng.random() < 0.6 else "savings"
            o = opened + timedelta(days=rng.randint(0, 200) if k else 0)
            open_account(dep, kind, o, partner, scale / n_acc * rng.uniform(0.4, 1.6))
        # money market fund holdings are customer money but not deposits
        if etype != "sole_prop" and scale > 2e6 and rng.random() < 0.45:
            treasury.append({"depositor_id": dep, "_scale": scale * rng.uniform(0.3, 1.2)})
        # excluded program banks the customer told us about, and direct deposits they didn't mention
        if etype != "sole_prop" and scale > 1.5e6 and rng.random() < 0.09:
            bank = rng.choice(PROGRAM_BANKS[:8])
            told = rng.random() < 0.35
            if told:
                optouts.append({"depositor_id": dep, "bank_code": bank})
            truth_direct.append({"depositor_id": dep, "bank_code": bank, "_scale": math.exp(rng.gauss(12.9, 0.7))})

    # personal accounts: a quarter of founders also bank personally on the platform
    for p in persons:
        if rng.random() < 0.25:
            opened = date(2023, 3, 1) + timedelta(days=rng.randint(0, 1100))
            partner = "LEGACY" if opened < MIGRATION_START else rng.choice(["PA", "PB"])
            open_account(p["person_id"], "personal", opened, partner, math.exp(rng.gauss(11.0, 1.0)))

    # the migration: each legacy holder moves all accounts to one new partner on one date
    by_holder = {}
    for a in accounts:
        key = ("D", a["depositor_id"]) if a["depositor_id"] else ("P", a["person_id"])
        by_holder.setdefault(key, []).append(a)
    span = (MIGRATION_END - MIGRATION_START).days
    for key, accs in by_holder.items():
        legacy = [a for a in accs if events[a["account_id"] - 1]["bank_code"] == "LEGACY"]
        if not legacy:
            continue
        move = MIGRATION_START + timedelta(days=rng.randint(0, span))
        dest = rng.choice(["PA", "PB"])
        for a in legacy:
            if a["closed_at"] and d(a["closed_at"]) <= move:
                continue  # closed before it moved; stays LEGACY forever
            if d(a["opened_at"]) >= move:
                events[a["account_id"] - 1]["bank_code"] = dest  # opened after the move
                continue
            events.append({"account_id": a["account_id"], "bank_code": dest, "effective_at": move.isoformat()})

    # quarter-end balances: burn, the odd fundraise
    for a in accounts:
        level = a["_scale"]
        for q in QUARTERS:
            qd = d(q)
            if d(a["opened_at"]) > qd or (a["closed_at"] and d(a["closed_at"]) <= qd):
                level *= rng.uniform(0.85, 1.05)
                continue
            balances.append({"account_id": a["account_id"], "as_of": q, "ledger_balance": round(level, 2)})
            level *= rng.uniform(0.78, 1.02) * (rng.uniform(2.0, 4.0) if rng.random() < 0.04 else 1.0)
        del a["_scale"]

    tre = []
    for t in treasury:
        for q in QUARTERS:
            tre.append({"depositor_id": t["depositor_id"], "as_of": q, "mmf_balance": round(t["_scale"] * rng.uniform(0.8, 1.2), 2)})
    direct = []
    for t in truth_direct:
        for q in QUARTERS:
            direct.append({"depositor_id": t["depositor_id"], "bank_code": t["bank_code"], "as_of": q,
                           "balance": round(t["_scale"] * rng.uniform(0.8, 1.2), 2)})

    return {
        "raw_persons": persons,
        "raw_depositors": depositors,
        "raw_accounts": accounts,
        "raw_bank_events": events,
        "raw_balances": balances,
        "raw_treasury": tre,
        "raw_program_banks": [{"bank_code": b, "priority": i + 1} for i, b in enumerate(PROGRAM_BANKS)],
        "raw_sweep_optouts": optouts,
        "truth_direct_holdings": direct,
    }
