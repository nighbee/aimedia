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
import logging
import os
import shutil
import signal
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

from src.config import Config

# ─── Structured Logging Setup ─────────────────────────────────────────────────

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger("media-worker")
logger.setLevel(logging.INFO)

# Suppress noisy libraries
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("confluent_kafka").setLevel(logging.WARNING)


def log_stage(job_id: str, stage: str, msg: str, level: str = "info"):
    """Log a pipeline stage with structured context."""
    extra = {"job_id": job_id, "stage": stage}
    log_fn = getattr(logger, level, logger.info)
    log_fn(f"[{stage}] job={job_id} {msg}", extra=extra)


# ─── Lazy imports (deferred so startup errors are clear) ──────────────────────

def _import_components():
    """Import all pipeline components. Returns dict of instances."""
    from src.extractor.downloader import VideoDownloader
    from src.extractor.ffmpeg_processor import FFmpegProcessor
    from src.analyzer.soniox_client import SonioxClient
    from src.analyzer.gemini_client import GeminiClient
    from src.pdfgen.generator import EvidencePackGenerator
    from src.queue.consumer import JobConsumer
    from src.queue.producer import JobProducer
    from src.cache import ContentCache

    return {
        "downloader": VideoDownloader,
        "ffmpeg": FFmpegProcessor,
        "soniox": SonioxClient,
        "gemini": GeminiClient,
        "pdf_gen": EvidencePackGenerator,
        "consumer_cls": JobConsumer,
        "producer_cls": JobProducer,
        "cache_cls": ContentCache,
    }


# ─── Status Sync ───────────────────────────────────────────────────────────────

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
        log_stage(job_id, "status-sync", f"→ {status} OK")
    except Exception as e:
        if Config.IS_MOCK_MODE:
            log_stage(job_id, "status-sync", f"→ {status} (mock: {e})", "warning")
        else:
            log_stage(job_id, "status-sync", f"PATCH failed {url}: {e}", "error")


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
        log_stage(job_id, "evidence-sync", f"evidence_url updated OK")
    except Exception as e:
        log_stage(job_id, "evidence-sync", f"PATCH failed: {e}", "error")


# ─── Pipeline ──────────────────────────────────────────────────────────────────

USE_SCENE_DETECTION = os.getenv("USE_SCENE_DETECTION", "false").lower() == "true"
USE_PARALLEL_PASS1 = os.getenv("USE_PARALLEL_PASS1", "true").lower() == "true"
RISK_THRESHOLD = Config.EVIDENCE_RISK_THRESHOLD
WORK_DIR = Path(Config.TMP_DIR)


def _custody_entry(stage: str, status: str = "OK") -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stage": stage,
        "status": status,
    }


