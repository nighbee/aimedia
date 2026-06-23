"""
Main Coordinator — AI Media Watch Media Pipeline Entry Point

Orchestrates the 6-stage pipeline:
  1. Consume job from Kafka (media.job.created)
  2. Download video via yt-dlp
  3. Extract audio (MP3) and keyframes via FFmpeg
  4. Transcribe audio via Soniox
  5. Two-pass fraud analysis via Gemini 2.0 Flash
  6. (If risk_score >= 70) Generate Evidence Pack PDF
  7. Publish result to Kafka (media.job.completed)
  8. Sync status to Go API Gateway via PATCH
  9. Clean up /tmp working directory
"""
import json
import os
import shutil
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

from src.config import Config
from src.extractor.downloader import VideoDownloader
from src.extractor.ffmpeg_processor import FFmpegProcessor
from src.analyzer.soniox_client import SonioxClient
from src.analyzer.gemini_client import GeminiClient
from src.pdfgen.generator import EvidencePackGenerator
from src.queue.consumer import JobConsumer
from src.queue.producer import JobProducer
from src.cache import ContentCache

RISK_THRESHOLD = Config.EVIDENCE_RISK_THRESHOLD
WORK_DIR = Path(Config.TMP_DIR)
USE_SCENE_DETECTION = os.getenv("USE_SCENE_DETECTION", "false").lower() == "true"
USE_PARALLEL_PASS1 = os.getenv("USE_PARALLEL_PASS1", "true").lower() == "true"


# ─── Status Sync ───────────────────────────────────────────────────────────────

_status_log: dict[str, list[dict]] = {}  # job_id → list of status updates received

def _sync_status(job_id: str, status: str, failed_at_stage: Optional[str] = None):
    """PATCH the Go API Gateway internal endpoint to update job status."""
    url = f"{Config.GO_API_BASE_URL}/internal/v1/jobs/{job_id}/status"
    headers = {
        "Authorization": f"Bearer {Config.GO_API_INTERNAL_TOKEN}",
        "Content-Type": "application/json",
    }
    body: dict = {"status": status}
    if failed_at_stage:
        body["failed_at_stage"] = failed_at_stage

    try:
        resp = requests.patch(url, json=body, headers=headers, timeout=10)
        resp.raise_for_status()
        print(f"[Status Sync] {job_id} → {status} OK")
    except Exception as e:
        if Config.IS_MOCK_MODE:
            print(f"[MOCK Status Sync] {job_id} → {status} (mock server may not be running: {e})")
        else:
            print(f"[Status Sync] Could not PATCH {url}: {e}")


# ─── Mock HTTP Server ──────────────────────────────────────────────────────────

class _MockStatusHandler(BaseHTTPRequestHandler):
    """Handles PATCH /internal/v1/jobs/<job_id>/status — logs requests for verification."""

    def _parse_path(self):
        parsed = urlparse(self.path)
        return parsed.path, parsed.path.split("/")

    def do_PATCH(self):
        path, parts = self._parse_path()
        if path.startswith("/internal/v1/jobs/") and path.endswith("/status"):
            content_len = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_len)) if content_len > 0 else {}
            job_id = parts[-2]
            status = body.get("status", "unknown")

            _status_log.setdefault(job_id, []).append(body)
            print(f"[Mock API] PATCH /internal/v1/jobs/{job_id}/status → {status}")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # suppress default HTTP server logging


def _start_mock_server(host: str = "0.0.0.0", port: int = 8080) -> HTTPServer:
    """Start a mock HTTP server on a background thread — returns the server instance."""
    server = HTTPServer((host, port), _MockStatusHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"[Mock API] HTTP server listening on {host}:{port}")
    return server


def _custody_entry(stage: str, status: str = "OK") -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stage": stage,
        "status": status,
    }


