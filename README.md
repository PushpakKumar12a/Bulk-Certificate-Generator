# Bulk Certificate Generator

Backend API for submitting bulk certificate-generation jobs, tracking their
progress, and retrieving generated certificates.

## Implementation decisions

- **Framework:** FastAPI is the planned API framework.
- **Database:** Hosted PostgreSQL is the relational database.
- **Queue:** Hosted Redis is the broker/backend for Celery background jobs.
- **Certificate format:** PDF certificates are rendered from the single
  predefined HTML/CSS template using WeasyPrint.
- **Input:** `POST /jobs` accepts one CSV file containing the recipient list
  plus certificate-level form fields.
- **Processing:** Jobs are processed asynchronously so the request returns
  quickly for large batches and the client can track progress.
- **Template:** Every certificate uses one predefined template; a template
  editor and multiple designs are intentionally out of scope.
- **Failure isolation:** Each recipient is processed independently. A
  generation failure is recorded for that recipient without preventing other
  valid recipients from completing.
- **Persistence:** A relational database stores jobs, recipients, statuses,
  and result metadata. Certificate files are stored separately through a
  storage interface.

## Project structure

```text
bulk-certificate-generator/
├── app/
│   ├── __init__.py
│   ├── core/
│   │   └── config.py      # Environment settings
│   ├── db/
│   │   ├── models.py      # SQLAlchemy database models
│   │   ├── repo.py        # Database queries
│   │   └── session.py     # Async PostgreSQL session
│   ├── jobs/
│   │   ├── csv.py         # CSV parsing and validation
│   │   ├── routes.py      # Job upload endpoint
│   │   └── schemas.py     # Job and recipient schemas
│   ├── certificates/
│   │   ├── routes.py      # Authorized certificate download
│   │   ├── service.py     # Per-recipient generation and failure isolation
│   │   ├── storage.py     # Private local filesystem storage
│   │   └── template.py    # Predefined HTML/CSS and PDF rendering
│   └── main.py            # FastAPI application
├── alembic/
│   ├── env.py             # Migration configuration
│   ├── script.py.mako     # Migration template
│   └── versions/
│       └── create_tables.py
├── tests/
│   ├── test_csv.py
│   ├── test_health.py
│   └── test_models.py
├── storage/               # Local generated PDFs, ignored by Git
├── .env.example           # Safe environment template
├── .env.local             # Local secrets, ignored by Git
├── alembic.ini
├── main.py
├── pyproject.toml
└── uv.lock
```

## Setup

### Requirements