def process_job(
    job: dict,
    downloader,
    gemini,
    soniox,
    pdf_gen,
    producer,
    ffmpeg,
    cache=None,
) -> None:
    job_id = job["job_id"]
    url = job["url"]
    platform = job.get("platform", "unknown")
    inspector_id = job.get("inspector_id", "system")
    start_time = time.time()

    log_stage(job_id, "start", f"url={url} platform={platform} priority={job.get('priority', 2)}")

    # ── Cache check ───────────────────────────────────────────────────────
    if cache:
        cached = cache.get(url)
        if cached:
            log_stage(job_id, "cache", "HIT — publishing cached result")
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
            elapsed = time.time() - start_time
            log_stage(job_id, "done", f"CACHED in {elapsed:.1f}s")
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
        log_stage(job_id, "download", "starting video download…")
        dl_start = time.time()
        downloader.download(url, video_path)
        dl_elapsed = time.time() - dl_start
        file_size = os.path.getsize(video_path) if os.path.exists(video_path) else 0
        log_stage(job_id, "download", f"done in {dl_elapsed:.1f}s ({file_size} bytes)")
        custody_log.append(_custody_entry("download", "Video downloaded via download layers"))

        # ── Stage 2: Extract (parallel audio + keyframes) ──────────────────
        _sync_status(job_id, "extracting")
        log_stage(job_id, "extract", "starting FFmpeg extraction…")
        ext_start = time.time()
        audio_path, keyframe_paths = ffmpeg.extract_all(
            video_path, audio_path, frames_dir, use_scene_detection=USE_SCENE_DETECTION,
        )
        ext_elapsed = time.time() - ext_start
        log_stage(job_id, "extract", f"done in {ext_elapsed:.1f}s — {len(keyframe_paths)} keyframes")
        custody_log.append(_custody_entry("extraction", f"Extracted audio + {len(keyframe_paths)} keyframes (parallel)"))

        # ── Stage 3: Transcribe ────────────────────────────────────────────
        _sync_status(job_id, "analyzing")
        log_stage(job_id, "transcribe", "starting STT transcription…")
        stt_start = time.time()
        transcript = soniox.transcribe(audio_path)
        stt_elapsed = time.time() - stt_start
        log_stage(job_id, "transcribe", f"done in {stt_elapsed:.1f}s — {len(transcript.tokens)} tokens, job={transcript.soniox_job_id}")
        custody_log.append(_custody_entry("soniox_stt", f"Transcribed {len(transcript.tokens)} tokens (job={transcript.soniox_job_id})"))

        # ── Stage 4: AI Analysis — Pass 1 (parallel visual + audio) ───────
        log_stage(job_id, "pass1", f"starting Gemini Pass 1 (parallel={USE_PARALLEL_PASS1})…")
        p1_start = time.time()
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
        p1_elapsed = time.time() - p1_start
        log_stage(job_id, "pass1", f"done in {p1_elapsed:.1f}s — {len(signals.phrases)} phrases, {len(signals.visual_markers)} markers")

        # ── Stage 5: AI Analysis — Pass 2 ─────────────────────────────────
        _sync_status(job_id, "aggregating")
        log_stage(job_id, "pass2", "starting Gemini Pass 2 (risk scoring)…")
        p2_start = time.time()
        scoring = gemini.pass2_score_risk(signals)
        p2_elapsed = time.time() - p2_start
        log_stage(job_id, "pass2", f"done in {p2_elapsed:.1f}s — risk_score={scoring.risk_score} confidence={scoring.confidence}")
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
        log_stage(job_id, "result", f"published — risk_score={scoring.risk_score} (publishing before PDF)")

        # ── Stage 7: Evidence Pack (async, non-blocking) ───────────────────
        if scoring.risk_score >= RISK_THRESHOLD:
            log_stage(job_id, "evidence", f"risk_score={scoring.risk_score} >= {RISK_THRESHOLD}, generating PDF…")

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
                    if evidence_url:
                        _patch_evidence_url(job_id, evidence_url)
                    log_stage(job_id, "evidence", f"PDF done — evidence={evidence_url}")
                except Exception as e:
                    log_stage(job_id, "evidence", f"PDF generation failed: {e}", "error")

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

        elapsed = time.time() - start_time
        log_stage(job_id, "done", f"completed in {elapsed:.1f}s (risk_score={scoring.risk_score})")

    except Exception as e:
        elapsed = time.time() - start_time
        stage = "unknown"
        log_stage(job_id, "ERROR", f"failed after {elapsed:.1f}s at stage={stage}: {e}", "error")
        logger.error(traceback.format_exc())
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
    logger.info("=" * 60)
    logger.info("AI Media Watch — Media Worker Starting")
    logger.info("=" * 60)

    try:
        Config.validate()
    except Exception as e:
        logger.error(f"Config validation failed: {e}")
        sys.exit(1)

    # Import components with error reporting
    try:
        components = _import_components()
        logger.info("All pipeline components imported successfully")
    except ImportError as e:
        logger.error(f"Failed to import pipeline components: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

    # Initialize components
    try:
        consumer = components["consumer_cls"]()
        producer = components["producer_cls"]()
        downloader = components["downloader"]()
        gemini = components["gemini"]()
        soniox = components["soniox"]()
        pdf_gen = components["pdf_gen"]()
        cache = components["cache_cls"]()
        ffmpeg = components["ffmpeg"]
        logger.info("All pipeline components initialized")
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

    # Graceful shutdown
    running = True
    def _shutdown(sig, frame):
        nonlocal running
        logger.info(f"Shutdown signal received (signal={sig}). Draining…")
        running = False

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info(f"MOCK_MODE={Config.IS_MOCK_MODE}")
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    # ── Always enter Kafka poll loop (mock mode uses mock AI responses) ──────
    logger.info("Entering Kafka poll loop…")
    poll_count = 0
    last_heartbeat = time.time()
    HEARTBEAT_INTERVAL = 30  # seconds

    while running:
        try:
            job = consumer.poll(timeout_s=5.0)
            if job:
                poll_count += 1
                logger.info(f"Job received from Kafka: {job.get('job_id', 'unknown')}")
                process_job(job, downloader, gemini, soniox, pdf_gen, producer, ffmpeg, cache)
                last_heartbeat = time.time()
            else:
                # Heartbeat log every 30s when idle
                if time.time() - last_heartbeat > HEARTBEAT_INTERVAL:
                    logger.info(f"[HEARTBEAT] Worker alive. Polling… (processed {poll_count} jobs total)")
                    last_heartbeat = time.time()
                time.sleep(0.1)
        except Exception as e:
            logger.error(f"Unhandled error in poll loop: {e}")
            logger.error(traceback.format_exc())
            time.sleep(2)

    # Cleanup
    logger.info("Shutting down…")
    soniox.close()
    producer.close()
    consumer.close()
    logger.info(f"Shutdown complete. Processed {poll_count} jobs in this session.")


if __name__ == "__main__":
    main()
