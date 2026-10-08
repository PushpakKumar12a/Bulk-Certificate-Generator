# Bulk Certificate Generator

A high-performance FastAPI backend for asynchronous bulk certificate generation, real-time job tracking, secure PDF downloads, and public certificate authenticity verification.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Core Features](#core-features)
- [Project Structure](#project-structure)
- [Failure Isolation & Resilience](#failure-isolation--resilience)
- [Security & Storage Safety](#security--storage-safety)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Running the Application](#running-the-application)
- [API Reference & Usage](#api-reference--usage)
- [Running Tests](#running-tests)

---

## Overview

Generating hundreds or thousands of personalized PDF certificates synchronously in a web request quickly leads to HTTP timeouts (504 Gateway Timeout), memory exhaustion, and partial batch failures.

**Bulk Certificate Generator** solves this with an asynchronous, distributed pipeline:
1. **FastAPI** validates uploaded recipient CSV files and metadata in milliseconds, returning an immediate `202 Accepted` job tracking ID.
2. **Celery** background workers process certificates asynchronously via a **Redis / Valkey** message broker.
3. **ReportLab** programmatically renders high-resolution, vector-quality PDF certificates without needing heavy headless browsers (like Puppeteer or WeasyPrint).
4. **Per-Recipient Isolation** guarantees that if one row has bad data, the remaining valid certificates generate uninterrupted.
5. **Unified REST API** provides simple endpoints for polling progress, downloading generated PDFs, and publicly verifying authenticity.

---

## Architecture

```mermaid
graph LR
    client[Client / Frontend]
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
    client -->|"GET /certificates/{id}"| api
    client -->|"GET /certificates/{id}/verify"| api
    certs -->|"query metadata"| db
    certs -->|"read PDF"| storage
```

### End-to-End Processing Flow

1. **Submission**: A client submits certificate metadata (title, course, issuing organization, issue date) along with a CSV file of recipients to `POST /jobs`.
2. **Validation**: The API checks file size limits, row limits, and validates CSV structure. It saves the `Job` and all `Recipient` records in PostgreSQL with status `queued`.
3. **Queueing**: A Celery task (`process_job`) is dispatched through Redis/Valkey.
4. **Processing**: The worker updates the job status to `running`, iterates through recipients, generates a ReportLab PDF with custom vector styling and an immutable UUID, and persists the PDF to disk.
5. **Completion**: If all recipients succeed, the job status transitions to `completed`. If any recipient encountered an error, the specific error is logged and the job transitions to `completed_with_errors`.
6. **Retrieval & Verification**: Recipients and clients download PDFs via `GET /certificates/{id}` or verify credentials publicly via `GET /certificates/{id}/verify`.

---

## Core Features

- **Asynchronous Execution**: Decouples CSV uploads from generation to prevent request timeouts.
- **Pure-Python Vector PDFs**: Uses ReportLab for fast, deterministic PDF rendering with Bitstream Vera typography, decorative guilloche borders, dynamic name auto-scaling, and authorized signature lines.
- **Per-Recipient Failure Isolation**: Errors in individual rows are recorded in `recipients.error` without halting the batch.
- **RESTful Endpoints**: Clean, unified URLs without duplicate paths or confusing aliases.
- **Multi-Tenant Scoping**: API key authentication (`X-Api-Key`) ensures users only access their own jobs and recipient lists.
- **Operational Health Probes**: Includes `/health` (liveness) and `/ready` (checks live connectivity to PostgreSQL and Redis).

---

## Project Structure

```text
bulk-certificate-generator/
├── app/
│   ├── certificates/
│   │   ├── routes.py          # Unified download and verification endpoints
│   │   ├── schemas.py         # Verification response Pydantic models
│   │   ├── service.py         # Per-recipient rendering and error handling
│   │   ├── storage.py         # Safe filesystem storage with traversal checks
│   │   └── template.py        # ReportLab vector certificate layout engine
│   ├── core/
│   │   ├── auth.py            # API key authentication & user resolution
│   │   └── config.py          # Pydantic environment settings
│   ├── db/
│   │   ├── models.py          # SQLAlchemy models (Job, Recipient, Certificate)
│   │   ├── repo.py            # Async PostgreSQL database queries
│   │   └── session.py         # Async engine lifecycle & session dependency
│   ├── jobs/
│   │   ├── csv.py             # CSV parsing, sanitization, and validation
│   │   ├── routes.py          # Job creation (CSV upload) & status endpoints
│   │   ├── schemas.py         # Job request & response schemas
│   │   └── status.py          # Progress metrics & recipient result models
│   ├── worker/
│   │   ├── celery_app.py      # Celery broker and backend configuration
│   │   └── tasks.py           # Background batch task worker logic
│   └── main.py                # FastAPI entrypoint, middleware, and health probes
├── alembic/
│   ├── versions/              # Unified database migration scripts (0001)
│   └── env.py                 # Async Alembic migration environment
├── sample-data/
│   └── recipients.csv         # Sample dataset with 50 recipients for testing
├── tests/                     # Test suite (routes, models, certificates, csv)
├── storage/                   # Generated PDF output directory (git-ignored)
├── pyproject.toml             # Project dependencies and tool configurations
└── README.md                  # Complete project documentation
```

---

## Failure Isolation & Resilience

In high-volume batch operations, a single bad record (e.g. invalid characters, storage write failure) should never crash the entire generation process.

```mermaid
stateDiagram-v2
    [*] --> queued: Job registered
    queued --> running: Worker claims batch
    state running {
        Recipient_1 --> Succeeded: PDF rendered and stored
        Recipient_2 --> Failed: Error caught and logged
        Recipient_3 --> Succeeded: PDF rendered and stored
    }
    running --> completed: 100% Succeeded
    running --> completed_with_errors: Some failed, some succeeded
    running --> failed: Entire job crashed
```

* **Individual Catch Blocks**: Each recipient is processed in an isolated `try...except` block in `app/certificates/service.py`.
* **Granular Status Tracking**: When a recipient fails, its status is marked `failed` and the exact exception message is stored in `recipients.error`. The remaining recipients proceed unaffected.
* **Automated Celery Retries**: If any recipient fails due to transient errors or connection issues, Celery automatically retries the job up to 3 times with exponential backoff (`autoretry_for = (ConnectionError, OSError, BatchRetryError)`). On every retry, all previously completed certificates are skipped, attempting only the failed or unrendered rows.
* **Crash Resilience via Late Acknowledgments**: With `task_acks_late = True` and `task_reject_on_worker_lost = True`, if a worker process terminates abruptly midway through a batch, the task is rejected back to the broker and resumed from where it left off.
* **Deterministic Job Statuses**:
  * `queued`: Job created, awaiting Celery worker pickup.
  * `running`: Actively processing recipient rows.
  * `completed`: All certificates generated successfully.
  * `completed_with_errors`: Finished with a mix of successful and failed certificates after all retries are exhausted.
  * `failed`: Critical task-level failure (e.g. database unreachable after all retries).

---

## Security & Storage Safety

- **Path Traversal Protection**: `app/certificates/storage.py` resolves and verifies all file paths against the base storage directory. Attempting to pass keys like `../../etc/passwd` or absolute drive paths raises a `ValueError("invalid storage key")`.
- **API Key Scoping**: Administrative endpoints (`POST /jobs` and `GET /jobs/{id}`) require an `X-Api-Key` header. Jobs are scoped to the authenticated user ID (`owner`), preventing unauthorized users from accessing or monitoring other tenants' jobs.
- **Public Credential Verification**: The verification endpoint (`GET /certificates/{id}/verify`) and download endpoint (`GET /certificates/{id}`) are publicly accessible without an API key, allowing third-party employers, verifiers, and recipients to view and validate issued certificates seamlessly.

---

## Prerequisites

- **Python**: 3.12 or newer
- **Package Manager**: [uv](https://docs.astral.sh/uv/) (Astral)
- **PostgreSQL**: Running on `localhost:5432`, database `certificates`
- **Redis / Valkey**: Running on `localhost:6380` (or `6379`)

---

## Setup & Installation

### 1. Install Dependencies

Using `uv`, install all required and development dependencies into a local virtual environment:

```powershell
uv sync --dev
```

### 2. Configure Environment Variables

Create `.env.local` from the example template:

```powershell
Copy-Item .env.example .env.local
```

Verify or update connection strings in `.env.local`:

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

> **Note**: `API_KEYS` is a comma-separated list of `api_key:user_id` pairs.

### 3. Run Database Migrations

Apply the initial unified database schema:

```powershell
uv run alembic upgrade head
```

---

## Running the Application

To run the application locally, start each service in a separate terminal:

1. **Terminal 1 &ndash; Message Broker (Redis / Valkey)**:
   Ensure your Redis or Valkey instance is running on port `6380`.

2. **Terminal 2 &ndash; Celery Background Worker**:
   ```powershell
   uv run celery -A app.worker.celery_app worker --loglevel=INFO -P solo
   ```
   > **Note**: On Windows, `-P solo` is required to avoid POSIX fork conflicts with `asyncpg` and asyncio event loops.

3. **Terminal 3 &ndash; FastAPI Web Server**:
   ```powershell
   uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

Interactive Swagger documentation is available at **<http://127.0.0.1:8000/docs>** once the web service is running.

---

## API Reference & Usage

### 1. Submit a Generation Job

Upload a recipient CSV file and initiate background certificate rendering:

```powershell
curl.exe -X POST http://127.0.0.1:8000/jobs `
  -H "X-Api-Key: local-dev-key" `
  -F "title=Certificate of Completion" `
  -F "course=DevOps & Cloud Engineering" `
  -F "org=Cloud Academy" `
  -F "issue_date=2026-10-08" `
  -F "recipients_file=@sample-data/recipients.csv"
```

**CSV Format** (Requires `full_name`, optional `email`):
```csv
full_name,email
Aarav Sharma,aarav.sharma@example.com
Ananya Patel,ananya.patel@example.com
```

**Response (`202 Accepted`)**:
```json
{
  "job_id": "91e68292-8ef2-4fe9-9def-0f7a138c9d5c",
  "status": "queued",
  "total": 50,
  "status_url": "/jobs/91e68292-8ef2-4fe9-9def-0f7a138c9d5c"
}
```

---

### 2. Poll Job Status & Results

Check progress metrics and retrieve generated certificate IDs:

```powershell
curl.exe http://127.0.0.1:8000/jobs/91e68292-8ef2-4fe9-9def-0f7a138c9d5c `
  -H "X-Api-Key: local-dev-key"
```

**Response (`200 OK`)**:
```json
{
  "job_id": "91e68292-8ef2-4fe9-9def-0f7a138c9d5c",
  "status": "completed",
  "total": 50,
  "done": 50,
  "success": 50,
  "failed": 0,
  "results": [
    {
      "row": 2,
      "name": "Dev Mishra",
      "status": "completed",
      "error": null,
      "certificate_id": "d0dc9cdc-b4af-4ecb-81c8-9f71494f0aad",
      "download_url": "/certificates/d0dc9cdc-b4af-4ecb-81c8-9f71494f0aad",
      "verification_url": "/certificates/d0dc9cdc-b4af-4ecb-81c8-9f71494f0aad/verify"
    }
  ]
}
```

---

### 3. Download Certificate PDF

Download the rendered PDF file directly using the certificate ID:

```powershell
curl.exe -L http://127.0.0.1:8000/certificates/d0dc9cdc-b4af-4ecb-81c8-9f71494f0aad `
  --output certificate.pdf
```

---

### 4. Verify Certificate Authenticity

Publicly verify the authenticity, recipient name, course, and issuance date:

```powershell
curl.exe http://127.0.0.1:8000/certificates/d0dc9cdc-b4af-4ecb-81c8-9f71494f0aad/verify
```

**Response (`200 OK`)**:
```json
{
  "valid": true,
  "certificate_id": "d0dc9cdc-b4af-4ecb-81c8-9f71494f0aad",
  "recipient_name": "Dev Mishra",
  "course": "DevOps & Cloud Engineering",
  "org": "Cloud Academy",
  "issue_date": "2026-10-08",
  "issued_at": "2026-10-08T12:20:42.202914Z"
}
```

---

### 5. System Health Probes

- **Liveness Probe**: `GET /health` &ndash; Confirms the FastAPI process is active.
- **Readiness Probe**: `GET /ready` &ndash; Checks active connection pools to PostgreSQL and Redis.

---

## Running Tests

Execute the automated test suite with `pytest`:

```powershell
uv run pytest
```

Test coverage includes:
- **Routes & Authentication**: Header enforcement, 401 unauthorized handling, 404 error responses, and verification serialization.
- **Storage Protection**: Directory traversal and absolute path rejection (`../`, `..\`, `/outside.pdf`).
- **CSV Parser**: Size bounds, row limits, missing columns, and header stripping.
- **Models**: Database constraints, cascade deletions, and status enum transitions.