# AI Media Watch — Developer Environment Specification

This file is the single source of truth for service names, ports, environment variables,
file paths, and Kafka topic names. Every agent working on this codebase must read this
file before generating any configuration, connection string, or Dockerfile.

Do not hardcode any value listed here in application code. Always read from environment.

---

## Service names (Docker Compose)

| Service | Compose name | Internal hostname |
|---|---|---|
| Go API | `go-api` | `go-api` |
| Python worker | `python-worker` | `python-worker` |
| Kafka broker | `kafka` | `kafka` |
| PostgreSQL | `postgres` | `postgres` |
| React frontend | `frontend` | `frontend` |

---

## Ports

| Service | Internal port | Host-mapped port |
|---|---|---|
| Go API | 8080 | 8080 |
| React frontend (nginx) | 80 | 3000 |
| PostgreSQL | 5432 | 5432 |
| Kafka broker | 9092 | 9092 |
| Kafka controller (KRaft) | 9093 | — (internal only) |

---

## Environment variables

### Go API (`go-api`)

```env
# Server
PORT=8080
ENV=development

# PostgreSQL
DB_HOST=postgres
DB_PORT=5432
DB_USER=mediawatchuser
DB_PASSWORD=mediawatchpass
DB_NAME=mediawatch
DB_SSL_MODE=disable
DB_MAX_OPEN_CONNS=10
DB_MAX_IDLE_CONNS=5

# Kafka
KAFKA_BROKERS=kafka:9092
KAFKA_GROUP_ID=go-api-consumer
KAFKA_TOPIC_JOB_CREATED=media.job.created
KAFKA_TOPIC_JOB_COMPLETED=media.job.completed

# Auth
JWT_SECRET=change-me-in-production
JWT_EXPIRY_HOURS=24

# GCS (evidence pack storage)
GCS_BUCKET_NAME=ai-media-watch-evidence
GCS_SIGNED_URL_EXPIRY_HOURS=168
GOOGLE_APPLICATION_CREDENTIALS=/app/secrets/gcp-key.json
```

### Python worker (`python-worker`)

```env
# PostgreSQL (same creds as Go API — shared DB)
DB_HOST=postgres
DB_PORT=5432
DB_USER=mediawatchuser
DB_PASSWORD=mediawatchpass
DB_NAME=mediawatch

# Kafka
KAFKA_BROKERS=kafka:9092
KAFKA_GROUP_ID=python-worker-consumer
KAFKA_TOPIC_JOB_CREATED=media.job.created
KAFKA_TOPIC_JOB_COMPLETED=media.job.completed

# External AI APIs
SONIOX_API_KEY=your-soniox-key-here
GEMINI_API_KEY=your-gemini-key-here
GEMINI_MODEL=gemini-1.5-flash-latest

# Go API (worker calls PATCH /api/v1/jobs/:id/status to update state)
GO_API_BASE_URL=http://go-api:8080
GO_API_INTERNAL_TOKEN=internal-service-token-change-me

# GCS
GCS_BUCKET_NAME=ai-media-watch-evidence
GOOGLE_APPLICATION_CREDENTIALS=/app/secrets/gcp-key.json

# Processing
TMP_DIR=/tmp/mediawatch-jobs
MAX_VIDEO_DURATION_SECONDS=600
KEYFRAME_INTERVAL_SECONDS=3
KEYFRAME_MAX_WIDTH_PX=800
AUDIO_SAMPLE_RATE_HZ=16000
EVIDENCE_RISK_THRESHOLD=70

# Gemini rate limiting
GEMINI_MAX_RETRIES=3
GEMINI_RETRY_BACKOFF_BASE_SECONDS=2
```

---

## Kafka topics

| Topic | Partitions | Replication | Retention |
|---|---|---|---|
| `media.job.created` | 3 | 1 (hackathon) | 24h |
| `media.job.completed` | 3 | 1 (hackathon) | 24h |

**Consumer group IDs:**
- Go API consumes `media.job.completed` with group `go-api-consumer`
- Python worker consumes `media.job.created` with group `python-worker-consumer`

---

## PostgreSQL

```
Host:     postgres (internal) / localhost:5432 (from host)
Database: mediawatch
User:     mediawatchuser
Password: mediawatchpass
```

### Schemas