- Python 3.12 or newer
- Hosted PostgreSQL
- Hosted Redis
- Local filesystem storage
- WeasyPrint and its platform-specific rendering dependencies
- [uv](https://docs.astral.sh/uv/)

### Install

```powershell
uv sync --dev
```

Copy `.env.example` to `.env` and replace the placeholder service values:

```powershell
Copy-Item .env.example .env
```

WeasyPrint renders the predefined HTML/CSS certificate template to PDF. Follow
the WeasyPrint installation instructions for the target operating system if
native rendering libraries are required.

Create the local environment configuration from the project template and set
the hosted PostgreSQL, Redis, and storage values before starting the
application. Never commit secrets or production credentials.

Example configuration:

```env
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<postgres-host>:5432/<database>
REDIS_URL=rediss://default:<password>@<redis-host>:6379
STORAGE_PATH=storage
```

Generated certificates are stored in the local `storage/` directory. The
storage interface remains separate from the API and worker so a third-party
provider can be added later without changing certificate-generation logic.
Generated certificates should use generated storage keys; never use a
user-supplied filename or path.

## Certificate generation and retrieval

Certificates are rendered as PDFs from the predefined template and stored
under `STORAGE_PATH`, which is not mounted as a static web directory. Each
certificate receives a UUID and a generated key of the form
`certificates/{job_id}/{certificate_id}.pdf`. Downloads must use the scoped
endpoint `GET /jobs/{job_id}/certificates/{certificate_id}`; the job and
certificate relationship is checked before the file is streamed. Invalid,
missing, or failed certificate results return a safe not-found response.

## Run the application

Apply database migrations, then start the API and background worker:

```powershell
uv run uvicorn app.main:app --reload
uv run celery -A app.worker.celery_app worker --loglevel=INFO
```

The API entry point is `app.main:app`. Verify the API foundation with:

```powershell
uv run uvicorn app.main:app --reload
```

The API exposes `/health` and interactive OpenAPI documentation at `/docs`.
Run migrations using the configured migration tool once the database phase is
implemented. For example:

```powershell
uv run alembic upgrade head
```

The API should expose interactive OpenAPI documentation at `/docs` when
running locally.

## Run tests

Run the complete test suite with:

```powershell
uv run python -m pytest
```

The test suite covers health checks, CSV validation, certificate generation,
job status/progress, and storage behavior.

## Phase 2 database

Set `DATABASE_URL`, then run the first migration:

```powershell
uv run alembic upgrade head
```

Phase 2 stores jobs, recipients, and generated certificate file keys in
PostgreSQL. PDF files remain in the local `storage/` directory.

## Background processing and job status

Job creation queues `jobs.process` in Celery and returns immediately. Start a
worker with:

```powershell
uv run celery -A app.worker.celery_app:celery_app worker --loglevel=INFO
```

Poll `GET /jobs/{job_id}` for the job state, progress counters, and
per-recipient results. A retry skips recipients that already have completed
certificates, so worker retries do not create duplicate results.

## Authentication and limits

Job and certificate endpoints require `X-API-Key`. Configure identities with
the `API_KEYS` environment variable using comma-separated
`key:user:scope|scope` entries, for example:

```env
API_KEYS=replace-me:team-a:jobs:write|jobs:read|certificates:read
```

Jobs are owned by the authenticated user and cannot be read or downloaded by
another identity. Requests are rate-limited per client and endpoint, and each
user has a configurable job quota through `MAX_JOBS_PER_USER`.
In production, HTTP requests are redirected to HTTPS, security headers are
added to responses, and `WORKER_CONCURRENCY` caps parallel certificate jobs.

## Database portability and backups

Phase 8 operations use a database-neutral JSON export containing jobs,
recipients, and certificate references. The export validator checks all
foreign-key references and rejects unsafe storage keys before import.
`backup_storage` creates a ZIP archive with a SHA-256 manifest; restoration
verifies every checksum before copying files, preserving certificate keys.

Before a cutover:

1. Stop job creation and drain the worker queue.
2. Export and validate domain records.
3. Back up `STORAGE_PATH` and verify its manifest.
4. Provision the target database with `uv run alembic upgrade head`.
5. Import records, then compare certificate references with restored files.

Keep the source database and storage archive until verification succeeds.
Rollback is to stop traffic, restore the prior database snapshot, and restore
the storage archive to the original `STORAGE_PATH`.

## Observability and operations

Use `/health` for a process liveness check and `/ready` for dependency
configuration status. `/metrics` exposes request counters suitable for
scraping or forwarding to an operations system. Responses include
`X-Request-ID` and `X-Response-Time-Ms` headers for request tracing.
Application logs are emitted as JSON and intentionally exclude API keys,
uploaded rows, and certificate contents.

For production operations, run the complete test suite before deployment,
apply migrations with `uv run alembic upgrade head`, and retain the database
and storage backup until a restore verification succeeds.

## CSV upload

Create a job with a CSV file and certificate details:

```powershell
curl.exe -X POST http://127.0.0.1:8000/jobs `
  -F "title=Certificate of Completion" `
  -F "course=Python Basics" `
  -F "org=Acme Learning" `
  -F "issue_date=2026-10-07" `
  -F "recipients_file=@recipients.csv"
```

The CSV must contain `full_name`. It may also contain `email` and
`certificate_number`. The API validates UTF-8 encoding, row count, field
lengths, email format, duplicate certificate numbers, and empty files before
creating a queued job.

## API architecture

The API is designed around asynchronous job processing. A request creates a
job and returns its identifier immediately; individual recipients are then
processed independently so one certificate failure does not stop the rest of
the batch.

```mermaid
flowchart LR
    Client[API Client]

    subgraph API[Certificate API]
        Create["POST /jobs<br/>(multipart CSV upload)"]
        Status["GET /jobs/{job_id}"]
        Download["GET /jobs/{job_id}/certificates/{certificate_id}"]
        Validate[Request and recipient validation]
    end

    subgraph Processing[Bulk processing]
        Queue[(Hosted Redis)]
        Worker[Celery worker]
        Template[Predefined certificate template]
        Generator[WeasyPrint PDF generator]
    end

    subgraph Persistence[Persistence]
        Repository[Repository interfaces]
        Adapter[Database adapter]
        DB[(Hosted PostgreSQL)]
        Migrations[Versioned schema migrations]
        Files[(Certificate file storage)]
    end

    Client --> Create
    Client --> Status
    Client --> Download

    Create --> Validate
    Validate -->|accepted| Repository
    Validate -->|job id| Create
    Repository --> Adapter
    Adapter --> DB
    Migrations --> DB
    Repository --> Queue
    Queue --> Worker
    Worker --> Generator
    Template --> Generator
    Generator -->|success or failure per recipient| Repository
    Generator -->|generated file| Files

    Status --> DB
    Download --> DB
    Download --> Files
```

The API publishes jobs to hosted Redis through Celery. A Celery worker
consumes each job, renders the predefined HTML/CSS template with WeasyPrint,
records per-recipient results in PostgreSQL, and writes generated PDFs to the
private local `storage/` directory.

### CSV upload input

The client provides the recipient list as a CSV file using a multipart
`POST /jobs` request. Certificate-level fields are sent as form fields, while
the `recipients_file` field contains the CSV upload.

```http
POST /jobs
Authorization: Bearer <access-token>
Content-Type: multipart/form-data
```

Example form fields:

```text
certificate_title=Certificate of Completion
course_name=Advanced Python Programming
organization_name=Acme Learning
issue_date=2026-10-07
recipients_file=recipients.csv
```

The CSV must contain a header row with these columns:

```csv
full_name,email,certificate_number
Aarav Sharma,aarav.sharma@example.com,PY-2026-0001
Priya Patel,priya.patel@example.com,PY-2026-0002
```

`full_name` is required. `email` and `certificate_number` are recommended,
and certificate numbers must be unique within a job when provided. The API
should validate the file type, encoding, headers, row count, field lengths,
email values, duplicate rows, and configured file-size and recipient-count
limits before placing the job on the queue. Invalid rows should be reported
with row numbers; valid rows may continue processing according to the job
validation policy.

The endpoint returns a job identifier immediately:

```json
{
  "job_id": "0f7f9f7b-ef37-4e7a-8845-f3b4a8c7a9c1",
  "status": "queued",
  "total_recipients": 2,
  "status_url": "/jobs/0f7f9f7b-ef37-4e7a-8845-f3b4a8c7a9c1"
}
```

### Request flow

1. The client submits certificate metadata and a CSV file to `POST /jobs`.
2. The API validates the form fields and parses the CSV, creates a job record,
   and queues the work.
3. A background worker generates certificates independently for each valid
   recipient using the predefined template.
4. The worker records each recipient's success or failure and updates job
   progress in the relational database.
5. The client polls `GET /jobs/{job_id}` for progress and uses the certificate
   download endpoint for successful outputs.

## Retrieve generated certificates

Poll the returned status URL:

```http
GET /jobs/{job_id}
Authorization: Bearer <access-token>
```

The response should include the job status, total, completed, successful, and
failed counts, plus per-recipient results. Successful results include the
certificate download endpoint:

```json
{
  "job_id": "0f7f9f7b-ef37-4e7a-8845-f3b4a8c7a9c1",
  "status": "completed",
  "total_recipients": 2,
  "successful": 1,
  "failed": 1,
  "results": [
    {
      "certificate_number": "PY-2026-0001",
      "status": "completed",
      "certificate_id": "certificate-id-1"
    },
    {
      "certificate_number": "PY-2026-0002",
      "status": "failed",
      "error_code": "GENERATION_FAILED"
    }
  ]
}
```

```http
GET /jobs/{job_id}/certificates/{certificate_id}
Authorization: Bearer <access-token>
```

Only successfully generated certificates are downloadable. Failed recipients
remain visible in the job result with a safe error code and message.

## Database portability and migrations

Database access should remain behind the repository interfaces and a
database-adapter boundary. API handlers and background workers must not contain
database-specific SQL or depend directly on a database driver's types. This
allows the adapter to be replaced when moving between supported relational
databases without changing the API or certificate-generation code.

The schema should be managed using versioned migrations rather than manual
database changes. Each migration must be repeatable in a fresh environment and
must include a rollback strategy where the migration tool supports it. Keep
these concerns separate:

- **Domain data:** jobs, recipients, and per-recipient generation results are
  stored through repositories.
- **Generated files:** certificate binaries are stored in the private local
  filesystem;
  the database stores only their stable storage key and metadata.
- **Schema history:** migration metadata records which schema versions have
  been applied.

### Moving to another database

1. Provision the target relational database.
2. Run the complete migration history against the target.
3. Export the domain tables from the source and import them through a
   database-neutral data migration or the repository layer.
4. Copy the local certificate files and preserve their storage keys.
5. Configure the new database connection and storage location.
6. Run consistency checks for job counts, recipient results, and file keys
   before switching API traffic.

Using stable UUIDs for job and certificate identifiers, ISO-8601 timestamps,
explicit status values, and portable column types further reduces vendor
coupling during a migration.