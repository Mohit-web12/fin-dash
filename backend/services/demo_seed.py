"""Seed the demo account with a realistic transaction history.

Render's free plan has an ephemeral filesystem, so the SQLite file is wiped on
every deploy and on periodic restarts. Without this, anyone opening the live
demo logs in to a dashboard of empty gauges. This refills it on boot.

Two properties matter here:

- Deterministic. A fixed RNG seed means the demo looks the same on every
  restart, so a screenshot in the README keeps matching the live site.
- Anchored to today. Dates are generated relative to the current month rather
  than hardcoded, because /summary defaults to the most recent month holding
  data. A fixed range would leave the dashboard opening on a stale month that
  drifts further out of date the longer the deploy sits.
"""

import random
from datetime import date, timedelta

from sqlalchemy.orm import Session

from models import Budget, Transaction, User

# Merchants chosen to exercise the rules in services.categorize, so the seeded
# history also demonstrates auto-categorization rather than only stored labels.
# (merchant, min, max, times per month)
RECURRING = [
    ("Employer Payroll", 4200.00, 4200.00, 1),   # income
    ("Stuyvesant Property Mgmt", -1850.00, -1850.00, 1),
    ("ConEd", -68.00, -142.00, 1),
    ("Verizon", -85.00, -85.00, 1),
    ("Netflix", -15.49, -15.49, 1),
    ("Spotify", -11.99, -11.99, 1),
]

VARIABLE = [
    ("Starbucks", -4.75, -9.40, 6),
    ("Whole Foods", -42.00, -138.00, 3),
    ("Trader Joe's", -28.00, -74.00, 2),
    ("Chipotle", -12.00, -19.50, 3),
    ("DoorDash", -22.00, -48.00, 2),
    ("Uber", -8.50, -34.00, 4),
    ("Shell", -38.00, -62.00, 2),
    ("Amazon", -14.00, -96.00, 4),
    ("Target", -22.00, -110.00, 2),
    ("Apple", -2.99, -9.99, 1),
]

BUDGETS = {
    # Rent is budgeted too, otherwise the headline spend gauge measures total
    # spend against a limit that excludes the largest line and sits redlined.
    "Housing": 1900.0,
    "Dining": 400.0,
    "Groceries": 600.0,
    "Transport": 250.0,
    "Shopping": 350.0,
    "Utilities": 300.0,
    "Subscriptions": 60.0,
}

MONTHS_OF_HISTORY = 6


def _month_start(today: date, months_back: int) -> date:
    y, m = today.year, today.month - months_back
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def _days_in_month(d: date) -> int:
    nxt = date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)
    return (nxt - d).days


def seed_demo_transactions(db: Session, today: date | None = None) -> int:
    """Populate the seeded user's history. No-op if they already have data.

    Returns the number of transactions inserted.
    """
    from app import dedupe_key  # local import: app imports this module at startup

    user = db.query(User).order_by(User.id).first()
    if user is None:
        return 0
    if db.query(Transaction).filter(Transaction.user_id == user.id).count() > 0:
        return 0

    today = today or date.today()
    rng = random.Random(20260819)
    rows: list[Transaction] = []
    seen: set[str] = set()

    def add(when: date, amount: float, merchant: str) -> None:
        # Never post a future-dated transaction: the current month is partial,
        # so the dashboard should read like a month in progress.
        if when > today:
            return
        amount = round(amount, 2)
        key = dedupe_key(user.id, when, amount, merchant)
        if key in seen:
            return
        seen.add(key)
        category, subcategory = _categorize(merchant)
        rows.append(
            Transaction(
                user_id=user.id,
                account_id=None,
                date=when,
                amount=amount,
                merchant=merchant,
                raw_description=f"{merchant.upper()} PURCHASE",
                category=category,
                subcategory=subcategory,
                is_recurring=merchant in {m for m, _, _, _ in RECURRING},
                dedupe_key=key,
            )
        )

    for months_back in range(MONTHS_OF_HISTORY - 1, -1, -1):
        start = _month_start(today, months_back)
        span = _days_in_month(start)

        for merchant, lo, hi, per_month in RECURRING:
            for _ in range(per_month):
                day = 1 if lo > 0 else min(rng.randint(1, 5), span)
                add(start + timedelta(days=day - 1), rng.uniform(lo, hi), merchant)

        for merchant, lo, hi, per_month in VARIABLE:
            for _ in range(per_month):
                add(start + timedelta(days=rng.randint(0, span - 1)), rng.uniform(lo, hi), merchant)

    db.add_all(rows)

    if db.query(Budget).filter(Budget.user_id == user.id).count() == 0:
        db.add_all(
            Budget(user_id=user.id, category=c, monthly_limit=v) for c, v in BUDGETS.items()
        )

    db.commit()
    return len(rows)


def _categorize(merchant: str) -> tuple[str, str]:
    """Fall back to explicit labels for the few merchants the rules miss."""
    from services.categorize import categorize

    category, subcategory = categorize(merchant)
    if category != "Uncategorized":
        return category, subcategory
    if "payroll" in merchant.lower():
        return "Income", "Salary"
    if "property" in merchant.lower():
        return "Housing", "Rent"
    return category, subcategory
