def create_tx(client, auth_headers, **overrides):
    payload = {
        "date": "2026-01-15",
        "amount": -20.0,
        "merchant": "Test Merchant",
        "category": "Shopping",
        "subcategory": "Online",
        "notes": "note",
    }
    payload.update(overrides)
    resp = client.post("/transactions", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    return resp.json()["id"]


def test_create_and_get_transaction(client, auth_headers):
    tx_id = create_tx(client, auth_headers)
    resp = client.get(f"/transactions/{tx_id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["merchant"] == "Test Merchant"
    assert body["amount"] == -20.0


def test_create_missing_required_fields(client, auth_headers):
    resp = client.post("/transactions", json={"amount": -5}, headers=auth_headers)
    assert resp.status_code == 422


def test_get_nonexistent_transaction(client, auth_headers):
    resp = client.get("/transactions/99999", headers=auth_headers)
    assert resp.status_code == 404


def test_update_transaction(client, auth_headers):
    tx_id = create_tx(client, auth_headers)
    resp = client.put(f"/transactions/{tx_id}", json={"notes": "updated"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["notes"] == "updated"


def test_update_nonexistent_transaction(client, auth_headers):
    resp = client.put("/transactions/99999", json={"notes": "x"}, headers=auth_headers)
    assert resp.status_code == 404


def test_delete_transaction(client, auth_headers):
    tx_id = create_tx(client, auth_headers)
    resp = client.delete(f"/transactions/{tx_id}", headers=auth_headers)
    assert resp.status_code == 200

    resp = client.get(f"/transactions/{tx_id}", headers=auth_headers)
    assert resp.status_code == 404


def test_list_filters_by_month(client, auth_headers):
    create_tx(client, auth_headers, date="2026-01-05")
    create_tx(client, auth_headers, date="2026-02-05")

    resp = client.get("/transactions?month=2026-01", headers=auth_headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["date"] == "2026-01-05"


def test_list_bad_month_format(client, auth_headers):
    resp = client.get("/transactions?month=2026-13", headers=auth_headers)
    assert resp.status_code == 400


def test_list_filters_by_category_and_search(client, auth_headers):
    create_tx(client, auth_headers, merchant="Starbucks", category="Dining")
    create_tx(client, auth_headers, merchant="Shell Gas", category="Transport")

    resp = client.get("/transactions?category=Dining", headers=auth_headers)
    assert [t["merchant"] for t in resp.json()] == ["Starbucks"]

    resp = client.get("/transactions?q=shell", headers=auth_headers)
    assert [t["merchant"] for t in resp.json()] == ["Shell Gas"]


def test_list_ordering_and_amount_range(client, auth_headers):
    create_tx(client, auth_headers, amount=-5.0, merchant="Small")
    create_tx(client, auth_headers, amount=-50.0, merchant="Big")

    resp = client.get("/transactions?order=amount_asc", headers=auth_headers)
    amounts = [t["amount"] for t in resp.json()]
    assert amounts == sorted(amounts)

    resp = client.get("/transactions?min_amount=-10&max_amount=0", headers=auth_headers)
    assert [t["merchant"] for t in resp.json()] == ["Small"]


def test_transactions_are_scoped_to_user(client, auth_headers):
    """A second user must never see the first user's transactions."""
    create_tx(client, auth_headers, merchant="User1 purchase")

    # Register a second login isn't supported (single seeded user), so instead
    # verify directly that a forged token for a nonexistent user is rejected
    # rather than silently falling back to another user's data.
    import jwt as pyjwt

    from config import settings

    fake_token = pyjwt.encode({"sub": "999999"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    resp = client.get("/transactions", headers={"Authorization": f"Bearer {fake_token}"})
    assert resp.status_code == 401
