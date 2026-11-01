# Deploy on one Oracle Always Free VM

This configuration runs the frontend, Django API, PostgreSQL, and HTTPS proxy
on one server. It does not use Neon or Supabase.

## Before deployment

1. Create an Oracle Cloud Always Free Ubuntu VM and assign it a public IP.
2. Point a domain's DNS `A` record to that public IP. HTTPS needs a domain.
3. In the Oracle cloud firewall and the VM firewall, allow inbound TCP ports 80,
   443, and 22 only. Do not expose port 5432.
4. Install Docker Engine and the Docker Compose plugin on the VM.
5. Clone this repository to the VM.

## Configure and start

```bash
cp .env.production.example .env.production
# Edit .env.production and set DOMAIN, POSTGRES_PASSWORD, and SECRET_KEY.
docker compose up -d --build
```

The backend runs all Django migrations automatically before it starts. Caddy
obtains and renews the TLS certificate after the domain points to the server.

## Useful operations

```bash
docker compose logs -f
docker compose exec backend python manage.py createsuperuser
docker compose exec db pg_dump -U dasher dasher > dasher-backup.sql
docker compose up -d --build
```

Keep off-server backups of `dasher-backup.sql`. The Docker volume retains the
database and uploaded media across ordinary container rebuilds, but it is not a
backup.
