import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import Gauge from "../components/Gauge";
import { api } from "../api/client";

const money = (n) => `${n < 0 ? "-" : ""}$${Math.abs(n).toFixed(2)}`;

const tickStyle = { fill: "var(--text-muted)", fontSize: 12, fontFamily: "var(--font-body)" };
const tooltipContentStyle = {
  background: "var(--surface-2)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-sm)",
  fontFamily: "var(--font-body)",
  fontSize: "var(--text-sm)",
};

function DashboardSkeleton() {
  return (
    <div>
      <div className="page-header">
        <h1>Dashboard</h1>
        <div className="skeleton" style={{ width: "140px", height: "36px" }} />
      </div>

      <div className="gauge-row">
        {Array.from({ length: 3 }).map((_, i) => (
          <div className="gauge-card" key={i}>
            <div className="skeleton" style={{ width: "150px", height: "150px", borderRadius: "50%", margin: "0 auto" }} />
            <div className="skeleton" style={{ width: "80px", height: "22px", margin: "12px auto 0" }} />
          </div>
        ))}
      </div>

      <div className="chart-row">
        {Array.from({ length: 2 }).map((_, i) => (
          <div className="chart-card" key={i}>
            <div className="skeleton" style={{ width: "180px", height: "16px", marginBottom: "16px" }} />
            <div className="skeleton" style={{ width: "100%", height: "220px" }} />
          </div>
        ))}
      </div>
    </div>
  );
}

// Bars ranked by length in one accent color, not a multi-hue pie — the
// vintage palette only has three real colors and a 7-category pie would
// need seven, so rank-by-length reads better than inventing more hues.
function CategoryBreakdown({ categories }) {
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setRevealed(true), 100);
    return () => clearTimeout(t);
  }, []);

  const withSpend = categories.filter((c) => c.spend > 0);
  if (withSpend.length === 0) {
    return <p className="muted">No spending recorded for this month.</p>;
  }
  const max = Math.max(...withSpend.map((c) => c.spend));

  return (
    <div>
      {withSpend.map((c) => (
        <div className="cat-row" key={c.category}>
          <div className="cat-name">{c.category}</div>
          <div className="cat-track">
            <div className="cat-fill" style={{ width: revealed ? `${(c.spend / max) * 100}%` : "0%" }} />
          </div>
          <div className="cat-value">{money(c.spend)}</div>
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const [month, setMonth] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [budgetDraft, setBudgetDraft] = useState({});
  const [savingCategory, setSavingCategory] = useState(null);

  async function load(m) {
    setLoading(true);
    setError("");
    try {
      const result = await api.summary(m ? { month: m } : {});
      setData(result);
      setMonth(result.month);
    } catch (err) {
      setError(err.detail || "Could not load summary");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleBudgetSave(category) {
    const value = parseFloat(budgetDraft[category]);
    if (Number.isNaN(value)) return;
    setSavingCategory(category);
    try {
      await api.upsertBudget(category, value);
      await load(month);
    } finally {
      setSavingCategory(null);
    }
  }

  if (loading) return <DashboardSkeleton />;
  if (error) return <div className="error-banner">{error}</div>;
  if (!data) return null;

  const totalBudget = data.by_category.reduce((sum, c) => sum + (c.budget || 0), 0);
  const gaugeMax = Math.max(totalBudget, data.total_spend, data.total_income, 1);
  const spendSub = totalBudget > 0 ? `of ${money(totalBudget)} budget` : "no budget set";
  const savingsRate = data.total_income > 0 ? Math.round((data.net / data.total_income) * 100) : null;
  const netSub = savingsRate != null ? `${savingsRate}% of income saved` : "this month";

  return (
    <div>
      <div className="page-header">
        <h1>Dashboard</h1>
        <input
          type="month"
          value={month}
          onChange={(e) => {
            setMonth(e.target.value);
            load(e.target.value);
          }}
        />
      </div>

      <div className="gauge-row">
        <Gauge label="Spend" value={data.total_spend} max={gaugeMax} sub={spendSub} accent="var(--accent)" />
        <Gauge label="Income" value={data.total_income} max={gaugeMax} sub="this month" accent="var(--positive)" />
        <Gauge label="Net" value={data.net} max={gaugeMax} sub={netSub} accent="var(--brass)" />
      </div>

      <div className="chart-row">
        <div className="chart-card">
          <div className="panel-head">
            <h3>Spending by category</h3>
            <span className="suffix">{data.month}</span>
          </div>
          <div className="rule" />
          <CategoryBreakdown categories={data.by_category} />
        </div>

        <div className="chart-card">
          <h3>Monthly trend</h3>
          <div className="rule" />
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={data.monthly_totals}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis dataKey="month" tick={tickStyle} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
              <YAxis tick={tickStyle} axisLine={false} tickLine={false} width={40} />
              <Tooltip
                formatter={(v) => `$${Number(v).toFixed(2)}`}
                contentStyle={tooltipContentStyle}
                labelStyle={{ color: "var(--text-muted)" }}
                itemStyle={{ color: "var(--text)" }}
                cursor={{ fill: "var(--surface-2)" }}
              />
              <Legend wrapperStyle={{ color: "var(--text-muted)", fontSize: "var(--text-sm)", fontFamily: "var(--font-body)" }} />
              <Bar dataKey="spend" fill="var(--negative)" name="Spend" radius={[3, 3, 0, 0]} />
              <Bar dataKey="income" fill="var(--positive)" name="Income" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="table-wrap">
        <div className="panel-head">
          <h3>Budgets — actual vs. limit</h3>
          <span className="suffix">{data.month}</span>
        </div>
        <div className="rule" />
        <table>
          <thead>
            <tr>
              <th>Category</th>
              <th className="num">Spend</th>
              <th className="num">Budget</th>
              <th className="num">Remaining</th>
              <th>Set budget</th>
            </tr>
          </thead>
          <tbody>
            {data.by_category.map((c) => (
              <tr key={c.category}>
                <td>{c.category}</td>
                <td className="num">${c.spend.toFixed(2)}</td>
                <td className="num">{c.budget != null ? `$${c.budget.toFixed(2)}` : "—"}</td>
                <td className={`num ${c.remaining != null && c.remaining < 0 ? "negative" : ""}`}>
                  {c.remaining != null ? `$${c.remaining.toFixed(2)}` : "—"}
                </td>
                <td>
                  <input
                    type="number"
                    step="1"
                    placeholder={c.budget ?? "e.g. 200"}
                    className="budget-input"
                    value={budgetDraft[c.category] ?? ""}
                    onChange={(e) =>
                      setBudgetDraft((d) => ({ ...d, [c.category]: e.target.value }))
                    }
                  />
                  <button
                    className="btn btn-ghost"
                    disabled={savingCategory === c.category}
                    onClick={() => handleBudgetSave(c.category)}
                  >
                    {savingCategory === c.category ? "Saving…" : "Save"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
