import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("demo@example.com");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(email, password);
      navigate(location.state?.from ?? "/", { replace: true });
    } catch (err) {
      setError(err.detail || "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1>SpendGauge</h1>
        <p className="muted">Sign in to your finance dashboard</p>

        <div className="demo-hint">
          <span className="demo-hint-label">Demo account</span>
          <dl>
            <dt>Email</dt>
            <dd><code>demo@example.com</code></dd>
            <dt>Password</dt>
            <dd><code>password</code></dd>
          </dl>
          <button
            type="button"
            className="demo-hint-fill"
            onClick={() => {
              setEmail("demo@example.com");
              setPassword("password");
            }}
          >
            Fill these in
          </button>
        </div>

        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>

        {error && <div className="error-banner">{error}</div>}

        <button className="btn btn-primary" type="submit" disabled={submitting}>
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
