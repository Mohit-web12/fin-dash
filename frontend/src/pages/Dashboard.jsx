import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";

const COLORS = ["#6366f1", "#22c55e", "#f97316", "#ec4899", "#06b6d4", "#eab308", "#8b5cf6", "#ef4444"];

export default function Dashboard() {
  const [month, setMonth] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [budgetDraft, setBudgetDraft] = useState({});

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
    await api.upsertBudget(category, value);
    await load(month);
  }

  if (loading) return <div className="page-loading">Loading…</div>;
  if (error) return <div className="error-banner">{error}</div>;
  if (!data) return null;

  const pieData = data.by_category.filter((c) => c.spend > 0);

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

      <div className="stat-row">
        <div className="stat-card">
          <div className="stat-label">Spend</div>
          <div className="stat-value negative">${data.total_spend.toFixed(2)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Income</div>
          <div className="stat-value positive">${data.total_income.toFixed(2)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Net</div>
          <div className={`stat-value ${data.net < 0 ? "negative" : "positive"}`}>
            ${data.net.toFixed(2)}
          </div>
        </div>
      </div>

      <div className="chart-row">
        <div className="chart-card">
          <h3>Spending by category — {data.month}</h3>
          {pieData.length === 0 ? (
            <p className="muted">No spending recorded for this month.</p>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={pieData}
                  dataKey="spend"
                  nameKey="category"
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  label={(entry) => entry.category}
                >
                  {pieData.map((entry, i) => (
                    <Cell key={entry.category} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => `$${v.toFixed(2)}`} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="chart-card">
          <h3>Monthly trend</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={data.monthly_totals}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
              <XAxis dataKey="month" />
              <YAxis />
              <Tooltip formatter={(v) => `$${Number(v).toFixed(2)}`} />
              <Legend />
              <Bar dataKey="spend" fill="#ef4444" name="Spend" />
              <Bar dataKey="income" fill="#22c55e" name="Income" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="table-wrap">
        <h3>Budgets — actual vs. limit</h3>
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
                  <button className="btn btn-ghost" onClick={() => handleBudgetSave(c.category)}>
                    Save
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
