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
import os
import shutil
import signal
import sys
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

RISK_THRESHOLD = Config.EVIDENCE_RISK_THRESHOLD
WORK_DIR = Path(Config.TMP_DIR)


# ─── Status Sync ───────────────────────────────────────────────────────────────

def _sync_status(job_id: str, status: str, failed_at_stage: Optional[str] = None):
    """PATCH the Go API Gateway internal endpoint to update job status."""
    if Config.IS_MOCK_MODE:
        stage_info = f" (failed_at={failed_at_stage})" if failed_at_stage else ""
        print(f"[MOCK Status Sync] {job_id} → {status}{stage_info}")
        return

    url = f"{Config.GO_API_BASE_URL}/internal/v1/jobs/{job_id}/status"
    headers = {
        "Authorization": f"Bearer {Config.GO_API_INTERNAL_TOKEN}",
        "Content-Type": "application/json",
    }
    body = {"status": status}
    try:
        resp = requests.patch(url, json=body, headers=headers, timeout=10)
        resp.raise_for_status()
        print(f"[Status Sync] {job_id} → {status} OK")
    except Exception as e:
        print(f"[Status Sync] Could not PATCH {url}: {e}")


def _custody_entry(stage: str, status: str = "OK") -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stage": stage,
        "status": status,
    }


# ─── Pipeline ──────────────────────────────────────────────────────────────────

def process_job(
    job: dict,
    downloader: VideoDownloader,
    gemini: GeminiClient,
    soniox: SonioxClient,
    pdf_gen: EvidencePackGenerator,
    producer: JobProducer,
) -> None:
    job_id = job["job_id"]
    url = job["url"]
    platform = job.get("platform", "unknown")
    inspector_id = job.get("inspector_id", "system")

    job_dir = WORK_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    video_path = str(job_dir / "source.mp4")
    audio_path = str(job_dir / "audio.mp3")
    frames_dir = str(job_dir / "frames")

    custody_log: list[dict] = [_custody_entry("ingestion", "Job received from Kafka")]

    try:
        # ── Stage 1: Download ──────────────────────────────────────────────────
        _sync_status(job_id, "downloading")
        print(f"\n{'='*60}")
        print(f"[Pipeline] START job={job_id} url={url}")
        downloader.download(url, video_path)
        custody_log.append(_custody_entry("download", "Video downloaded via yt-dlp"))

        # ── Stage 2: Extract ──────────────────────────────────────────────────
        _sync_status(job_id, "extracting")
        FFmpegProcessor.extract_audio(video_path, audio_path)
        keyframe_paths = FFmpegProcessor.extract_keyframes(video_path, frames_dir)
        custody_log.append(_custody_entry("extraction", f"Extracted audio + {len(keyframe_paths)} keyframes via FFmpeg"))

        # ── Stage 3: Transcribe ───────────────────────────────────────────────
        _sync_status(job_id, "analyzing")
        transcript = soniox.transcribe(audio_path)
        custody_log.append(_custody_entry("soniox_stt", f"Transcribed {len(transcript.tokens)} tokens (job={transcript.soniox_job_id})"))

        # ── Stage 4: AI Analysis — Pass 1 ────────────────────────────────────
        signals = gemini.pass1_extract_signals(
            transcript_text=transcript.text,
            keyframe_paths=keyframe_paths,
        )
        custody_log.append(_custody_entry("gemini_pass1", f"Extracted {len(signals.phrases)} phrases, {len(signals.visual_markers)} visual markers"))

        # ── Stage 5: AI Analysis — Pass 2 ────────────────────────────────────
        _sync_status(job_id, "aggregating")
        scoring = gemini.pass2_score_risk(signals)
        custody_log.append(_custody_entry("gemini_pass2", f"Risk score={scoring.risk_score}, confidence={scoring.confidence}"))

        # ── Stage 6: Evidence Pack (conditional) ──────────────────────────────
        evidence_url: Optional[str] = None
        if scoring.risk_score >= RISK_THRESHOLD:
            _sync_status(job_id, "generating_evidence")
            custody_log.append(_custody_entry("evidence_pack", "Generating PDF — risk >= 70"))
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
            custody_log.append(_custody_entry("evidence_pack", f"PDF stored → {(evidence_url or 'FAILED')[:60]}"))

        # ── Publish completed ─────────────────────────────────────────────────
        producer.publish_completed(
            job_id=job_id,
            risk_score=scoring.risk_score,
            confidence=scoring.confidence,
            reasoning=scoring.reasoning,
            categories=scoring.categories,
            top_flags=scoring.top_flags,
            evidence_url=evidence_url,
        )
        _sync_status(job_id, "completed")
        print(f"[Pipeline] DONE  job={job_id} risk_score={scoring.risk_score} evidence={'yes' if evidence_url else 'no'}")

    except Exception as e:
        stage = "unknown"
        print(f"[Pipeline] ERROR job={job_id}: {e}")
        custody_log.append(_custody_entry(stage, f"FAILED: {e}"))
        producer.publish_failed(job_id=job_id, stage=stage, error=str(e))
        _sync_status(job_id, "failed", failed_at_stage=stage)

    finally:
        # Always clean up temp files
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

    # ── Mock mode: process one synthetic job then exit ────────────────────────
    if Config.IS_MOCK_MODE:
        print("[MOCK] Running single mock job to verify pipeline …\n")
        mock_job = {
            "job_id": "mock-job-00000000",
            "url": "https://www.tiktok.com/@example/video/7123456789",
            "platform": "tiktok",
            "priority": 2,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "inspector_id": "inspector-mock-001",
        }
        process_job(mock_job, downloader, gemini, soniox, pdf_gen, producer)
        print("\n[MOCK] Pipeline verification complete.")
        return

    # ── Live mode: continuous Kafka loop ──────────────────────────────────────
    print("[Main] Entering Kafka poll loop …")
    while running:
        try:
            job = consumer.poll(timeout_s=5.0)
            if job:
                process_job(job, downloader, gemini, soniox, pdf_gen, producer)
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
