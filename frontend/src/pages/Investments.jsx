import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";

const POLL_MS = 15000;

function money(v) {
  if (v === null || v === undefined) return "—";
  return Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function Signed({ value, suffix = "" }) {
  // A missing price is not a flat position — show a dash, never 0.00.
  if (value === null || value === undefined) return <span className="muted">—</span>;
  const n = Number(value);
  return (
    <span className={n > 0 ? "gain" : n < 0 ? "loss" : ""}>
      {n > 0 ? "+" : ""}
      {money(n)}
      {suffix}
    </span>
  );
}

function LogTradeForm({ onCancel, onSaved }) {
  const [form, setForm] = useState({ symbol: "", side: "BUY", quantity: "", limit_price: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      await api.logTrade({
        symbol: form.symbol.trim().toUpperCase(),
        side: form.side,
        quantity: parseFloat(form.quantity),
        limit_price: form.limit_price ? parseFloat(form.limit_price) : null,
      });
      onSaved();
    } catch (err) {
      setError(err.detail || "Could not log the trade");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <form className="modal-card" onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}>
        <h2>Log a trade</h2>
        <p className="muted" style={{ marginTop: -6 }}>
          Record what you believe you traded. The engine reconciles it against what the
          broker actually reports.
        </p>

        <label>
          Symbol
          <input
            required
            maxLength={16}
            placeholder="VOO"
            value={form.symbol}
            onChange={(e) => update("symbol", e.target.value)}
          />
        </label>
        <label>
          Side
          <select value={form.side} onChange={(e) => update("side", e.target.value)}>
            <option value="BUY">Buy</option>
            <option value="SELL">Sell</option>
          </select>
        </label>
        <label>
          Quantity
          <input
            type="number"
            step="0.0001"
            min="0"
            required
            value={form.quantity}
            onChange={(e) => update("quantity", e.target.value)}
          />
        </label>
        <label>
          Price (optional)
          <input
            type="number"
            step="0.01"
            min="0"
            value={form.limit_price}
            onChange={(e) => update("limit_price", e.target.value)}
          />
        </label>

        {error ? <div className="error-banner">{error}</div> : null}

        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="btn" disabled={saving}>
            {saving ? "Saving…" : "Log trade"}
          </button>
        </div>
      </form>
    </div>
  );
}

export default function Investments() {
  const [data, setData] = useState(null);
  const [breaks, setBreaks] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [resetting, setResetting] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [positions, brk] = await Promise.all([
        api.investmentPositions(),
        api.investmentBreaks(),
      ]);
      setData(positions);
      setBreaks(brk);
      setError("");
    } catch (err) {
      // 503 means the engine is down — a separate service, so say which one.
      setError(err.detail || "Could not reach the trade engine");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  const positions = data?.positions ?? [];
  // The API says which source it answered from; the page reads differently for each.
  const isDemo = data?.source === "demo";

  async function resetDemo() {
    setResetting(true);
    try {
      await api.resetInvestmentsDemo();
      await refresh();
    } catch (err) {
      setError(err.detail || "Could not reset the sample data");
    } finally {
      setResetting(false);
    }
  }

  const totalPL = positions.reduce(
    (acc, p) => (p.unrealized_pl == null ? acc : acc + Number(p.unrealized_pl)),
    0
  );

  return (
    <>
      <div className="page-header">
        <h1>Investments</h1>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          {isDemo ? (
            <button className="btn btn-ghost" onClick={resetDemo} disabled={resetting}>
              {resetting ? "Resetting…" : "Reset sample data"}
            </button>
          ) : null}
          <button className="btn" onClick={() => setShowForm(true)}>
            Log a trade
          </button>
        </div>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}

      {/* Say plainly where the numbers come from. The engine is the real source and runs
          locally; on the public demo there is no engine, so this book is the app's own
          and the prices are simulated. Better to state that than to imply a market feed. */}
      {isDemo ? (
        <div className="banner banner-info">
          <strong>Sample portfolio.</strong> Positions are computed from trades recorded
          here, and prices are simulated — this deployment isn't connected to a market
          feed. Log a trade and the table recalculates live. Reconciliation against a
          broker runs in the trade lifecycle engine, which runs locally.
        </div>
      ) : null}

      <div className="panel-head">
        <h2>Positions</h2>
        {data ? (
          <span className="muted">
            {isDemo
              ? "simulated prices"
              : !data.prices_live
                ? "prices unavailable"
                : data.market_open
                  ? "market open — live"
                  : "market closed — last close"}
          </span>
        ) : null}
      </div>

      {loading ? (
        <div className="skeleton" />
      ) : positions.length === 0 ? (
        <p className="muted">No open positions yet — log a trade to get started.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th className="num">Qty</th>
                <th className="num">Avg cost</th>
                <th className="num">Price</th>
                <th className="num">Today</th>
                <th className="num">Value</th>
                <th className="num">P/L</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => (
                <tr key={p.symbol}>
                  <td>{p.symbol}</td>
                  <td className="num">{Number(p.quantity)}</td>
                  <td className="num">{money(p.avg_cost)}</td>
                  <td className="num">{money(p.price)}</td>
                  <td className="num">
                    <Signed value={p.day_change_pct} suffix="%" />
                  </td>
                  <td className="num">{money(p.market_value)}</td>
                  <td className="num">
                    <Signed value={p.unrealized_pl} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data?.prices_live ? (
            <p className="num" style={{ marginTop: 8 }}>
              Total unrealized <Signed value={totalPL} />
            </p>
          ) : null}
        </div>
      )}

      {breaks.length > 0 ? (
        <>
          <div className="panel-head" style={{ marginTop: 28 }}>
            <h2>Open breaks</h2>
            <span className="muted">{breaks.length} needing investigation</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Ours</th>
                  <th>Broker</th>
                </tr>
              </thead>
              <tbody>
                {breaks.map((b) => (
                  <tr key={b.id}>
                    <td>{b.break_type.replaceAll("_", " ").toLowerCase()}</td>
                    <td>{b.our_value ?? "—"}</td>
                    <td>{b.their_value ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      {showForm ? (
        <LogTradeForm
          onCancel={() => setShowForm(false)}
          onSaved={() => {
            setShowForm(false);
            refresh();
          }}
        />
      ) : null}
    </>
  );
}
