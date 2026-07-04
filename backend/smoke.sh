#!/usr/bin/env bash
set -euo pipefail

BASE="http://127.0.0.1:8000"
DB="finance.db"
RESET=false
[[ "${1:-}" == "--reset" ]] && RESET=true

# small helper to curl and capture status+body
call() {
  local method="$1"; shift
  local url="$1"; shift
  local data="${1:-}"
  if [[ -n "$data" ]]; then
    resp=$(curl -sS -w "\n%{http_code}" -X "$method" "$url" -H "Content-Type: application/json" -d "$data")
  else
    resp=$(curl -sS -w "\n%{http_code}" -X "$method" "$url")
  fi
  body=$(printf "%s" "$resp" | sed '$d')
  code=$(printf "%s" "$resp" | tail -n1)
  echo "$code" "$body"
}

if $RESET; then
  echo "🔄 Resetting DB..."
  rm -f "$DB"
  python - <<'PY'
from db import Base, engine
Base.metadata.create_all(bind=engine)
print("✅ DB reset & tables created.")
PY
fi

# Health
read -r code body < <(call GET "$BASE/health")
echo "✅ Health:"; echo "$body"
[[ "$code" == "200" ]] || { echo "Health failed ($code)"; exit 1; }

# Create
echo "➕ Create:"
payload='{"date":"2025-08-09","amount":-8.75,"merchant":"Chipotle","category":"Dining","subcategory":"Fast Food","notes":"bowl"}'
read -r code body < <(call POST "$BASE/transactions" "$payload")
echo "$body"
[[ "$code" == "200" ]] || { echo "Create failed ($code)"; exit 1; }

# List
echo "📄 List:"
read -r code body < <(call GET "$BASE/transactions?limit=5&order=date_desc")
echo "$body"
[[ "$code" == "200" ]] || { echo "List failed ($code)"; exit 1; }

# Extract ID safely (in case of unexpected shape)
ID=$(python3 - <<'PY'
import sys, json
try:
    arr=json.load(sys.stdin)
    if isinstance(arr, list) and arr:
        print(arr[0]["id"])
except Exception:
    pass
PY <<< "$body")
if [[ -z "${ID:-}" ]]; then
  echo "Could not parse ID from list; stopping early."
  exit 1
fi

# Get / Update / Delete
echo "🔎 Get $ID:"
read -r code body < <(call GET "$BASE/transactions/$ID"); echo "$body"
echo "✏️ Update $ID:"
read -r code body < <(call PUT "$BASE/transactions/$ID" '{"notes":"updated"}'); echo "$body"
echo "🗑️ Delete $ID:"
read -r code body < <(call DELETE "$BASE/transactions/$ID"); echo "$body"

echo "✅ Done."
