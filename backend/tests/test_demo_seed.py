"""Tests for the demo-data seeder.

The seeder only runs on boot against an empty database, which is exactly the
path nobody exercises locally — so the failure mode is a live demo that looks
broken. These pin the properties the dashboard depends on.
"""

from datetime import date

import pytest

from auth import SessionLocal, seed_default_user
from db import Base, engine
from models import Budget, Transaction, User
from services.demo_seed import MONTHS_OF_HISTORY, seed_demo_transactions


@pytest.fixture
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        seed_default_user(session)
        yield session
    finally:
        session.close()


def test_seeds_transactions_and_budgets(db):
    inserted = seed_demo_transactions(db)
    assert inserted > 0
    assert db.query(Transaction).count() == inserted
    assert db.query(Budget).count() > 0


def test_is_idempotent(db):
    first = seed_demo_transactions(db)
    second = seed_demo_transactions(db)
    assert second == 0
    assert db.query(Transaction).count() == first


def test_no_op_without_a_user(db):
    db.query(User).delete()
    db.commit()
    assert seed_demo_transactions(db) == 0


def test_is_deterministic(db):
    seed_demo_transactions(db, today=date(2026, 8, 19))
    first = sorted((t.date, t.amount, t.merchant) for t in db.query(Transaction).all())

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_default_user(db)
    seed_demo_transactions(db, today=date(2026, 8, 19))
    second = sorted((t.date, t.amount, t.merchant) for t in db.query(Transaction).all())

    assert first == second


def test_covers_current_month_and_history(db):
    today = date(2026, 8, 19)
    seed_demo_transactions(db, today=today)
    months = {t.date.isoformat()[:7] for t in db.query(Transaction).all()}
    assert "2026-08" in months, "current month must have data or the dashboard opens empty"
    assert len(months) == MONTHS_OF_HISTORY


def test_never_posts_future_dates(db):
    today = date(2026, 8, 19)
    seed_demo_transactions(db, today=today)
    assert max(t.date for t in db.query(Transaction).all()) <= today


def test_has_income_and_expenses(db):
    seed_demo_transactions(db)
    amounts = [t.amount for t in db.query(Transaction).all()]
    assert any(a > 0 for a in amounts), "needs income or the net figure is meaningless"
    assert any(a < 0 for a in amounts)


def test_categories_are_resolved(db):
    seed_demo_transactions(db)
    cats = {t.category for t in db.query(Transaction).all()}
    assert "Uncategorized" not in cats
    assert {"Dining", "Groceries", "Transport"} <= cats


def test_dedupe_keys_are_unique(db):
    seed_demo_transactions(db)
    keys = [t.dedupe_key for t in db.query(Transaction).all()]
    assert len(keys) == len(set(keys))