def _patch_evidence_url(job_id: str, evidence_url: str):
    """PATCH the Go API to update evidence_url on a completed job."""
    url = f"{Config.GO_API_BASE_URL}/internal/v1/jobs/{job_id}/evidence"
    headers = {
        "Authorization": f"Bearer {Config.GO_API_INTERNAL_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.patch(url, json={"evidence_url": evidence_url}, headers=headers, timeout=10)
        resp.raise_for_status()
        print(f"[Status Sync] {job_id} evidence_url updated OK")
    except Exception as e:
        print(f"[Status Sync] Could not PATCH evidence_url for {job_id}: {e}")


# ─── Pipeline ──────────────────────────────────────────────────────────────────

def process_job(
    job: dict,
    downloader: VideoDownloader,
    gemini: GeminiClient,
    soniox: SonioxClient,
    pdf_gen: EvidencePackGenerator,
    producer: JobProducer,
    cache: ContentCache = None,
) -> None:
    job_id = job["job_id"]
    url = job["url"]
    platform = job.get("platform", "unknown")
    inspector_id = job.get("inspector_id", "system")

    # ── Cache check ───────────────────────────────────────────────────────
    if cache:
        cached = cache.get(url)
        if cached:
            print(f"[Pipeline] Cache hit for job={job_id}, publishing cached result")
            producer.publish_completed(
                job_id=job_id,
                risk_score=cached["risk_score"],
                confidence=cached["confidence"],
                reasoning=cached["reasoning"],
                categories=cached["categories"],
                top_flags=cached["top_flags"],
                evidence_url=cached.get("evidence_url"),
                custody_log=[_custody_entry("cache", "Result served from cache")],
            )
            _sync_status(job_id, "completed")
            return

    job_dir = WORK_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    video_path = str(job_dir / "source.mp4")
    audio_path = str(job_dir / "audio.mp3")
    frames_dir = str(job_dir / "frames")

    custody_log: list[dict] = [_custody_entry("ingestion", "Job received from Kafka")]

    try:
        # ── Stage 1: Download ──────────────────────────────────────────────
        _sync_status(job_id, "downloading")
        print(f"\n{'='*60}")
        print(f"[Pipeline] START job={job_id} url={url}")
        downloader.download(url, video_path)
        custody_log.append(_custody_entry("download", "Video downloaded via download layers"))

        # ── Stage 2: Extract (parallel audio + keyframes) ──────────────────
        _sync_status(job_id, "extracting")
        audio_path, keyframe_paths = FFmpegProcessor.extract_all(
            video_path, audio_path, frames_dir, use_scene_detection=USE_SCENE_DETECTION,
        )
        custody_log.append(_custody_entry("extraction", f"Extracted audio + {len(keyframe_paths)} keyframes (parallel)"))

        # ── Stage 3: Transcribe ────────────────────────────────────────────
        _sync_status(job_id, "analyzing")
        transcript = soniox.transcribe(audio_path)
        custody_log.append(_custody_entry("soniox_stt", f"Transcribed {len(transcript.tokens)} tokens (job={transcript.soniox_job_id})"))

        # ── Stage 4: AI Analysis — Pass 1 (parallel visual + audio) ───────
        if USE_PARALLEL_PASS1:
            signals = gemini.pass1_extract_signals_parallel(
                transcript_text=transcript.text,
                keyframe_paths=keyframe_paths,
            )
            custody_log.append(_custody_entry("gemini_pass1", f"Parallel: {len(signals.phrases)} phrases, {len(signals.visual_markers)} markers"))
        else:
            signals = gemini.pass1_extract_signals(
                transcript_text=transcript.text,
                keyframe_paths=keyframe_paths,
            )
            custody_log.append(_custody_entry("gemini_pass1", f"Sequential: {len(signals.phrases)} phrases, {len(signals.visual_markers)} markers"))

        # ── Stage 5: AI Analysis — Pass 2 ─────────────────────────────────
        _sync_status(job_id, "aggregating")
        scoring = gemini.pass2_score_risk(signals)
        custody_log.append(_custody_entry("gemini_pass2", f"Risk score={scoring.risk_score}, confidence={scoring.confidence}"))

        # ── Stage 6: Publish result first (don't block on PDF) ─────────────
        producer.publish_completed(
            job_id=job_id,
            risk_score=scoring.risk_score,
            confidence=scoring.confidence,
            reasoning=scoring.reasoning,
            categories=scoring.categories,
            top_flags=scoring.top_flags,
            evidence_url=None,
            custody_log=custody_log,
        )
        _sync_status(job_id, "completed")
        print(f"[Pipeline] RESULT  job={job_id} risk_score={scoring.risk_score} (publishing before PDF)")

        # ── Stage 7: Evidence Pack (async, non-blocking) ───────────────────
        if scoring.risk_score >= RISK_THRESHOLD:
            def _generate_pdf_async():
                try:
                    _sync_status(job_id, "generating_evidence")
                    evidence_url = pdf_gen.generate(
                        job_id=job_id,
                        source_url=url,
                        platform=platform,
                        inspector_id=inspector_id,
                        transcript=transcript,
                        signals=signals,
                        scoring=scoring,
                        keyframe_paths=keyframe_paths,
                        custody_log=custody_log,
                    )
                    # Update job with evidence URL via internal PATCH
                    if evidence_url:
                        _patch_evidence_url(job_id, evidence_url)
                    print(f"[Pipeline] PDF done  job={job_id} evidence={evidence_url}")
                except Exception as e:
                    print(f"[Pipeline] PDF generation failed for job={job_id}: {e}")

            threading.Thread(target=_generate_pdf_async, daemon=True, name=f"pdf-{job_id[:8]}").start()

        # ── Cache the result ───────────────────────────────────────────────
        if cache:
            cache.put(url, {
                "risk_score": scoring.risk_score,
                "confidence": scoring.confidence,
                "reasoning": scoring.reasoning,
                "categories": scoring.categories,
                "top_flags": [{"signal": f.signal, "weight": f.weight} for f in scoring.top_flags],
            })

    except Exception as e:
        stage = "unknown"
        print(f"[Pipeline] ERROR job={job_id}: {e}")
        custody_log.append(_custody_entry(stage, f"FAILED: {e}"))
        producer.publish_failed(job_id=job_id, stage=stage, error=str(e), custody_log=custody_log)
        _sync_status(job_id, "failed", failed_at_stage=stage)

    finally:
        try:
            shutil.rmtree(str(job_dir), ignore_errors=True)
        except Exception:
            pass


# ─── Entry Point ───────────────────────────────────────────────────────────────

def main():
    Config.validate()

    consumer = JobConsumer()
    producer = JobProducer()
    downloader = VideoDownloader()
    gemini = GeminiClient()
    soniox = SonioxClient()
    pdf_gen = EvidencePackGenerator()
    cache = ContentCache()

    # Graceful shutdown
    running = True
    def _shutdown(sig, frame):
        nonlocal running
        print("\n[Main] Shutdown signal received. Draining …")
        running = False

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    print(f"[Main] Media worker started. MOCK_MODE={Config.IS_MOCK_MODE}")
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    # ── Mock mode: start mock HTTP server, process synthetic job, then exit ───
    if Config.IS_MOCK_MODE:
        # Extract host/port from GO_API_BASE_URL for mock server
        mock_port = 8080
        if ":" in Config.GO_API_BASE_URL.split("//")[-1]:
            mock_port = int(Config.GO_API_BASE_URL.split("//")[-1].split(":")[-1].rstrip("/"))
        mock_server = _start_mock_server(host="0.0.0.0", port=mock_port)
        print("[MOCK] Running single mock job to verify pipeline …\n")
        mock_job = {
            "job_id": "mock-job-00000000",
            "url": "https://www.tiktok.com/@example/video/7123456789",
            "platform": "tiktok",
            "priority": 2,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "inspector_id": "inspector-mock-001",
        }
        process_job(mock_job, downloader, gemini, soniox, pdf_gen, producer, cache)

        # Verify status sync calls
        received = _status_log.get("mock-job-00000000", [])
        # Note: generating_evidence may appear asynchronously after completed
        expected_core = ["downloading", "extracting", "analyzing", "aggregating", "completed"]
        print(f"\n[MOCK] Status sync verification:")
        print(f"  Expected {len(expected_core)} core status updates, received {len(received)}")
        for exp in expected_core:
            rec_statuses = [r.get("status", "?") for r in received]
            ok = "✓" if exp in rec_statuses else "✗"
            print(f"  {ok} {exp}")

        mock_server.shutdown()
        print("\n[MOCK] Pipeline verification complete.")
        return

    # ── Live mode: continuous Kafka loop ──────────────────────────────────────
    print("[Main] Entering Kafka poll loop …")
    while running:
        try:
            job = consumer.poll(timeout_s=5.0)
            if job:
                process_job(job, downloader, gemini, soniox, pdf_gen, producer, cache)
            else:
                time.sleep(0.1)
        except Exception as e:
            print(f"[Main] Unhandled error in poll loop: {e}")
            time.sleep(2)

    # Cleanup
    soniox.close()
    producer.close()
    consumer.close()
    print("[Main] Shutdown complete.")


if __name__ == "__main__":
    main()
