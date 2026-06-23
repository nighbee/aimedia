# AI Media Watch

> **An intelligent media analysis platform for detecting fraudulent content — illegal gambling, pyramid schemes, investment fraud, and referral schemes in social media videos.**

AI Media Watch is an **end-to-end media forensics pipeline** that ingests social media video URLs (TikTok, Instagram), downloads and analyzes the content through a multi-stage AI processing pipeline, and produces a **risk-scored investigation report** with downloadable evidence packs. Built for fraud investigators, compliance teams, and content moderation analysts.

---

## Table of Contents

- [System Overview](#system-overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Approaches & Patterns](#approaches--patterns)
- [Media Worker Pipeline](#media-worker-pipeline)
- [Frontend (Output)](#frontend-output)
- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Deployment](#deployment)
- [Contributing](#contributing)

---

## System Overview

AI Media Watch is a **microservices-based monorepo** comprising three custom services orchestrated alongside three infrastructure services via Docker Compose. The system follows an **event-driven architecture** where media analysis jobs flow asynchronously through a 6-stage processing pipeline.

**The core workflow:**

1. An **Inspector** (authenticated user) submits a social media video URL through the React frontend
2. The **Go API Gateway** validates the request, persists a job record, and publishes a Kafka event
3. The **Python Media Worker** consumes the event and runs the video through a 6-stage pipeline — downloading, extracting audio/keyframes, transcribing via Soniox STT, analyzing via Gemini AI (two-pass chain), scoring risk, and optionally generating a PDF evidence pack
4. The frontend **polls for progress** and displays the final report with risk scores, category breakdowns, flagged content, and an evidence download link

---

## Architecture

```
┌─────────────┐     ┌──────────┐     ┌──────────────┐
│  React SPA  │────▶│  Nginx   │────▶│  Go API      │
│  (Frontend) │◀────│  (Proxy) │◀────│  Gateway     │
└─────────────┘     └──────────┘     └──────┬───────┘
                                            │
                    ┌───────────────────────┼───────────────────┐
                    │                       │                   │
                    ▼                       ▼                   ▼
            ┌──────────────┐       ┌──────────────┐    ┌──────────────┐
            │  PostgreSQL  │       │    Kafka     │    │    MinIO     │
            │  (Database)  │       │  (Message    │    │  (S3 Storage)│
            │              │       │   Broker)    │    │              │
            └──────────────┘       └──────┬───────┘    └──────────────┘
                                          │
                                          ▼
                                  ┌──────────────┐
                                  │   Python     │
                                  │ Media Worker │
                                  │  (Pipeline)  │
                                  └──────────────┘
                                          │
                          ┌───────────────┼───────────────┐
                          ▼               ▼               ▼
                   ┌────────────┐  ┌────────────┐  ┌────────────┐
                   │ yt-dlp    │  │  Soniox    │  │   Gemini   │
                   │ Download  │  │    STT     │  │ 2.0 Flash  │
                   └────────────┘  └────────────┘  └────────────┘
```

### Service Breakdown

| Service | Language | Role |
|---------|----------|------|
| **React Frontend** | TypeScript / React 19 | User interface — job submission, progress tracking, report viewing |
| **Nginx** | — | Serves static assets, reverse-proxies `/api/*` to Go API |
| **Go API Gateway** | Go 1.25 / Fiber v2 | Authentication, job CRUD, Kafka pub/sub, S3 presigned URLs |
| **Python Media Worker** | Python 3.11 | The 6-stage analysis pipeline |
| **PostgreSQL** | PostgreSQL 16 | Persists users, jobs, and analysis results |
| **Kafka** | Confluent Kafka 7.6 | Async message broker between Go API and Python Worker |
| **MinIO** | MinIO (latest) | S3-compatible object store for evidence PDFs |

### Communication Patterns

- **Synchronous (HTTP):** Frontend ↔ Go API (REST), Worker → Go API (status PATCH)
- **Asynchronous (Event-Driven):** Go API → Kafka → Worker → Kafka → Go API
- **External APIs:** Worker → Soniox (STT), Worker → Gemini (AI analysis)
- **Object Storage:** Worker → MinIO (PDF upload), Go API → MinIO (presigned URLs)

---

## Tech Stack

### Frontend
| Technology | Version | Purpose |
|------------|---------|---------|
| **TypeScript** | ~6.0.2 | Language |
| **React** | 19.2.6 | UI framework |
| **Vite** | 8.0.12 | Build tool / dev server |
| **Tailwind CSS** | 4.3.1 | Utility-first styling |
| **React Router** | 7.18.0 | Client-side routing |
| **Lucide React** | 1.21.0 | Icon library |
| **ESLint** | 10.3.0 | Linting |

### API Gateway
| Technology | Version | Purpose |
|------------|---------|---------|
| **Go** | 1.25 | Language |
| **Fiber v2** | 2.52.13 | HTTP framework (Express-like) |
| **pgx v5** | 5.10.0 | PostgreSQL driver |
| **kafka-go** | 0.4.51 | Kafka client |
| **minio-go v7** | 7.0.73 | S3 client |
| **golang-jwt v5** | 5.3.1 | JWT authentication |
| **Zap** | 1.28.0 | Structured logging |

### Media Worker
| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.11.11 | Language |
| **confluent-kafka** | ≥2.3.0 | Kafka client |
| **google-genai** | ≥0.1.0 | Gemini 2.0 Flash API |
| **soniox** | ≥2.0.0 | Speech-to-text (KZ/RU) |
| **yt-dlp** | ≥2024.3.10 | Social media video download |
| **FFmpeg** | (system) | Audio extraction, keyframe extraction |
| **WeasyPrint** | ≥60.0 | HTML → PDF rendering |
| **Jinja2** | ≥3.1.0 | PDF template engine |
| **boto3** | ≥1.34.0 | S3/MinIO upload |
| **Pillow** | ≥10.0.0 | Image processing |
| **Pydantic** | ≥2.0.0 | Data validation |

### Infrastructure
| Technology | Version | Purpose |
|------------|---------|---------|
| **PostgreSQL** | 16-alpine | Database |
| **Apache Kafka** | 7.6.0 (Confluent) | Message broker (KRaft mode) |
| **MinIO** | latest | S3-compatible object storage |
| **Nginx** | 1.26-alpine | Reverse proxy / static serving |
| **Docker** | — | Container runtime |
| **Docker Compose** | — | Service orchestration |
| **Docker Bake** | — | Cache-aware parallel builds |

---

## Approaches & Patterns

### Architecture Patterns

| Pattern | Implementation |
|---------|---------------|
| **Microservices** | Three independently deployable services (Go API, Python Worker, React Frontend) |
| **Event-Driven Architecture** | Async communication via Kafka — services are decoupled and communicate through events |
| **Saga Pattern** | Distributed transaction across services — Go API creates a job → Worker processes it → Go API completes it, with status sync at every step |
| **CQRS** | Separate write path (job creation via POST) and read path (job polling via GET) |
| **Repository Pattern** | Go's `repository/` layer abstracts all PostgreSQL queries behind interfaces |
| **Service Layer Pattern** | Go's `service/` encapsulates business logic (URL validation, state machine, status transitions) |
| **Two-Pass AI Chain** | Dual Gemini prompts — Pass 1 extracts raw signals (multimodal), Pass 2 scores risk (text-only). Separation of concerns prevents cross-contamination |

### State Machine

Job status transitions are enforced in Go's service layer with a `validTransitions` map:

```
pending → downloading → extracting → analyzing → aggregating → generating_evidence → completed
                                                                                      └→ failed (any stage)
```

Invalid transitions (e.g., `pending → completed`) are rejected with a 400 error.

### Resilience Patterns

| Pattern | Where |
|---------|-------|
| **Retry with Exponential Backoff** | Kafka consumer DB operations (1s→2s→4s→8s), Gemini API calls (2s base) |
| **Graceful Degradation** | Mock mode at every stage — when API keys are missing, the pipeline produces deterministic mock results |
| **Idempotent Consumers** | Kafka consumer commits only after successful processing — restarting replays uncommitted messages |
| **Cleanup in Finally** | Temp directories are always cleaned up, even on pipeline failure |
| **Presigned URLs** | Go API generates short-lived (168h) S3 URLs dynamically — no persistent URL storage needed |
| **Chain of Custody** | Every pipeline stage is timestamped and logged in the PDF evidence pack for legal admissibility |

### Security Patterns

| Pattern | Where |
|---------|-------|
| **JWT Authentication** | HS256-signed tokens for inspector API access |
| **Internal Token** | Separate bearer token for worker→API communication (no user context needed) |
| **Bcrypt Password Hashing** | All user passwords hashed with bcrypt |
| **URL Allowlist** | Only URLs from trusted platforms (tiktok.com, instagram.com, instagr.am) are accepted |
| **Rate Limiting** | 100 requests/minute per IP |
| **Request Tracing** | X-Request-ID correlation across all services |
| **Distroless Base Image** | Go API runs on `gcr.io/distroless/static-debian12:nonroot` — zero shell, minimal attack surface |

---

## Media Worker Pipeline

The Python Media Worker is the core of the system. It consumes job events from Kafka and runs each video through a **6-stage pipeline**:

```
Kafka ──▶ 1. Download ──▶ 2. Extract ──▶ 3. Transcribe ──▶ 4. AI Pass 1 ──▶ 5. AI Pass 2 ──▶ 6. Evidence ──▶ Kafka
          (yt-dlp)       (FFmpeg)        (Soniox STT)     (Gemini:        (Gemini:         (WeasyPrint     (completed)
                                                           signals)         scoring)         PDF)  
```

### Stage 1 — Video Download
**Tool:** `yt-dlp`
Downloads the video from the provided social media URL to a temp directory as `source.mp4`. Falls back gracefully if the platform blocks the download.

### Stage 2 — Media Extraction
**Tool:** `FFmpeg`
- **Audio:** Extracts mono MP3 audio (`-ac 1`, `libmp3lame` codec)
- **Keyframes:** Extracts 1 JPEG frame every 3 seconds (`fps=1/3`) for visual analysis

### Stage 3 — Speech-to-Text
**Service:** `Soniox STT`
Transcribes the audio with **per-word timestamps** and **per-token language detection**. Supports code-switched Kazakh/Russian — critical for analyzing Central Asian social media content.

### Stage 4 — AI Pass 1: Signal Extraction
**Model:** `Gemini 2.0 Flash` (multimodal)
Sends keyframes (base64 images) + transcript to Gemini and requests structured JSON output:
- Flagged phrases with timestamps and categories
- Visual markers (logos, text overlays, UI elements)
- Detected entities (brands, people, platforms)

**Categories monitored:** `illegal_gambling`, `pyramid_scheme`, `investment_fraud`, `referral_scheme`

### Stage 5 — AI Pass 2: Risk Scoring
**Model:** `Gemini 2.0 Flash` (text-only)
Takes Pass 1's structured output (no raw media) and produces:
- **risk_score** (0–100)
- **confidence** (low/medium/high)
- **Per-category scores** (0–100 each)
- **Reasoning** (free-text explanation)
- **Top flags** (prioritized list of signals with weights)

The two-pass design prevents the model from being influenced by raw media when scoring — it scores based on extracted signals only, reducing hallucination risk.

### Stage 6 — Evidence Pack PDF (Conditional)
**Threshold:** `risk_score >= 70`

If the risk threshold is met:
1. **Jinja2** renders an HTML template with inline CSS (A4 print format)
2. **WeasyPrint** converts HTML to PDF
3. **boto3** uploads the PDF to MinIO (`evidence-packs/<job_id>.pdf`)

**PDF contents:**
- Cover page with risk score badge
- Executive summary (Gemini's reasoning)
- Category score breakdown (bar and table)
- Flagged keyframes (embedded as base64 images)
- Annotated transcript (flagged phrases in red)
- Technical metadata (request IDs, model versions)
- **Chain of custody** — timestamped log of every pipeline step

---

## Frontend (Output)

The React frontend provides a **3-page inspector dashboard**:

### Pages

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | **HomePage** | URL input form with platform detection, risk tier display |
| `/processing/:jobId` | **ProcessingPage** | Live progress visualization — polls every 2s (max 60s), shows 6-stage pipeline status with color-coded badges |
| `/report/:jobId` | **ReportPage** | Full analysis report — risk score (0–100), confidence badge, 4-category breakdown (horizontal bar charts), top flags, reasoning, and evidence PDF download button |

### Key Behaviors

- **Auto-navigation:** ProcessingPage → ReportPage on job completion
- **Polling:** Every 2 seconds with 60-second timeout
- **Status badges:** Color-coded (pending=gray, downloading=blue, extracting=indigo, analyzing=purple, aggregating=orange, generating_evidence=yellow, completed=green, failed=red) with pulse animation
- **Evidence download:** Go API generates a fresh S3 presigned URL on click (168h expiry)
- **Static serving:** Built with Vite → served by Nginx in production (no Node.js runtime)

---

## Getting Started

### Prerequisites

- Docker & Docker Compose v2
- (Optional) Soniox API key for STT transcription
- (Optional) Google Gemini API key for AI analysis

Without API keys, the system runs in **mock mode** — producing deterministic results for pipeline testing.

### Quick Start

```bash
# 1. Clone the repository
git clone <repo-url>
cd aimedia

# 2. Start all services
docker compose -f deploy/docker/docker-compose.yml up -d

# 3. Access the frontend
open http://localhost

# 4. Log in with the seeded admin account
#    Email: admin@mediawatch.ai
#    Password: admin123 (see db/migrations/002_create_users.sql)
```

The frontend is served at `http://localhost`, and the Go API is available internally at `go-api:8080`.

---

## Project Structure

```
aimedia/
├── api-gateway/                    # Go API Gateway
│   ├── cmd/server/main.go         # Entry point — DI wiring, server startup
│   └── internal/
│       ├── config/                # Environment-based configuration
│       ├── handler/               # HTTP handlers (health, auth, jobs, internal)
│       ├── middleware/            # Auth, CORS, logging, rate-limit, recovery, tracing
│       ├── model/                 # Domain types (Job, Auth, Result)
│       ├── router/                # Route registration
│       ├── service/               # Business logic (URL validation, state machine)
│       ├── repository/           # PostgreSQL data access layer
│       ├── queue/                 # Kafka producer + consumer
│       └── storage/              # MinIO S3 client
├── media-worker/                   # Python Media Worker
│   └── src/
│       ├── main.py               # Pipeline orchestrator
│       ├── config.py             # Configuration
│       ├── queue/                # Kafka consumer + producer
│       ├── extractor/            # yt-dlp downloader + FFmpeg processor
│       ├── analyzer/             # Soniox STT + Gemini AI clients
│       └── pdfgen/               # PDF generation (Jinja2 + WeasyPrint)
│           └── templates/        # HTML templates for evidence PDFs
├── frontend/                       # React SPA
│   └── src/
│       ├── pages/                # HomePage, ProcessingPage, ReportPage
│       ├── components/           # Navbar, Footer, StatusBadge, RiskScoreBadge,
│       │                         # CategoryBreakdown, EvidenceButton
│       └── services/            # API client + polling logic
├── db/                             # PostgreSQL schemas & migrations
│   └── migrations/               # 004 sequential SQL migration files
├── deploy/                         # Infrastructure
│   ├── docker/                    # docker-compose.yml
│   └── nginx/                     # nginx.conf
├── docs/                           # Documentation
│   ├── AI_Media_Watch_Architecture.md
│   ├── dev-env-spec.md
│   ├── media-check.md
│   └── media-explanations.md
└── docker-bake.hcl                # Docker Bake — multi-service builds
```

---

## Environment Variables

### Go API Gateway (`.env`)
| Variable | Default | Description |
|----------|---------|-------------|
| `API_PORT` | `8080` | HTTP server port |
| `DATABASE_URL` | — | PostgreSQL connection string |
| `KAFKA_BROKER` | `kafka:29092` | Kafka broker address |
| `MINIO_ENDPOINT` | `minio:9000` | MinIO S3 endpoint |
| `MINIO_ACCESS_KEY` | — | MinIO access key |
| `MINIO_SECRET_KEY` | — | MinIO secret key |
| `JWT_SECRET` | — | JWT signing key |
| `INTERNAL_TOKEN` | — | Worker→API shared secret |

### Media Worker (`.env`)
| Variable | Default | Description |
|----------|---------|-------------|
| `GO_API_BASE_URL` | `http://go-api:8080` | Go API endpoint for status sync |
| `GO_API_INTERNAL_TOKEN` | — | Shared internal auth token |
| `KAFKA_BROKER` | `kafka:29092` | Kafka broker address |
| `SONIOX_API_KEY` | — | Soniox STT API key |
| `GEMINI_API_KEY` | — | Google Gemini API key |
| `MINIO_ENDPOINT` | `minio:9000` | MinIO S3 endpoint |
| `MINIO_ACCESS_KEY` | — | MinIO access key |
| `MINIO_SECRET_KEY` | — | MinIO secret key |

### Frontend
| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `/api/v1` | API base path (proxied by Nginx) |

---

## API Reference

### Public Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/health` | None | Liveness probe |
| `POST` | `/api/v1/auth/login` | None | Authenticate and receive JWT |

### Protected Endpoints (JWT Required)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/jobs` | JWT | Submit a new media analysis job |
| `GET` | `/api/v1/jobs` | JWT | List all jobs for the inspector |
| `GET` | `/api/v1/jobs/:id` | JWT | Get job details with results |
| `GET` | `/api/v1/jobs/:id/evidence` | JWT | Get presigned evidence download URL |

### Internal Endpoints (Worker → API)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `PATCH` | `/internal/v1/jobs/:id/status` | Internal Token | Update job pipeline status |

---

## Deployment

### Docker Compose (Development / Single-Host)

```bash
docker compose -f deploy/docker/docker-compose.yml up -d
```

Seven services with resource limits:

| Service | Memory Limit | Port(s) |
|---------|-------------|---------|
| postgres | 256M | 5432 |
| kafka | 600M | 9092 |
| minio | 256M | 9000 (API), 9001 (Console) |
| go-api | 150M | 8080 |
| python-worker | 450M | — |
| react-frontend | 30M | 80 |

### Docker Bake (Cache-Aware Parallel Builds)

```bash
docker buildx bake -f docker-bake.hcl
```

Builds all three custom services in parallel with layer caching, pushing to GitHub Container Registry.

### Multi-Stage Builds

All three custom Dockerfiles use multi-stage builds:

- **Go API:** `golang:1.26-alpine` build → `gcr.io/distroless/static-debian12:nonroot` runtime (~2MB final image)
- **Python Worker:** `python:3.11.11-slim` with system dependencies (FFmpeg, libpango for WeasyPrint)
- **React Frontend:** `node:22-alpine` build → `nginx:1.26-alpine` runtime

---

## License

[MIT](LICENSE) — feel free to use, modify, and distribute.
