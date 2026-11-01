# Deploy to Render without a credit card

This repository includes `render.yaml`, which creates one Docker web service
for the frontend and Django backend plus one PostgreSQL database.

1. Push this repository to GitHub.
2. Create a free Render account and connect GitHub; Render does not require a
   payment method for the free web-service flow.
3. In Render, choose **New** → **Blueprint** and select this repository.
4. Confirm the `dasher` service and `dasher-db` database, then create the
   Blueprint instance.
5. Open the generated `https://dasher-<suffix>.onrender.com` URL after the
   build completes.

The service applies Django migrations when it starts and generates a secret
key automatically. The free backend sleeps after inactivity, so the first
request after 15 minutes can take about a minute.

## Important data limit

Render's free PostgreSQL database has a 1 GB limit and expires after 30 days.
Download a backup before then if you need to preserve its data:

```bash
pg_dump "$DATABASE_URL" > dasher-backup.sql
```

For a permanent database, later move `DATABASE_URL` to a paid or self-hosted
PostgreSQL server; no application-code change is required.
