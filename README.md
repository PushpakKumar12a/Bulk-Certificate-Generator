# Bulk Certificate Generator

A FastAPI backend for submitting bulk certificate-generation jobs, tracking background progress, downloading generated PDFs, and publicly verifying certificate authenticity.

## Architecture

```mermaid
graph LR
    client[Client]
    api[FastAPI API<br/>app.main]
    jobs[Job routes<br/>CSV validation & status]
    certs[Certificate routes<br/>download & verification]
    db[(PostgreSQL<br/>jobs, recipients, certificates)]
    broker[(Redis / Valkey<br/>Celery broker & backend)]
    worker[Celery worker<br/>app.worker.tasks]
    service[Certificate service<br/>per-recipient isolation]
    pdf[ReportLab<br/>PDF renderer]
    storage[(Certificate storage<br/>storage/*.pdf)]

    client -->|"POST /jobs + CSV"| api
    api --> jobs
    api --> certs
    jobs -->|"create job and recipients"| db
    jobs -->|"enqueue process_job"| broker
    broker -->|"consume task"| worker
    worker -->|"read/update job state"| db
    worker --> service
    service --> pdf
    service -->|"save generated PDF"| storage
    service -->|"persist certificate metadata"| db
    client -->|"GET /jobs/{id}"| api
    client -->|"GET /verify/{certificate_id}"| api
    client -->|"GET /certificates/{certificate_id}"| api
    certs -->|"query metadata"| db
    certs -->|"read PDF"| storage
```

### Processing flow

1. A client uploads certificate metadata and a recipient CSV to `POST /jobs`.
2. The API validates the CSV, creates the job and recipient records in PostgreSQL, and publishes a Celery task through Redis/Valkey.
3. A worker processes recipients independently. Each successful recipient gets a UUID, a generated ReportLab PDF, and a certificate record.
4. The worker updates job progress after each batch. A single recipient failure is recorded without stopping the rest of the job.
5. Clients poll the job status endpoint, download PDFs, or verify certificate IDs publicly.

### Design decisions

- **FastAPI:** Async HTTP handling with generated OpenAPI documentation at `/docs`.
- **Celery + Redis/Valkey:** Background processing keeps bulk generation out of the request path.
- **PostgreSQL + SQLAlchemy:** Durable job, recipient, and certificate metadata.
- **ReportLab:** Deterministic PDF rendering without browser or system-binary dependencies.
- **UUID certificate IDs:** Each generated certificate receives a unique, immutable, verifiable identifier.
- **Filesystem storage:** Generated PDFs are stored locally by default behind the `CertificateStorage` abstraction.
- **Failure isolation:** Recipient-level errors are persisted and do not fail the entire batch.

## Project structure

```text
bulk-certificate-generator/
├── app/
│   ├── certificates/
│   │   ├── routes.py          # Download and verification endpoints
│   │   ├── schemas.py         # Verification response models
│   │   ├── service.py         # Per-recipient generation and isolation
│   │   ├── storage.py         # Safe local certificate storage
│   │   └── template.py         # ReportLab PDF template
│   ├── core/
│   │   ├── auth.py            # API-key/current-user resolution
│   │   └── config.py          # Environment-backed settings
│   ├── db/
│   │   ├── models.py          # Job, recipient, and certificate models
│   │   ├── repo.py            # Async database queries
│   │   └── session.py         # Async engine and session management
│   ├── jobs/
│   │   ├── csv.py             # CSV parsing and validation
│   │   ├── routes.py          # Job creation and status endpoints
│   │   ├── schemas.py         # Job request/response models
│   │   └── status.py          # Progress and recipient result models
│   ├── worker/
│   │   ├── celery_app.py      # Celery broker/backend setup
│   │   └── tasks.py           # Background batch processing
│   └── main.py                # FastAPI application entry point
├── alembic/
│   ├── versions/              # Database migrations
│   └── env.py                 # Alembic configuration
├── sample-data/
│   └── recipients.csv         # Example recipient input
├── tests/                     # API, model, service, and status tests
├── storage/                   # Generated PDFs (git-ignored)
├── pyproject.toml             # Project and development dependencies
└── README.md
```

