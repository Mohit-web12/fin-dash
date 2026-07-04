def create_tx(client, auth_headers, **overrides):
    payload = {
        "date": "2026-03-10",
        "amount": -20.0,
        "merchant": "Test Merchant",
        "category": "Dining",
        "subcategory": "Coffee",
    }
    payload.update(overrides)
    resp = client.post("/transactions", json=payload, headers=auth_headers)
    assert resp.status_code == 200


def test_summary_with_no_transactions(client, auth_headers):
    resp = client.get("/summary", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_spend"] == 0
    assert body["by_category"] == []


def test_summary_aggregates_spend_and_income(client, auth_headers):
    create_tx(client, auth_headers, amount=-30.0, category="Dining")
    create_tx(client, auth_headers, amount=-70.0, category="Groceries")
    create_tx(client, auth_headers, amount=1000.0, category="Income")

    resp = client.get("/summary?month=2026-03", headers=auth_headers)
    body = resp.json()
    assert body["total_spend"] == 100.0
    assert body["total_income"] == 1000.0
    assert body["net"] == 900.0

    by_cat = {c["category"]: c["spend"] for c in body["by_category"]}
    assert by_cat["Dining"] == 30.0
    assert by_cat["Groceries"] == 70.0
    assert "Income" not in by_cat  # positive amounts aren't "spend"


def test_summary_bad_month_format(client, auth_headers):
    resp = client.get("/summary?month=not-a-month", headers=auth_headers)
    assert resp.status_code == 400


def test_summary_defaults_to_most_recent_month_with_data(client, auth_headers):
    create_tx(client, auth_headers, date="2025-11-01", amount=-10.0)
    create_tx(client, auth_headers, date="2026-03-10", amount=-20.0)

    resp = client.get("/summary", headers=auth_headers)
    assert resp.json()["month"] == "2026-03"


def test_budget_upsert_and_summary_remaining(client, auth_headers):
    create_tx(client, auth_headers, amount=-30.0, category="Dining")

    resp = client.put("/budgets/Dining", json={"monthly_limit": 100}, headers=auth_headers)
    assert resp.status_code == 200

    resp = client.get("/summary?month=2026-03", headers=auth_headers)
    dining = next(c for c in resp.json()["by_category"] if c["category"] == "Dining")
    assert dining["budget"] == 100.0
    assert dining["remaining"] == 70.0


def test_budget_upsert_is_idempotent_update(client, auth_headers):
    client.put("/budgets/Dining", json={"monthly_limit": 100}, headers=auth_headers)
    client.put("/budgets/Dining", json={"monthly_limit": 150}, headers=auth_headers)

    budgets = client.get("/budgets", headers=auth_headers).json()
    assert len(budgets) == 1
    assert budgets[0]["monthly_limit"] == 150.0


def test_budget_delete(client, auth_headers):
    client.put("/budgets/Dining", json={"monthly_limit": 100}, headers=auth_headers)
    resp = client.delete("/budgets/Dining", headers=auth_headers)
    assert resp.status_code == 200
    assert client.get("/budgets", headers=auth_headers).json() == []


def test_budget_delete_nonexistent(client, auth_headers):
    resp = client.delete("/budgets/Nope", headers=auth_headers)
    assert resp.status_code == 404


def test_monthly_totals_trend(client, auth_headers):
    create_tx(client, auth_headers, date="2026-01-01", amount=-10.0)
    create_tx(client, auth_headers, date="2026-02-01", amount=-20.0)
    create_tx(client, auth_headers, date="2026-03-01", amount=-30.0)

    resp = client.get("/summary?month=2026-03&trailing_months=2", headers=auth_headers)
    months = [m["month"] for m in resp.json()["monthly_totals"]]
    assert months == ["2026-02", "2026-03"]
