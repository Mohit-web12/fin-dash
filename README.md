# Fin Dash

A personal finance tracker with the soul of a vintage dashboard. Track your spending across a cluster of analog gauges, import transactions by CSV, and watch/manage your budget dashboard. Built with FastAPI, and React.

Live demo: https://fin-dash-web.onrender.com

Log in with:
- **Email:** demo@example.com
- **Password:** password

> Quick note: the dashboard load may take ~30–60s to wake up. Give it a moment.

## Stack

FastAPI, SQLAlchemy, SQLite, React (Vite), Recharts, JWT auth, Docker, Render.

## Run locally

```
docker compose up --build
```

App at http://localhost:3000, API at http://localhost:8000. Log in with `demo@example.com` / `password`.

## Tests

```
cd backend && pytest
```

## API

```
POST   /auth/login          issue a JWT
GET    /health              liveness check
GET    /transactions        list with filters + pagination
POST   /transactions        create a transaction
GET    /transactions/{id}   fetch one
PUT    /transactions/{id}   update one
DELETE /transactions/{id}   delete one
POST   /ingest/csv          bulk CSV import (auto-categorized, deduped)
GET    /summary             spend by category, monthly totals, budget vs actual
```

## Deployment

Deployed on Render from `render.yaml` — two services: `fin-dash-api` (Docker) and `fin-dash-web` (static site).
