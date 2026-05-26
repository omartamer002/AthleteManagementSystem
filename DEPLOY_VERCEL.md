Quick Vercel deployment steps for this monorepo

Overview
- Frontend: static site built by `gulp build` into `dist` (configured in `package.json`).
- Backend: Django app located in `backend/` exposing WSGI/ASGI at `backend/ams_core/wsgi.py` (already wired in `vercel.json`).

Prerequisites
- A Vercel account with the Git repository connected.
- A production Postgres database (e.g. Supabase) — do not use the bundled `db.sqlite3` in production.

Vercel project setup
1. Import this repository into Vercel (select the repository and root).
2. Vercel will use `vercel.json` (already present). The important parts:
   - Python build: `backend/ams_core/wsgi.py` uses `@vercel/python` (runtime `python3.12`).
   - Static build: `package.json` with `vercel-build` script runs `gulp build` and outputs `dist`.
3. In Vercel > Settings > Environment Variables, add:
   - `DATABASE_URL` = Postgres connection URL (e.g. `postgres://user:pass@host:5432/dbname`).
   - `SECRET_KEY` = Django secret key (random long string).
   - `DEBUG` = `False`
   - Any other keys used by your app (e.g. `GEMINI_API_KEY`, Supabase keys, etc.).

Database & migrations
- The app uses `dj_database_url` to pick up `DATABASE_URL`. Point it to a managed Postgres instance (Supabase, Render DB, AWS RDS, etc.).
- Run Django migrations once against the production DB from your local machine or CI:

```bash
# from repo root
python -m pip install -r backend/requirements.txt
python backend/manage.py migrate --settings=ams_core.settings
``` 

Static files
- WhiteNoise is configured in `settings.py` so static files can be served by the Django app. The frontend assets are also built into `dist` and served by the static build.

Notes & caveats
- The Python serverless environment has size limits for dependencies. The repository's `requirements.txt` is large and may hit Vercel limits. If you run into build failures due to size, consider:
  - Deploying the backend to a dedicated service (Render, DigitalOcean App Platform, Heroku, or Railway) and keeping the frontend on Vercel.
  - Slimming dependencies (only install what's needed in production).
- The repo includes `db.sqlite3` for local dev — this will not persist on Vercel. Use a managed Postgres DB.

CI / automatic migrations
- A GitHub Actions workflow (`.github/workflows/vercel_migrate.yml`) has been added to run migrations on push to `main` and optionally trigger a Vercel deploy.
- Add the following GitHub repository secrets: `DATABASE_URL`, `SECRET_KEY`. Optionally add `VERCEL_TOKEN`, `VERCEL_ORG_ID`, and `VERCEL_PROJECT_ID` to let the workflow trigger a Vercel production deploy.

Production requirements and CI
- I replaced `backend/requirements.txt` with a trimmed production set to reduce Vercel build size, and saved the original full list to `backend/requirements-full.txt`.
- For CI and Vercel builds the project will run:

```bash
pip install -r backend/requirements.txt
python backend/manage.py collectstatic --noinput
```

If you need the full development requirements later, see `backend/requirements-full.txt`.

Local testing
- Frontend build:

```bash
npm install
npm run vercel-build
# ./dist will contain the built site
```

- Backend testing:

```bash
python -m pip install -r backend/requirements.txt
python backend/manage.py runserver
```

If you want, I can:
- Add a small deployment checklist to this repo and mark steps done.
- Help set up a Supabase database and generate a `DATABASE_URL`.
- Trim `requirements.txt` for Vercel compatibility.
