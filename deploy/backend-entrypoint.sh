#!/bin/sh
set -eu

if [ -z "${DATABASE_URL:-}" ]; then
    export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}"
fi

python manage.py migrate --noinput
exec "$@"
