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
from pathlib import Path
from typing import Optional

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

    # ── Always enter Kafka poll loop (mock mode uses mock AI responses) ──────
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
