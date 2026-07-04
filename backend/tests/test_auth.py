def test_login_success(client):
    resp = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "testpass123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "test@example.com"
    assert body["access_token"]


def test_login_wrong_password(client):
    resp = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "wrong"},
    )
    assert resp.status_code == 401


def test_login_unknown_email(client):
    resp = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )
    assert resp.status_code == 401


def test_me_requires_token(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_with_bad_token(client):
    resp = client.get("/auth/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


def test_me_with_valid_token(client, auth_headers):
    resp = client.get("/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@example.com"


def test_transactions_require_auth(client):
    resp = client.get("/transactions")
    assert resp.status_code == 401
