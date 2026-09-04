"""Investments data for when the trade lifecycle engine isn't connected.

The engine runs locally and is not reachable from the public deploy, so without this the
Investments page renders an error on the live demo. These functions let the page stand on
its own: positions are derived from the user's own InvestmentTrade rows, exactly the way
the engine derives them from its event log.

Prices here are SIMULATED, not market data. SpendGauge has no market feed. The number is
a deterministic walk around a fixed base per symbol, so the panel moves while someone is
looking at it without ever claiming to be real. Everything that reads this is expected to
label it as sample data — see `source: "demo"` on the API responses.
"""

import math
import random
import time
from datetime import date, timedelta

from sqlalchemy.orm import Session

from models import InvestmentTrade, User

# (symbol, side, quantity, price, days ago). Chosen to produce a mixed book: a couple of
# clear winners, one loser, and one position built from two buys at different prices so
# the average-cost maths is visible rather than trivial.
DEMO_TRADES = [
    ("VOO",  "BUY", 12, 498.20, 172),
    ("VOO",  "BUY",  6, 536.75,  61),
    ("AAPL", "BUY", 40, 214.30, 138),
    ("NVDA", "BUY", 25, 121.40, 96),
    ("MSFT", "BUY", 15, 447.90, 47),
    ("TSLA", "BUY", 18, 289.60, 24),
]

# Base price per symbol for the simulated walk. Roughly plausible, deliberately not
# pretending to be a quote.
BASE_PRICES = {
    "VOO": 552.40,
    "AAPL": 231.75,
    "NVDA": 138.20,
    "MSFT": 466.10,
    "TSLA": 262.90,
}

# How far the simulated price wanders from base, and how fast.
DRIFT_PCT = 0.018
DRIFT_PERIOD_SECONDS = 90.0


def simulated_price(symbol: str, now: float | None = None) -> float:
    """A gently moving price for `symbol`.

    Deterministic given the clock, so two viewers loading the page at the same moment see
    the same number, and a single viewer watching sees it move. A sine wave (rather than a
    random walk) keeps it bounded — a random walk left running for days would drift into
    nonsense.
    """
    base = BASE_PRICES.get(symbol)
    if base is None:
        # Unknown symbol (someone logged a trade in something we have no base for):
        # derive a stable pseudo-price from the name so it at least behaves consistently.
        base = 50 + (sum(ord(c) for c in symbol) % 400)
    now = time.time() if now is None else now
    phase = (sum(ord(c) for c in symbol) % 100) / 100 * math.tau
    wave = math.sin(now / DRIFT_PERIOD_SECONDS + phase)
    return round(base * (1 + DRIFT_PCT * wave), 2)


def seed_demo_trades(db: Session, today: date | None = None) -> int:
    """Give the demo account an opening book. No-op if it already has trades."""
    user = db.query(User).order_by(User.id).first()
    if user is None:
        return 0
    if db.query(InvestmentTrade).filter(InvestmentTrade.user_id == user.id).count() > 0:
        return 0

    today = today or date.today()
    rows = [
        InvestmentTrade(
            user_id=user.id,
            symbol=symbol,
            side=side,
            quantity=float(qty),
            price=float(price),
            traded_on=today - timedelta(days=days_ago),
        )
        for symbol, side, qty, price, days_ago in DEMO_TRADES
    ]
    db.add_all(rows)
    db.commit()
    return len(rows)


def compute_positions(db: Session, user_id: int) -> list[dict]:
    """Net holdings per symbol, priced with the simulated feed.

    Same shape the engine's /positions returns, so the frontend renders either source
    without branching. Cost basis is a weighted average over buys; sells reduce the
    quantity. Symbols that net to zero or below drop out — this models a long-only book,
    the same limitation the engine has.
    """
    trades = (
        db.query(InvestmentTrade)
        .filter(InvestmentTrade.user_id == user_id)
        .order_by(InvestmentTrade.traded_on)
        .all()
    )

    agg: dict[str, dict[str, float]] = {}
    for t in trades:
        a = agg.setdefault(t.symbol, {"buy_qty": 0.0, "buy_notional": 0.0, "sell_qty": 0.0})
        if (t.side or "").upper() == "BUY":
            a["buy_qty"] += t.quantity or 0.0
            a["buy_notional"] += (t.quantity or 0.0) * (t.price or 0.0)
        else:
            a["sell_qty"] += t.quantity or 0.0

    out: list[dict] = []
    for symbol in sorted(agg):
        a = agg[symbol]
        net = a["buy_qty"] - a["sell_qty"]
        if net <= 0:
            continue
        avg_cost = (a["buy_notional"] / a["buy_qty"]) if a["buy_qty"] else 0.0
        price = simulated_price(symbol)
        market_value = net * price
        cost_basis = net * avg_cost
        pl = market_value - cost_basis
        out.append(
            {
                "symbol": symbol,
                "quantity": round(net, 4),
                "avg_cost": round(avg_cost, 2),
                "price": price,
                # Day change is not knowable without a real feed; the walk is the only
                # movement we have, so express it against base rather than inventing an open.
                "day_change_pct": round((price / BASE_PRICES.get(symbol, price) - 1) * 100, 2),
                "market_value": round(market_value, 2),
                "cost_basis": round(cost_basis, 2),
                "unrealized_pl": round(pl, 2),
                "unrealized_pl_pct": round((pl / cost_basis * 100) if cost_basis else 0.0, 2),
            }
        )
    return out


def record_trade(db: Session, user_id: int, symbol: str, side: str,
                 quantity: float, price: float | None) -> InvestmentTrade:
    """Log a trade against the local book. Falls back to the simulated price when the
    user didn't supply one, so a position always has a cost basis."""
    trade = InvestmentTrade(
        user_id=user_id,
        symbol=symbol.upper(),
        side=side.upper(),
        quantity=float(quantity),
        price=float(price) if price is not None else simulated_price(symbol.upper()),
        traded_on=date.today(),
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade
