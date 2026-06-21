**AI Media Watch**	System Architecture & API Reference

**AI MEDIA WATCH**

System Architecture & API Reference

Hackathon MVP — ИИ-Анализ Соцсетей и Видео Track

|<p>**Purpose**</p><p>Automated AI watchdog for government and platform inspectors. Hunts down illegal gambling operations, financial pyramid schemes, and investment fraud hidden in social media video content on Instagram and TikTok. Replaces thousands of hours of manual review with a real-time, multi-modal analysis pipeline.</p><p>**Core stack**</p><p>Go + Fiber (API gateway)  ·  Apache Kafka (async broker)  ·  Python 3.11 (media worker)  ·  PostgreSQL (persistence)  ·  Soniox API (KZ/RU STT)  ·  Gemini 1.5 Flash (vision + scoring)  ·  React + Tailwind (inspector UI)</p><p>**Key differentiator**</p><p>Evidence Pack — auto-generated timestamped PDF report containing transcript excerpts, risk score breakdown by fraud category, and the exact flagged keyframes. Ready to hand to a prosecutor without further preparation.</p>|
| :- |

June 2026


# **1. System Overview**
AI Media Watch is a five-stage event-driven pipeline. Each stage communicates asynchronously, so the Go API never blocks on slow media processing and the Python worker can be scaled independently. The sixth stage — the Evidence Pack generator — runs as a post-processing step inside the Python worker after a risk score exceeds the configured threshold.

## **1.1 Pipeline stages**

|**#**|**Stage**|**Component**|**Role**|
| :- | :- | :- | :- |
|1|**Ingestion**|React + Go + Fiber|Inspector submits a TikTok or Instagram URL. Go validates input, writes a pending job record to PostgreSQL, publishes a job\_id event to the media.job.created Kafka topic.|
|2|**Extraction**|Python + yt-dlp + FFmpeg|Python worker consumes the Kafka event, downloads the video via yt-dlp, then uses FFmpeg to extract a mono MP3 audio track and one keyframe every 3 seconds.|
|3|**Analysis**|Soniox API + Gemini 1.5 Flash|Audio sent to Soniox for KZ/RU code-switched transcription. Keyframes and transcript sent to Gemini in a two-pass structured prompt chain that returns risk signals as JSON.|
|4|**Aggregation**|Python aggregator|Combines Soniox transcript and Gemini JSON output. Produces a final risk\_score (0-100), per-category breakdown, and list of flagged phrases and visual markers.|
|5|**Evidence Pack**|Python + WeasyPrint + Jinja2|If risk\_score >= 70, generates a timestamped PDF evidence report embedding the transcript, risk breakdown, and the exact flagged keyframes. Stored to GCS and URL written to DB.|
|6|**Resolution**|Go + PostgreSQL + React|Go consumes media.job.completed Kafka event, updates job status and evidence\_url in PostgreSQL. React dashboard reflects the updated risk queue with download link for the evidence PDF.|

## **1.2 Job state machine**
Each job progresses through a defined set of states stored in the jobs.status column. Failed jobs record the stage at which they died, enabling targeted retry logic.

|**State**|**Description**|
| :- | :- |
|**pending**|Job written to DB. Awaiting Kafka consumption by Python worker.|
|**downloading**|yt-dlp is fetching the video from the source platform.|
|**extracting**|FFmpeg is splitting audio and keyframes from the downloaded video.|
|**analyzing**|Soniox and Gemini API calls are in flight.|
|**aggregating**|Python worker is computing final risk score from AI outputs.|
|**generating\_evidence**|WeasyPrint PDF is being rendered (risk\_score >= 70 only).|
|**completed**|All stages successful. evidence\_url populated if threshold was met.|
|**failed**|A stage threw an unrecoverable error. failed\_at\_stage column populated.|


# **2. Component Specifications**
## **2.1 Go + Fiber API Gateway**
The Go backend is the single HTTP entry point for the React frontend and the Kafka consumer for completed job events. It never calls external AI APIs directly.

**Responsibilities**

- Validate and sanitise incoming URLs (allowlist: tiktok.com, instagram.com)
- Write initial job records to PostgreSQL with status = pending
- Publish job\_id events to Kafka topic media.job.created
- Consume media.job.completed events and update job status + evidence\_url
- Serve REST endpoints consumed by the React dashboard
- Serve pre-signed GCS download URLs for evidence PDFs

**Key endpoints**

|**Method**|**Path**|**Auth**|**Description**|
| :- | :- | :- | :- |
|**POST**|/api/v1/jobs|Inspector JWT|Submit a video URL for analysis. Returns job\_id immediately.|
|**GET**|/api/v1/jobs|Inspector JWT|List all jobs, sorted by risk\_score desc. Supports ?status= filter.|
|**GET**|/api/v1/jobs/:id|Inspector JWT|Fetch full job detail including AI reasoning and evidence\_url.|
|**GET**|/api/v1/jobs/:id/evidence|Inspector JWT|Returns a short-lived pre-signed download URL for the evidence PDF.|
|**GET**|/api/v1/health|None|Liveness probe. Returns 200 OK with component status map.|

## **2.2 Apache Kafka — Message Broker**
Kafka is the async backbone that decouples the Go API from the slow Python worker. Two topics are used. A third topic can be added in v2 for the auto-ingestion scheduler.

|**Topic**|**Producer**|**Consumer**|**Payload fields**|
| :- | :- | :- | :- |
|**media.job.created**|Go API|Python worker|job\_id (uuid), url (string), priority (int 1-3), submitted\_at (ISO8601)|
|**media.job.completed**|Python worker|Go API|job\_id, status, risk\_score (int), categories (obj), evidence\_url (string|null), error (string|null)|

## **2.3 Python Worker — Media Extraction**
The Python worker is a single Kafka consumer process. It is the only component that calls external AI APIs and the only component that touches video files. All intermediate files (video, audio, frames) are written to a local /tmp working directory and deleted after the job completes.

**Processing steps**

- Consume message from media.job.created
- Update job status to downloading in PostgreSQL via Go API PATCH call
- Run yt-dlp to download video to /tmp/{job\_id}/source.mp4
- Update status to extracting
- Run FFmpeg to extract mono MP3 audio track → /tmp/{job\_id}/audio.mp3
- Run FFmpeg to extract 1 keyframe per 3 seconds → /tmp/{job\_id}/frame\_{n}.jpg
- Update status to analyzing
- POST audio.mp3 to Soniox API, receive timestamped transcript JSON
- POST frame images + transcript to Gemini 1.5 Flash (pass 1: extract signals)
- POST extracted signals to Gemini 1.5 Flash (pass 2: score + categorise)
- Update status to aggregating, compute final risk\_score
- If risk\_score >= 70: update status to generating\_evidence, call Evidence Pack generator
- Publish result to media.job.completed Kafka topic
- Clean up /tmp/{job\_id}/ directory

## **2.4 AI Analysis — Two-Pass Prompt Chain**
The VLM analysis is split into two explicit passes to ensure reasoning is auditable and each pass can be iterated independently.

**Pass 1 — Signal extraction (Gemini 1.5 Flash)**

|**Input**|Up to 20 keyframe JPGs (base64) + full Soniox transcript text. System prompt instructs strict JSON output only.|
| :- | :- |

System prompt (abridged):

|<p>You are a fraud-signal extractor. Given video keyframes and a transcript, identify and return ONLY a JSON object with no preamble or markdown. Schema:</p><p>{ "phrases": [{"text": str, "timestamp\_s": int, "category": str}],</p><p>`  `"visual\_markers": [{"frame\_index": int, "description": str, "category": str}],</p><p>`  `"entities": [{"name": str, "type": "brand|person|platform"}] }</p><p>Categories: illegal\_gambling | pyramid\_scheme | investment\_fraud | referral\_scheme | other</p>|
| :- |

**Pass 2 — Risk scoring (Gemini 1.5 Flash)**

|**Input**|Pass 1 JSON output only. System prompt instructs scoring per fraud category plus an overall score.|
| :- | :- |

System prompt (abridged):

|<p>You are a fraud risk scorer. Given extracted signals, return ONLY JSON. Schema:</p><p>{ "risk\_score": int(0-100),</p><p>`  `"confidence": "low"|"medium"|"high",</p><p>`  `"categories": { "illegal\_gambling": int, "pyramid\_scheme": int,</p><p>`    `"investment\_fraud": int, "referral\_scheme": int },</p><p>`  `"reasoning": str,</p><p>`  `"top\_flags": [{"signal": str, "weight": "high"|"medium"|"low"}] }</p>|
| :- |