| Schema | Owner | Purpose |
|---|---|---|
| `core` | mediawatchuser | Users, jobs, targets (v2) |
| `media` | mediawatchuser | Raw media metadata |
| `analysis` | mediawatchuser | AI outputs, evidence records |

---

## File paths (Python worker)

```python
# Base temp directory — created fresh per job, deleted after completion
TMP_BASE = os.getenv("TMP_DIR", "/tmp/mediawatch-jobs")
JOB_DIR  = f"{TMP_BASE}/{job_id}"

# Files within job directory
VIDEO_PATH       = f"{JOB_DIR}/source.mp4"
AUDIO_PATH       = f"{JOB_DIR}/audio.mp3"
FRAME_PATTERN    = f"{JOB_DIR}/frame_%03d.jpg"   # ffmpeg output pattern
FRAME_GLOB       = f"{JOB_DIR}/frame_*.jpg"       # for listing extracted frames
EVIDENCE_PDF_PATH = f"{JOB_DIR}/evidence.pdf"

# GCS object path
GCS_OBJECT_PATH  = f"evidence-packs/{job_id}.pdf"
```

---

## Go API internal route (used by Python worker)

The Python worker calls the Go API to update job status mid-processing.
This avoids the worker needing a direct PostgreSQL connection for status updates.

```
PATCH /internal/v1/jobs/:id/status
Authorization: Bearer {GO_API_INTERNAL_TOKEN}
Content-Type: application/json

{
  "status": "downloading | extracting | analyzing | aggregating | generating_evidence"
}
```

This endpoint is not exposed to the React frontend. Bind it on a separate internal router
or protect it strictly with the internal token check.

---

## Docker Compose — complete file

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    container_name: postgres
    environment:
      POSTGRES_DB: mediawatch
      POSTGRES_USER: mediawatchuser
      POSTGRES_PASSWORD: mediawatchpass
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./migrations:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mediawatchuser -d mediawatch"]
      interval: 5s
      timeout: 5s
      retries: 5

  kafka:
    image: confluentinc/cp-kafka:7.6.0
    container_name: kafka
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_LOG_DIRS: /var/lib/kafka/data
      CLUSTER_ID: MkU3OEVBNTcwNTJENDM2Qk   # fixed for reproducibility
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_LOG_RETENTION_HOURS: 24
    volumes:
      - kafka_data:/var/lib/kafka/data
    ports:
      - "9092:9092"
    healthcheck:
      test: ["CMD-SHELL", "kafka-topics --bootstrap-server localhost:9092 --list"]
      interval: 10s
      timeout: 10s
      retries: 10

  go-api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: go-api
    env_file: ./backend/.env
    ports:
      - "8080:8080"
    depends_on:
      postgres:
        condition: service_healthy
      kafka:
        condition: service_healthy
    restart: unless-stopped

  python-worker:
    build:
      context: ./worker
      dockerfile: Dockerfile
    container_name: python-worker
    env_file: ./worker/.env
    volumes:
      - /tmp/mediawatch-jobs:/tmp/mediawatch-jobs
      - ./secrets:/app/secrets:ro
    depends_on:
      postgres:
        condition: service_healthy
      kafka:
        condition: service_healthy
      go-api:
        condition: service_started
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 450M

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: frontend
    ports:
      - "3000:80"
    depends_on:
      - go-api

volumes:
  postgres_data:
  kafka_data:
```

---

## Memory budget (GCP e2-small — 2 GB total)

| Service | Soft limit | Hard limit | Notes |
|---|---|---|---|
| Go API | 100 MB | 150 MB | GOGC=off if needed |
| Python worker | 350 MB | 450 MB | WeasyPrint peaks here |
| Kafka (KRaft) | 512 MB | 600 MB | Set KAFKA_HEAP_OPTS=-Xmx512m |
| PostgreSQL | 200 MB | 256 MB | shared_buffers=64MB |
| nginx (frontend) | 20 MB | 30 MB | Static files only |
| OS overhead | ~300 MB | — | |
| **Total** | **~1.48 GB** | **~1.79 GB** | Under 2 GB ceiling |

Add to Kafka service environment:
```yaml
KAFKA_HEAP_OPTS: "-Xmx512m -Xms256m"
```

Add to postgres service:
```yaml
command: postgres -c shared_buffers=64MB -c max_connections=20
```