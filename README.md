# Property Revenue Dashboard — debugging submission

The existing dashboard now calculates revenue from PostgreSQL, isolates tenants in queries and caches, reports local calendar months/years, and keeps money exact through the API and UI.

- [Findings, root causes, and verification](docs/INVESTIGATION.md)
- [5–7 minute Loom recording outline](docs/WALKTHROUGH.md)
- [45-second browser verification recording (MP4, silent)](docs/evidence/demo.mp4)
- [Original assignment](ASSIGNMENT.md)

## Run

```sh
docker compose up --build
# Alternatively, use docker-compose with the same arguments.
```

Open http://localhost:3000 and log in using either account in `ASSIGNMENT.md`. The dashboard defaults to March 2024 because that is the supplied sample-data period. The property selector shows only the signed-in tenant's properties. Change the reporting month or select **Show full year**.

The API documentation is at http://localhost:8000/docs. Example report:

```text
GET /api/v1/dashboard/summary?property_id=prop-001&month=3&year=2024
Authorization: Bearer <login access_token>
```

`year=2024` without a month requests the full local calendar year; omitting both returns all-time revenue. `month` requires `year`. Monetary totals are JSON decimal **strings**, e.g. `"2250.00"`.

The supplied credentials and signing secret are development fixtures. Local fixture login is disabled when a Supabase URL is configured.

## Tests

Python 3.11+ is required. Start the database with `docker compose up -d db`, then:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements-dev.txt
cd backend
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5433/propertyflow pytest -q
```

Tests create and drop uniquely named schemas in the selected PostgreSQL database. Use a local/disposable database account with schema creation privileges. Seed data in the existing public schema is untouched. Without `TEST_DATABASE_URL`, database-dependent tests are explicitly skipped; calendar and cache unit tests still run.

A dedicated GitHub Actions workflow runs the regression suite against PostgreSQL 15. To build the frontend locally:

```sh
cd frontend
npm ci
npm run build
```

The upstream snapshot includes generated `node_modules` and `dist` files. They are excluded from Docker build contexts; dependency manifests remain the source of truth. This solution does not commit changes to those generated files.