**Risk tier thresholds**

|**Score range**|**Tier**|**Dashboard colour**|**Action**|
| :- | :- | :- | :- |
|**70 – 100**|**High risk**|Red|Auto-flag for review. Evidence Pack PDF generated and attached.|
|**40 – 69**|**Medium risk**|Amber|Added to manual review queue. Inspector decision required.|
|**0 – 39**|**Low risk**|Green|Cleared. Job archived. No evidence pack generated.|


# **3. Evidence Pack — PDF Report**

|**Key differentiator**|The Evidence Pack is the feature that transforms AI Media Watch from an analysis dashboard into a prosecution-ready tool. A flagged video produces a self-contained PDF that an inspector can hand directly to legal counsel without further preparation.|
| :- | :- |

## **3.1 Trigger condition**
The Evidence Pack generator is called by the Python worker immediately after the aggregation step, if and only if risk\_score >= 70. Lower-scoring jobs are completed without generating a PDF.

## **3.2 PDF report structure**

|**#**|**Section**|**Content**|
| :- | :- | :- |
|1|**Cover page**|Report ID (UUID), generation timestamp (ISO8601), source URL, platform (TikTok/Instagram), inspector ID, overall risk score in large font with tier colour.|
|2|**Executive summary**|One paragraph AI-generated summary of why this content was flagged. Suitable for non-technical readers such as legal counsel.|
|3|**Risk score breakdown**|Table showing per-category scores (illegal\_gambling, pyramid\_scheme, investment\_fraud, referral\_scheme) and top\_flags with signal weight.|
|4|**Flagged keyframes**|Embedded JPEG images for each frame cited by Gemini (visual\_markers), with frame index, timestamp, and AI description underneath.|
|5|**Audio transcript**|Full Soniox transcript, with flagged phrases highlighted inline. Includes timestamps for each flagged segment.|
|6|**Technical metadata**|Video duration, resolution, file hash (SHA-256), yt-dlp source metadata, AI model versions used, Soniox job ID, Gemini request IDs.|
|7|**Chain of custody**|Auto-generated log of each processing stage with timestamp and component version. Required for legal admissibility.|

## **3.3 Technical implementation**
The Evidence Pack is generated in Python using Jinja2 HTML templates rendered to PDF via WeasyPrint. Flagged keyframe images are embedded as base64 data URIs so the PDF is fully self-contained with no external dependencies.

**Python dependencies**

- weasyprint >= 60.0 — HTML-to-PDF renderer with CSS support
- jinja2 >= 3.1 — HTML templating for the report layout
- Pillow >= 10.0 — keyframe resizing before embedding
- google-cloud-storage — upload to GCS and generate signed URL

**Generation flow**

- Receive aggregation output dict (risk\_score, categories, top\_flags, reasoning, phrases, visual\_markers)
- Load flagged keyframe files from /tmp/{job\_id}/frame\_{n}.jpg
- Resize each frame to max 800px wide, encode as base64
- Render Jinja2 HTML template with all data
- Call WeasyPrint HTML.write\_pdf() to produce bytes
- Upload PDF bytes to GCS bucket evidence-packs/{job\_id}.pdf
- Generate signed URL valid for 7 days
- Return signed URL to aggregator, included in media.job.completed Kafka message

|**File size guidance**|A typical evidence report for a 60-second video with 20 embedded keyframes renders to approximately 2–4 MB. WeasyPrint processing time is under 5 seconds on a standard CPU instance.|
| :- | :- |


# **4. PostgreSQL Database Schema**
Three logical schemas provide domain separation without the overhead of multiple database instances. All tables use UUID primary keys to ensure globally unique identifiers across distributed components.

## **4.1 core.jobs (primary job tracking)**

