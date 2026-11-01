# Build the static frontend once, then serve it through Caddy.
FROM node:22-bookworm-slim AS frontend-build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . ./
RUN npm run vercel-build

# Django API image.
FROM python:3.12-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend-build /app/dist /app/dist
RUN python manage.py collectstatic --noinput
COPY deploy/backend-entrypoint.sh /usr/local/bin/backend-entrypoint
RUN chmod +x /usr/local/bin/backend-entrypoint
ENTRYPOINT ["backend-entrypoint"]
CMD ["gunicorn", "ams_core.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-"]

# HTTPS reverse proxy and static frontend image.
FROM caddy:2-alpine AS web
COPY --from=frontend-build /app/dist /srv/frontend
COPY deploy/Caddyfile /etc/caddy/Caddyfile

# Render builds the final Docker stage and serves both the static frontend and
# Django API from one web service, keeping relative /api URLs working.
FROM backend AS render