## Prerequisites

- **Python:** 3.12 or newer
- **Package manager:** [uv](https://docs.astral.sh/uv/)
- **PostgreSQL:** `localhost:5432`, database `certificates`
- **Redis/Valkey:** `localhost:6380` (or another configured Redis-compatible endpoint)

## Setup

### 1. Install dependencies

```powershell
uv sync --dev
```

### 2. Configure the environment

Copy `.env.example` to `.env.local` for local development. The included

```powershell
Copy-Item .env.example .env.local
```

Update the connection settings for local services:

```env
APP_NAME=Bulk Certificate Generator
ENVIRONMENT=development
DATABASE_URL=postgresql+asyncpg://postgres:root@localhost:5432/certificates
REDIS_URL=redis://localhost:6380
STORAGE_PATH=storage
MAX_CSV_BYTES=5000000
MAX_ROWS=10000
API_KEYS=local-dev-key:local-user
```

`API_KEYS` is a comma-separated list of `key:user_id` pairs. Use a
non-placeholder key outside local development and do not commit `.env.local`.

### 3. Apply database migrations

```powershell
uv run alembic upgrade head
```

## Run locally

Start the API:

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

In a separate terminal, start the Celery worker:

```powershell
uv run celery -A app.worker.celery_app worker --loglevel=INFO -P solo
```

On Windows, `-P solo` keeps the worker process compatible with the local async database setup.

The interactive API documentation is available at <http://127.0.0.1:8000/docs>.


```powershell
```

The API is available at <http://127.0.0.1:8000>. Run migrations from an application container or from a local environment configured to reach the Compose PostgreSQL service:

```powershell
uv run alembic upgrade head
```

## Tests

```powershell
uv run pytest
```

## API usage

### Submit a generation job

Job creation, job status, and certificate downloads require the `X-Api-Key`
header. The examples below use the local-development key from `.env.local`.

```powershell
curl.exe -X POST http://127.0.0.1:8000/jobs `
  -H "X-Api-Key: local-dev-key" `
  -F "title=Certificate of Completion" `
  -F "course=DevOps & Cloud Engineering" `
  -F "org=Cloud Academy" `
  -F "issue_date=2026-10-07" `
  -F "recipients_file=@sample-data/recipients.csv"
```

The CSV must contain a `full_name` column. An optional `email` column is accepted:

```csv
full_name,email
Aarav Sharma,aarav.sharma@example.com
Ananya Patel,ananya.patel@example.com
```

The API returns `202 Accepted` with a job ID and status URL:

```json
{
  "job_id": "27f914f7-72cf-4371-be96-19ea869953bb",
  "status": "queued",
  "total": 50,
  "status_url": "/jobs/27f914f7-72cf-4371-be96-19ea869953bb"
}
```

### Check job progress

```powershell
curl.exe http://127.0.0.1:8000/jobs/27f914f7-72cf-4371-be96-19ea869953bb `
  -H "X-Api-Key: local-dev-key"
```

Job statuses are `queued`, `running`, `completed`, `completed_with_errors`, and `failed`. Each recipient result includes its certificate ID and download/verification URLs when generation succeeds.

### Verify a certificate

```powershell
curl.exe http://127.0.0.1:8000/verify/27759b61-fab3-4070-bccd-52c9e3307425
```

Unknown IDs return `404 Not Found`. The alias `/certificates/{certificate_id}/verify` is also available.

### Download a certificate

```powershell
curl.exe -L http://127.0.0.1:8000/certificates/27759b61-fab3-4070-bccd-52c9e3307425 `
  -H "X-Api-Key: local-dev-key" `
  --output certificate.pdf
```

The job-scoped download route `/jobs/{job_id}/certificates/{certificate_id}` is also available.

## Health checks

- **Liveness:** `GET /health` returns the application status and environment.
- **Readiness:** `GET /ready` verifies PostgreSQL and Redis/Valkey connectivity.