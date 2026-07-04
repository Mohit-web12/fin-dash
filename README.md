# Fin Dash

A full-stack personal finance / expense tracker: FastAPI + SQLAlchemy + SQLite backend, React (Vite) frontend, JWT auth, CSV import with auto-categorization, and a dashboard with spending-by-category and budget-vs-actual charts.

## Stack

- **Backend:** FastAPI, SQLAlchemy 2.0, SQLite, pandas (CSV ingest), PyJWT + bcrypt (auth)
- **Frontend:** React 19 + Vite, React Router, Recharts
- **Deployment:** Docker / docker-compose locally, Render in the cloud (see below)

## Running locally

### Option A — Docker Compose (closest to production)

```bash
docker compose up --build
```

- API: http://localhost:8000 (docs at `/docs`)
- Web app: http://localhost:3000

Override defaults (JWT secret, seed user credentials, CORS origins) via a `.env` file at the repo root or exported env vars — see `backend/.env.example` for the full list. `docker-compose.yml` reads them with sensible dev defaults if unset.

The SQLite file lives in the `backend_data` named volume (mounted at `/app/data` in the container), so it survives `docker compose down` / restarts. `docker compose down -v` will wipe it.

### Option B — manual dev (faster iteration, hot reload)

Backend:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt   # includes pytest/httpx on top of requirements.txt
cp .env.example .env                  # adjust if needed
uvicorn app:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
cp .env.example .env.local            # VITE_API_BASE_URL, defaults to localhost:8000
npm run dev
```

On first boot the backend seeds one user from `SEED_USER_EMAIL` / `SEED_USER_PASSWORD` (defaults: `demo@example.com` / `changeme123`) — that's what you log in with.

## Running tests

```bash
cd backend
source .venv/bin/activate
pytest
```

38 tests covering auth, transaction CRUD + filtering, CSV ingest edge cases (missing columns, bad rows, dedup), and the summary/budgets endpoints. Each run uses an isolated temp SQLite DB (see `tests/conftest.py`), so it doesn't touch your dev `finance.db`.

## API overview

All routes except `/health` and `/auth/login` require `Authorization: Bearer <token>`, obtained from `/auth/login`. Full interactive docs (Swagger) are at `/docs` when the backend is running.

| Route | Purpose |
|---|---|
| `POST /auth/login` | Exchange email/password for a JWT |
| `GET /auth/me` | Current user |
| `GET/POST /accounts` | List / create accounts (e.g. "Checking") |
| `GET/POST /transactions` | List (with filters: month, date range, category, search, amount range) / create |
| `GET/PUT/DELETE /transactions/{id}` | Fetch / update / delete one transaction |
| `POST /ingest/csv` | Bulk-import a CSV; auto-categorizes merchants unless the CSV already has category/subcategory columns; skips bad rows and duplicate rows and reports why |
| `GET/PUT/DELETE /budgets/{category}` | List / upsert / delete a monthly budget for a category |
| `GET /summary` | Spend/income/net for a month, spend-by-category with budget-vs-actual, and a trailing monthly trend — powers the dashboard |

## Data model

- `User` — single seeded user for now (no self-serve registration)
- `Account` — optional; a transaction can be tagged with one
- `Transaction` — the core record: date, amount (negative = expense, positive = income), merchant, category/subcategory, notes, `dedupe_key` (hash of user+date+amount+merchant, used to skip duplicate CSV rows)
- `Budget` — a monthly spending limit per category, per user

No migration tool is wired up — tables are created via `Base.metadata.create_all()` on startup, which is fine for SQLite at this scale. (Alembic was in the original dependency list but never initialized, so it was removed rather than left as dead weight implying a capability that didn't exist.)

## Deployment (Render)

Render was chosen over Fly.io/Railway because it deploys both a Docker web service (backend) and a static site (frontend build) from one `render.yaml` Blueprint, with a genuinely free tier for both and no credit card required.

**Trade-off to know:** Render's free web service plan has an *ephemeral filesystem* — the SQLite file resets on every deploy and on periodic restarts. Fine for a portfolio demo (the seed user always comes back); if you need data to actually persist, uncomment the `disk:` block in `render.yaml` and move the backend off the free plan (a Render persistent disk is a few dollars/month), or self-host with the included `docker-compose.yml` on a VM/Fly volume instead.

### Deploy steps

1. Push this repo to GitHub (already done if you're reading this from the remote).
2. In the Render dashboard: **New → Blueprint**, point it at this repo. Render reads `render.yaml` and proposes two services: `fin-dash-api` (Docker web service) and `fin-dash-web` (static site).
3. When prompted, set the two secret env vars on `fin-dash-api` (marked `sync: false` in the blueprint so they aren't stored in git):
   - `SEED_USER_EMAIL`
   - `SEED_USER_PASSWORD`
   `JWT_SECRET` is auto-generated by Render (`generateValue: true`); you don't set it.
4. Deploy. Render will give you real URLs like `https://fin-dash-api-xxxx.onrender.com` and `https://fin-dash-web-xxxx.onrender.com`.
5. Update two placeholder values to match those real URLs, then trigger a redeploy of both services (Vite bakes its env var in at build time, so the frontend must rebuild):
   - `CORS_ORIGINS` on `fin-dash-api` → the frontend's URL
   - `VITE_API_BASE_URL` on `fin-dash-web` → the backend's URL
6. Log in with the seed credentials from step 3.

Free-tier web services spin down after 15 minutes of inactivity; the first request after idling takes ~30-50s to cold-start. Expected, not a bug.
