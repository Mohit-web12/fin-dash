"""The investments proxy to the trade engine.

The engine is a separate service, so these stub it out. What matters here is fin-dash's
side of the contract: that the routes require a login, that engine responses pass through
unchanged, and that an engine which is down becomes a 503 the page can explain rather
than a 500.
"""

import pytest

from services import engine as engine_client
from services.engine import EngineError

SAMPLE_POSITIONS = {
    "positions": [
        {
            "symbol": "VOO",
            "quantity": "10.0000",
            "avg_cost": "500.00",
            "price": "520.00",
            "day_change_pct": "0.27",
            "market_value": "5200.00",
            "cost_basis": "5000.00",
            "unrealized_pl": "200.00",
            "unrealized_pl_pct": "4.00",
        }
    ],
    "prices_live": True,
    "market_open": False,
}


@pytest.fixture
def stub_engine(monkeypatch):
    monkeypatch.setattr(engine_client, "get_positions", lambda: SAMPLE_POSITIONS)
    monkeypatch.setattr(engine_client, "get_breaks", lambda: [])
    monkeypatch.setattr(engine_client, "get_trades", lambda: [])


@pytest.fixture
def dead_engine(monkeypatch):
    def boom(*a, **kw):
        raise EngineError("cannot reach the trade engine at http://localhost:8000")

    monkeypatch.setattr(engine_client, "get_positions", boom)
    monkeypatch.setattr(engine_client, "get_breaks", boom)
    return boom


# -- auth ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/investments/positions", "/investments/breaks", "/investments/trades"])
def test_investments_require_auth(client, path):
    """The engine has no auth of its own — these routes are what protects it."""
    assert client.get(path).status_code in (401, 403)


def test_logging_a_trade_requires_auth(client):
    resp = client.post("/investments/orders", json={"symbol": "VOO", "side": "BUY", "quantity": 1})
    assert resp.status_code in (401, 403)


# -- pass-through -------------------------------------------------------------------


def test_positions_pass_through_unchanged(client, auth_headers, stub_engine):
    resp = client.get("/investments/positions", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["positions"][0]["symbol"] == "VOO"
    # the market/price flags must survive the proxy — the UI renders differently on them
    assert body["prices_live"] is True
    assert body["market_open"] is False


# -- the engine being down ----------------------------------------------------------


def test_engine_down_is_503_not_500(client, auth_headers, dead_engine):
    """A separate service being unavailable is not an application error. 503 plus the
    reason lets the page say the engine is down."""
    resp = client.get("/investments/positions", headers=auth_headers)
    assert resp.status_code == 503
    assert "trade engine" in resp.json()["detail"]


# -- placing an order ---------------------------------------------------------------


def test_log_trade_normalises_and_forwards(client, auth_headers, monkeypatch):
    captured = {}

    def fake_place(symbol, side, quantity, limit_price=None):
        captured.update(symbol=symbol, side=side, quantity=quantity, limit_price=limit_price)
        return {"order_id": "o-1", "trade_id": "t-1", "status": "PLACED"}

    import app as app_module

    monkeypatch.setattr(app_module, "engine_place_order", fake_place)
    resp = client.post(
        "/investments/orders",
        json={"symbol": "voo", "side": "BUY", "quantity": 10, "limit_price": 500.25},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert captured["symbol"] == "VOO"  # lowercased input is normalised
    assert captured["quantity"] == 10
    assert captured["limit_price"] == 500.25


def test_log_trade_rejects_a_bad_side(client, auth_headers):
    resp = client.post(
        "/investments/orders",
        json={"symbol": "VOO", "side": "HOLD", "quantity": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_log_trade_rejects_non_positive_quantity(client, auth_headers):
    resp = client.post(
        "/investments/orders",
        json={"symbol": "VOO", "side": "BUY", "quantity": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 422
