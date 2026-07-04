import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";

const emptyForm = { date: "", amount: "", merchant: "", category: "", subcategory: "", notes: "" };

function TransactionForm({ initial, onCancel, onSave }) {
  const [form, setForm] = useState(initial ?? emptyForm);
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
      await onSave({ ...form, amount: parseFloat(form.amount) });
    } catch (err) {
      setError(err.detail || "Could not save transaction");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <form className="modal-card" onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}>
        <h2>{initial ? "Edit transaction" : "Add transaction"}</h2>

        <label>
          Date
          <input type="date" required value={form.date} onChange={(e) => update("date", e.target.value)} />
        </label>
        <label>
          Amount (negative = expense, positive = income)
          <input
            type="number"
            step="0.01"
            required
            value={form.amount}
            onChange={(e) => update("amount", e.target.value)}
          />
        </label>
        <label>
          Merchant
          <input value={form.merchant} onChange={(e) => update("merchant", e.target.value)} />
        </label>
        <label>
          Category
          <input value={form.category} onChange={(e) => update("category", e.target.value)} />
        </label>
        <label>
          Subcategory
          <input value={form.subcategory} onChange={(e) => update("subcategory", e.target.value)} />
        </label>
        <label>
          Notes
          <input value={form.notes ?? ""} onChange={(e) => update("notes", e.target.value)} />
        </label>

        {error && <div className="error-banner">{error}</div>}

        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </form>
    </div>
  );
}

export default function Transactions() {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [filters, setFilters] = useState({ month: "", category: "", q: "", start_date: "", end_date: "" });
  const [editing, setEditing] = useState(null); // null | {} (new) | transaction (edit)
  const [uploadSummary, setUploadSummary] = useState(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.listTransactions({ ...filters, limit: 200 });
      setTransactions(data);
    } catch (err) {
      setError(err.detail || "Could not load transactions");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSave(payload) {
    if (editing?.id) {
      await api.updateTransaction(editing.id, payload);
    } else {
      await api.createTransaction(payload);
    }
    setEditing(null);
    await load();
  }

  async function handleDelete(tx) {
    if (!confirm(`Delete transaction "${tx.merchant}" for ${tx.amount}?`)) return;
    await api.deleteTransaction(tx.id);
    await load();
  }

  async function handleFileChange(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadSummary(null);
    try {
      const result = await api.ingestCsv(file);
      setUploadSummary(result);
      await load();
    } catch (err) {
      setUploadSummary({ error: err.detail || "Upload failed" });
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Transactions</h1>
        <div className="header-actions">
          <label className="btn btn-secondary file-btn">
            {uploading ? "Uploading…" : "Upload CSV"}
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              hidden
              disabled={uploading}
              onChange={handleFileChange}
            />
          </label>
          <button className="btn btn-primary" onClick={() => setEditing({})}>
            + Add transaction
          </button>
        </div>
      </div>

      {uploadSummary && (
        <div className={`banner ${uploadSummary.error ? "banner-error" : "banner-info"}`}>
          {uploadSummary.error ? (
            uploadSummary.error
          ) : (
            <>
              Inserted {uploadSummary.inserted}, skipped {uploadSummary.skipped_duplicates} duplicate(s) and{" "}
              {uploadSummary.skipped_errors} error row(s).
              {uploadSummary.errors?.length > 0 && (
                <ul>
                  {uploadSummary.errors.map((e, i) => (
                    <li key={i}>
                      Row {e.row}: {e.reason}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      )}

      <div className="filter-bar">
        <input
          type="month"
          value={filters.month}
          onChange={(e) => setFilters((f) => ({ ...f, month: e.target.value }))}
        />
        <input
          placeholder="Category"
          value={filters.category}
          onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value }))}
        />
        <input
          placeholder="Search merchant…"
          value={filters.q}
          onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))}
        />
        <input
          type="date"
          title="Start date"
          value={filters.start_date}
          onChange={(e) => setFilters((f) => ({ ...f, start_date: e.target.value }))}
        />
        <input
          type="date"
          title="End date"
          value={filters.end_date}
          onChange={(e) => setFilters((f) => ({ ...f, end_date: e.target.value }))}
        />
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Merchant</th>
              <th>Category</th>
              <th className="num">Amount</th>
              <th>Notes</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6}>Loading…</td>
              </tr>
            ) : transactions.length === 0 ? (
              <tr>
                <td colSpan={6}>No transactions found.</td>
              </tr>
            ) : (
              transactions.map((t) => (
                <tr key={t.id}>
                  <td>{t.date}</td>
                  <td>{t.merchant}</td>
                  <td>
                    {t.category}
                    <span className="muted"> / {t.subcategory}</span>
                  </td>
                  <td className={`num ${t.amount < 0 ? "negative" : "positive"}`}>
                    {t.amount.toFixed(2)}
                  </td>
                  <td>{t.notes}</td>
                  <td className="row-actions">
                    <button className="btn btn-ghost" onClick={() => setEditing(t)}>
                      Edit
                    </button>
                    <button className="btn btn-ghost danger" onClick={() => handleDelete(t)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {editing && (
        <TransactionForm
          initial={editing.id ? editing : null}
          onCancel={() => setEditing(null)}
          onSave={handleSave}
        />
      )}
    </div>
  );
}