|**Column**|**Type**|**Nullable**|**Description**|
| :- | :- | :- | :- |
|**id**|UUID|NOT NULL PK|Auto-generated job identifier|
|**url**|TEXT|NOT NULL|Original submitted URL|
|**platform**|VARCHAR(32)|NOT NULL|tiktok | instagram|
|**status**|VARCHAR(32)|NOT NULL|Current job state (see state machine)|
|**priority**|SMALLINT|NOT NULL DEFAULT 2|1=high, 2=normal, 3=low|
|**risk\_score**|SMALLINT|NULL|Final 0-100 score, populated after analysis|
|**confidence**|VARCHAR(16)|NULL|low | medium | high|
|**reasoning**|TEXT|NULL|AI-generated explanation|
|**evidence\_url**|TEXT|NULL|Signed GCS URL for evidence PDF|
|**failed\_at\_stage**|VARCHAR(32)|NULL|Stage name if status = failed|
|**retry\_count**|SMALLINT|NOT NULL DEFAULT 0|Number of retry attempts|
|**inspector\_id**|UUID|NOT NULL FK|References core.users.id|
|**created\_at**|TIMESTAMPTZ|NOT NULL DEFAULT now()|Job submission time|
|**updated\_at**|TIMESTAMPTZ|NOT NULL DEFAULT now()|Last status change time|
|**completed\_at**|TIMESTAMPTZ|NULL|Time of final completed or failed state|

## **4.2 analysis.results (per-category scores)**

|**Column**|**Type**|**Description**|
| :- | :- | :- |
|**id**|UUID PK|Auto-generated|
|**job\_id**|UUID FK|References core.jobs.id|
|**illegal\_gambling\_score**|SMALLINT|Per-category risk score 0-100|
|**pyramid\_scheme\_score**|SMALLINT|Per-category risk score 0-100|
|**investment\_fraud\_score**|SMALLINT|Per-category risk score 0-100|
|**referral\_scheme\_score**|SMALLINT|Per-category risk score 0-100|
|**top\_flags**|JSONB|Array of {signal, weight} objects from pass 2|
|**extracted\_signals**|JSONB|Full pass 1 output: phrases, visual\_markers, entities|
|**soniox\_job\_id**|TEXT|Soniox API reference for audit|
|**gemini\_pass1\_request\_id**|TEXT|Gemini API reference for audit|
|**gemini\_pass2\_request\_id**|TEXT|Gemini API reference for audit|
|**created\_at**|TIMESTAMPTZ|Row creation timestamp|


# **5. Input / Output Contracts**
## **5.1 POST /api/v1/jobs — Submit video for analysis**
**Request**

