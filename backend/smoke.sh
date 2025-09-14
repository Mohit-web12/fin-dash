#!/usr/bin/env bash
set -euo pipefail

BASE="http://127.0.0.1:8000"
DB="finance.db"

RESET=false
[[ "${1:-}" == "--reset" ]] && RESET=true

if $RESET; then
  echo "🔄 Resetting DB..."
  rm -f "$DB"
fi

echo "✅ Health:"; curl -s "$BASE/health"; echo

echo "➕ Create:"
curl -s -X POST "$BASE/transactions" -H "Content-Type: application/json" -d '{
  "date":"2025-08-09","amount":-8.75,"merchant":"Chipotle",
  "category":"Dining","subcategory":"Fast Food","notes":"bowl"
}'; echo

echo "📄 List:"; curl -s "$BASE/transactions?limit=5&order=date_desc"; echo

ID=$(curl -s "$BASE/transactions?limit=1&order=date_desc" | python3 -c 'import sys,json;print(json.load(sys.stdin)[0]["id"])')
echo "🔎 Get $ID:"; curl -s "$BASE/transactions/$ID"; echo
echo "✏️ Update $ID:"; curl -s -X PUT "$BASE/transactions/$ID" -H "Content-Type: application/json" -d '{"notes":"updated"}'; echo
echo "🗑️ Delete $ID:"; curl -s -X DELETE "$BASE/transactions/$ID"; echo

echo "📥 Ingest CSV:"; curl -s -F "file=@sample.csv" "$BASE/ingest/csv"; echo

echo "✅ Done."
