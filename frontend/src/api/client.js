const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const TOKEN_KEY = "fin_dash_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, { method = "GET", body, isForm = false } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body && !isForm) headers["Content-Type"] = "application/json";

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: isForm ? body : body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 204) return null;

  const data = await res.json().catch(() => null);

  if (!res.ok) {
    throw new ApiError(res.status, data?.detail ?? res.statusText);
  }
  return data;
}

export const api = {
  login: (email, password) => request("/auth/login", { method: "POST", body: { email, password } }),
  me: () => request("/auth/me"),

  listTransactions: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v !== "" && v != null))
    ).toString();
    return request(`/transactions${qs ? `?${qs}` : ""}`);
  },
  createTransaction: (payload) => request("/transactions", { method: "POST", body: payload }),
  updateTransaction: (id, payload) => request(`/transactions/${id}`, { method: "PUT", body: payload }),
  deleteTransaction: (id) => request(`/transactions/${id}`, { method: "DELETE" }),

  ingestCsv: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/ingest/csv", { method: "POST", body: form, isForm: true });
  },

  summary: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v !== "" && v != null))
    ).toString();
    return request(`/summary${qs ? `?${qs}` : ""}`);
  },

  listBudgets: () => request("/budgets"),
  upsertBudget: (category, monthlyLimit) =>
    request(`/budgets/${encodeURIComponent(category)}`, {
      method: "PUT",
      body: { monthly_limit: monthlyLimit },
    }),
  deleteBudget: (category) => request(`/budgets/${encodeURIComponent(category)}`, { method: "DELETE" }),
};

export { ApiError };
