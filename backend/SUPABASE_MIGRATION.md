Steps to migrate the Django app from local SQLite -> Supabase (Postgres)

1. Create a Supabase project and database (you've created project id: bjarijdscgstpswuttni).
2. Get the full `DATABASE_URL` from Supabase (Settings → Database → Connection string).
3. On your machine, export the variable in the shell or create `backend/.env`:

   export DATABASE_URL="postgresql://postgres:<password>@db.bjarijdscgstpswuttni.supabase.co:5432/postgres"

4. (Optional) Securely add your Django `SECRET_KEY` and any other env vars into `backend/.env`.
5. Install the Postgres driver (already added to `backend/requirements.txt`):

   ./venv/bin/pip install -r backend/requirements.txt

6. Dump current data (already done here):

   PYTHONPATH=backend ./venv/bin/python backend/manage.py dumpdata --natural-primary --natural-foreign --indent 2 > backend/all_data.json

7. Apply migrations and load data:

   ./backend/scripts/migrate_to_supabase.sh

8. Run the server to test (with `DATABASE_URL` exported):

   PYTHONPATH=backend ./venv/bin/python backend/manage.py runserver

Notes:
- For large projects, consider using `pg_dump`/`pg_restore` or `pgloader` for better fidelity.
- If you plan to use Supabase Auth or Storage directly from clients, configure RLS rules and keys in the Supabase dashboard.
