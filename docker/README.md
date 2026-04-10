# Local Dev Stack

Run the local PostgreSQL + Redis + FastAPI stack:

```bash
docker compose -f docker/docker-compose.yml up --build
```

Only start infrastructure services:

```bash
docker compose -f docker/docker-compose.yml up -d postgres redis
```

Apply migrations after the database is healthy:

```bash
alembic upgrade head
```
