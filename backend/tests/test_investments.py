"""The investments proxy to the trade engine.

The engine is a separate service, so these stub it out. What matters here is SpendGauge's
side of the contract: that the routes require a login, that engine responses pass through
unchanged, and that an engine which is down becomes a 503 the page can explain rather
than a 500.
"""

import pytest

from auth import SessionLocal
from config import settings
from services import demo_investments, engine as engine_client
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
def engine_mode(monkeypatch):
    """Configure an engine URL.

    The routes only proxy when one is set; unset means the local demo book. These tests
    are about the proxy, so they have to opt in rather than rely on a default.
    """
    monkeypatch.setattr(settings, "engine_base_url", "http://engine.test:8000")


@pytest.fixture
def stub_engine(monkeypatch, engine_mode):
    monkeypatch.setattr(engine_client, "get_positions", lambda: SAMPLE_POSITIONS)
    monkeypatch.setattr(engine_client, "get_breaks", lambda: [])
    monkeypatch.setattr(engine_client, "get_trades", lambda: [])


@pytest.fixture
def dead_engine(monkeypatch, engine_mode):
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


def test_log_trade_normalises_and_forwards(client, auth_headers, monkeypatch, engine_mode):
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


@pytest.fixture
def demo_book(client):
    """Seed the sample portfolio.

    conftest disables demo seeding globally so the transaction tests start empty; these
    tests need the book, so they ask for it explicitly.
    """
    db = SessionLocal()
    try:
        demo_investments.seed_demo_trades(db)
    finally:
        db.close()
    return client


# -- without an engine: the local book ------------------------------------------------
#
# This is the public demo's path. The engine runs locally and can't be reached from the
# deploy, so Investments has to stand on its own rather than surface an error.


def test_positions_fall_back_to_local_book(demo_book, client, auth_headers):
    resp = client.get("/investments/positions", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "demo"
    # Prices are simulated here; saying otherwise would misrepresent them.
    assert body["prices_live"] is False
    assert len(body["positions"]) > 0


def test_breaks_are_empty_not_an_error_without_an_engine(client, auth_headers):
    """Reconciliation needs a second record to compare against, and there isn't one
    locally. Empty is the truthful answer; a 503 would read as broken."""
    resp = client.get("/investments/breaks", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_logging_a_trade_changes_the_positions(demo_book, client, auth_headers):
    """The interaction the demo exists for: log a trade, watch the book recalculate."""
    before = {p["symbol"]: p for p in client.get("/investments/positions", headers=auth_headers).json()["positions"]}
    start_qty = before["VOO"]["quantity"]

    resp = client.post(
        "/investments/orders",
        json={"symbol": "voo", "side": "BUY", "quantity": 5, "limit_price": 400},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["symbol"] == "VOO"  # normalised

    after = {p["symbol"]: p for p in client.get("/investments/positions", headers=auth_headers).json()["positions"]}
    assert after["VOO"]["quantity"] == start_qty + 5
    # A cheaper buy has to pull the weighted average down.
    assert after["VOO"]["avg_cost"] < before["VOO"]["avg_cost"]


def test_selling_everything_removes_the_position(demo_book, client, auth_headers):
    before = {p["symbol"]: p for p in client.get("/investments/positions", headers=auth_headers).json()["positions"]}
    qty = before["TSLA"]["quantity"]
    client.post(
        "/investments/orders",
        json={"symbol": "TSLA", "side": "SELL", "quantity": qty},
        headers=auth_headers,
    )
    after = [p["symbol"] for p in client.get("/investments/positions", headers=auth_headers).json()["positions"]]
    assert "TSLA" not in after


def test_reset_restores_the_sample_book(demo_book, client, auth_headers):
    client.post(
        "/investments/orders",
        json={"symbol": "GME", "side": "BUY", "quantity": 1000},
        headers=auth_headers,
    )
    assert "GME" in [p["symbol"] for p in client.get("/investments/positions", headers=auth_headers).json()["positions"]]

    resp = client.post("/investments/demo/reset", headers=auth_headers)
    assert resp.status_code == 200
    symbols = [p["symbol"] for p in client.get("/investments/positions", headers=auth_headers).json()["positions"]]
    assert "GME" not in symbols
    assert "VOO" in symbols


def test_reset_is_rejected_when_an_engine_owns_the_book(client, auth_headers, engine_mode):
    """With the engine connected it is the system of record — wiping local rows would be
    meaningless at best and misleading at worst."""
    assert client.post("/investments/demo/reset", headers=auth_headers).status_code == 400