|<p>**POST /api/v1/jobs**</p><p>Authorization: Bearer <inspector\_jwt></p><p>Content-Type: application/json</p><p></p><p>{</p><p>`  `"url": "https://www.tiktok.com/@example/video/7123456789",</p><p>`  `"priority": 1  // optional, 1=high 2=normal 3=low</p><p>}</p>|
| :- |

**Response — 202 Accepted**

|<p>{</p><p>`  `"job\_id": "550e8400-e29b-41d4-a716-446655440000",</p><p>`  `"status": "pending",</p><p>`  `"created\_at": "2026-06-20T09:14:22Z"</p><p>}</p>|
| :- |

## **5.2 GET /api/v1/jobs/:id — Fetch completed job**
**Response — 200 OK (completed high-risk job)**

|<p>{</p><p>`  `"job\_id": "550e8400-e29b-41d4-a716-446655440000",</p><p>`  `"url": "https://www.tiktok.com/@example/video/7123456789",</p><p>`  `"platform": "tiktok",</p><p>`  `"status": "completed",</p><p>`  `"risk\_score": 88,</p><p>`  `"confidence": "high",</p><p>`  `"reasoning": "High risk (88/100). Soniox detected guaranteed income promise at 0:12. Gemini identified 1xBet logo overlay at frame 7 and aggressive referral call-to-action at frame 14.",</p><p>`  `"categories": { "illegal\_gambling": 91, "pyramid\_scheme": 42, "investment\_fraud": 65, "referral\_scheme": 78 },</p><p>`  `"evidence\_url": "https://storage.googleapis.com/evidence-packs/550e8400.pdf?X-Goog-Signature=...",</p><p>`  `"completed\_at": "2026-06-20T09:16:05Z"</p><p>}</p>|
| :- |

## **5.3 media.job.completed — Kafka payload**
**Python worker publishes on success**

|<p>{</p><p>`  `"job\_id": "550e8400-e29b-41d4-a716-446655440000",</p><p>`  `"status": "completed",</p><p>`  `"risk\_score": 88,</p><p>`  `"confidence": "high",</p><p>`  `"reasoning": "...",</p><p>`  `"categories": { "illegal\_gambling": 91, "pyramid\_scheme": 42, "investment\_fraud": 65, "referral\_scheme": 78 },</p><p>`  `"top\_flags": [{"signal": "guaranteed income phrase at 0:12", "weight": "high"}, {"signal": "1xBet logo frame 7", "weight": "high"}],</p><p>`  `"evidence\_url": "https://storage.googleapis.com/evidence-packs/550e8400.pdf?X-Goog-Signature=...",</p><p>`  `"error": null</p><p>}</p>|
| :- |


# **6. V2 Auto-Ingestion — Design Boundary**
The MVP accepts URLs submitted manually by inspectors. Version 2 adds an automated ingestion scheduler that monitors known high-risk accounts and injects URLs directly into the same Kafka pipeline. The MVP-to-V2 boundary is intentionally thin: only the event producer changes.

## **6.1 Architecture**
- A new Go goroutine (or separate cron service) queries a core.targets table of monitored accounts
- A social scraper checks for new posts via yt-dlp metadata fetch (no video download at this stage)
- New post URLs are published to media.job.created with priority = 3 (background)
- The entire downstream pipeline is unchanged — the Python worker cannot tell the difference

## **6.2 core.targets table (V2)**

|**Column**|**Type**|**Description**|
| :- | :- | :- |
|**id**|UUID PK|Target account identifier|
|**platform**|VARCHAR(32)|tiktok | instagram|
|**handle**|TEXT|Account handle e.g. @example|
|**profile\_url**|TEXT|Full profile URL|
|**check\_interval\_mins**|SMALLINT|How frequently to poll for new posts|
|**last\_checked\_at**|TIMESTAMPTZ|Timestamp of last successful poll|
|**added\_by**|UUID FK|Inspector who added this target|
|**is\_active**|BOOLEAN|Whether monitoring is currently active|

# **7. Deployment — Hackathon Setup**
All services run on a single GCP e2-small VM using Docker Compose for the hackathon demo. Production would split Python workers to a separate scalable instance group.

|**Service**|**Image**|**Notes**|
| :- | :- | :- |
|**go-api**|golang:1.22-alpine|Exposes :8080. GOMAXPROCS=1 for e2-small.|
|**python-worker**|python:3.11-slim|Installs yt-dlp, ffmpeg, weasyprint at build time.|
|**kafka**|confluentinc/cp-kafka:7.6|Single broker. KRaft mode (no Zookeeper).|
|**postgres**|postgres:16-alpine|Init script creates core/media/analysis schemas.|
|**react-frontend**|node:20-alpine|Built to static files, served by nginx:alpine.|

|**Memory budget**|Kafka KRaft mode (no Zookeeper) saves approximately 512 MB on e2-small. Cap Python worker at 400 MB and Go API at 128 MB to avoid OOM kills. WeasyPrint PDF generation peaks at ~200 MB — ensure this is within the worker cap.|
| :- | :- |

# **8. Known Risks & Mitigations**

|**Risk**|**Impact**|**Mitigation**|
| :- | :- | :- |
|**yt-dlp blocked by platform**|Download stage fails for live demo|Pre-download demo videos. Use --cookies flag with session token as fallback.|
|**Soniox KZ/RU accuracy**|Missed Kazakh-language red flag phrases|Dual transcription: also pass audio to Gemini's built-in audio mode. Compare outputs.|
|**Gemini rate limits**|Analysis queue backs up under load|Add exponential backoff + jitter. For demo, run single-threaded with manual pacing.|
|**WeasyPrint memory spike**|OOM kill on e2-small during PDF gen|Cap worker at 400 MB. Process frames one at a time. Use streaming write if available.|
|**Evidence PDF admissibility**|Legal counsel questions AI output|Chain of custody section in PDF. Log all API request IDs. Do not modify Gemini raw output.|



AI Media Watch — Hackathon MVP  ·  June 2026  ·  Confidential
Confidential — Hackathon MVP Draft	Page 
