#!/usr/bin/env bash
# Usage: set DATABASE_URL env var, then run this script from project root
# Example:
# export DATABASE_URL="postgresql://postgres:password@db.bjarijdscgstpswuttni.supabase.co:5432/postgres"
# ./backend/scripts/migrate_to_supabase.sh

set -euo pipefail

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is not set. Export it first and retry."
  exit 1
fi

echo "Installing migrations and applying to Supabase..."
PYTHONPATH=backend ./venv/bin/python backend/manage.py migrate --no-input

echo "Loading data from backend/all_data.json (if exists)..."
if [ -f backend/all_data.json ]; then
  PYTHONPATH=backend ./venv/bin/python backend/manage.py loaddata backend/all_data.json
else
  echo "No backend/all_data.json found. Create one with dumpdata first." 
fi

echo "Done. Run the app with DATABASE_URL exported to test against Supabase."
