"""Client for the trade lifecycle engine.

fin-dash talks to the engine server-to-server, never from the browser. The engine has no
auth of its own, so it must not be publicly reachable — routing calls through here means
fin-dash's existing JWT is what guards the data, and the engine can stay on a private
network.

stdlib urllib rather than httpx: httpx is only a dev dependency here, and this is four
GETs and a POST.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from config import settings


class EngineError(Exception):
    """The engine is unreachable or returned an error."""


def _call(method, path, body=None, timeout=10):
    url = f"{settings.engine_base_url.rstrip('/')}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        method=method,
        data=data,
        headers={"content-type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise EngineError(f"engine returned {e.code}: {e.read().decode()[:200]}") from e
    except urllib.error.URLError as e:
        # The engine is a separate service and may simply be down; callers turn this into
        # a 503 so the page can say so rather than appearing broken.
        raise EngineError(f"cannot reach the trade engine at {url}: {e.reason}") from e


def get_positions():
    """Current holdings with live prices and P/L."""
    return _call("GET", "/positions")


def get_breaks():
    """Reconciliation breaks between our book and the broker's records."""
    return _call("GET", "/breaks")


def get_trades():
    return _call("GET", "/trades")


def place_order(symbol, side, quantity, limit_price=None):
    """Record an intended trade in the engine.

    This is deliberately NOT a broker order — it logs what you believe you did. The
    engine reconciles that against what the broker actually reports, which is the whole
    point: two independent records, and the gap between them is the break.
    """
    body = {"symbol": symbol, "side": side, "quantity": str(quantity)}
    if limit_price is not None:
        body["limit_price"] = str(limit_price)
    return _call("POST", "/orders", body)
