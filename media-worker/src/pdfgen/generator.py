"""
Evidence Pack PDF Generator

Renders a Jinja2 HTML template with embedded base64 keyframes,
then converts to PDF via WeasyPrint.

Storage:
  - If S3/MinIO is configured → uploads to bucket `evidence-packs/<job_id>.pdf`
    and returns the object path for the Go API to generate fresh presigned URLs.
  - Otherwise → saves locally to /tmp/evidence/<job_id>.pdf and returns a file:// URL
    (suitable for dev / hackathon environments).
"""
import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from src.analyzer.gemini_client import RiskScoringResult, SignalExtractionResult
from src.analyzer.soniox_client import TranscriptResult
from src.config import Config

TEMPLATE_DIR = Path(__file__).parent / "templates"


class EvidencePackGenerator:
    def __init__(self):
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=True,
        )

    def generate(
        self,
        job_id: str,
        source_url: str,
        platform: str,
        inspector_id: str,
        transcript: TranscriptResult,
        signals: SignalExtractionResult,
        scoring: RiskScoringResult,
        keyframe_paths: list[str],
        custody_log: list[dict],
    ) -> Optional[str]:
        """
        Render the evidence PDF and store it.
        Returns the download URL (GCS signed URL or local file path).
        Returns None if generation fails.
        """
        try:
            frames_b64 = self._encode_frames(keyframe_paths)
            risk_tier, risk_tier_label = self._risk_tier(scoring.risk_score)

            context = {
                "job_id": job_id,
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source_url": source_url,
                "platform": platform,
                "inspector_id": inspector_id,
                "risk_score": scoring.risk_score,
                "risk_tier": risk_tier,
                "risk_tier_label": risk_tier_label,
                "confidence": scoring.confidence,
                "reasoning": scoring.reasoning,
                "categories": scoring.categories,
                "top_flags": scoring.top_flags,
                "phrases": signals.phrases,
                "visual_markers": signals.visual_markers,
                "transcript_tokens": transcript.tokens,
                "frames_b64": frames_b64,
                "soniox_job_id": transcript.soniox_job_id,
                "gemini_pass1_request_id": signals.gemini_pass1_request_id,
                "gemini_pass2_request_id": scoring.gemini_pass2_request_id,
                "custody_log": custody_log,
            }

            html = self._jinja_env.get_template("evidence_report.html").render(**context)
            pdf_bytes = self._html_to_pdf(html)

            return self._store_pdf(job_id, pdf_bytes)

        except Exception as e:
            print(f"[EvidencePack] Generation failed for job {job_id}: {e}")
            return None

    # ── Private helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _encode_frames(keyframe_paths: list[str]) -> dict[int, str]:
        """Returns {frame_index: base64_string} for up to 20 keyframes."""
        encoded: dict[int, str] = {}
        for i, path in enumerate(keyframe_paths[:20]):
            try:
                with open(path, "rb") as f:
                    encoded[i + 1] = base64.b64encode(f.read()).decode()
            except Exception as e:
                print(f"[EvidencePack] Could not encode frame {path}: {e}")
        return encoded

    @staticmethod
    def _risk_tier(score: int) -> tuple[str, str]:
        if score >= 70:
            return "high", "High"
        if score >= 40:
            return "medium", "Medium"
        return "low", "Low"

    @staticmethod
    def _html_to_pdf(html: str) -> bytes:
        """Render HTML to PDF bytes using WeasyPrint."""
        try:
            from weasyprint import HTML
            return HTML(string=html).write_pdf()
        except ImportError:
            raise RuntimeError(
                "[EvidencePack] WeasyPrint not installed. Install with: pip install weasyprint"
            )
        except Exception as e:
            raise RuntimeError(f"[EvidencePack] WeasyPrint render error: {e}")

    @staticmethod
    def _store_pdf(job_id: str, pdf_bytes: bytes) -> str:
        """
        Upload to S3/MinIO if configured, otherwise save locally.
        Returns the S3 object path (e.g. "evidence-packs/<uuid>.pdf") so the Go API
        can generate a fresh presigned URL on each evidence download request.
        """
        endpoint = Config.S3_ENDPOINT
        access_key = Config.S3_ACCESS_KEY
        secret_key = Config.S3_SECRET_KEY
        bucket = Config.S3_BUCKET_NAME
        use_ssl = Config.S3_USE_SSL

        if endpoint and access_key and secret_key and bucket:
            try:
                import boto3
                from botocore.config import Config as BotoConfig

                protocol = "https" if use_ssl else "http"
                client = boto3.client(
                    "s3",
                    endpoint_url=f"{protocol}://{endpoint}",
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    config=BotoConfig(signature_version="s3v4"),
                )

                object_path = f"evidence-packs/{job_id}.pdf"
                client.put_object(
                    Bucket=bucket,
                    Key=object_path,
                    Body=pdf_bytes,
                    ContentType="application/pdf",
                )
                print(f"[EvidencePack] Uploaded to S3: {bucket}/{object_path}")
                return object_path
            except ImportError:
                print("[EvidencePack] boto3 not installed. Saving locally.")
            except Exception as e:
                print(f"[EvidencePack] S3 upload failed: {e}. Saving locally.")

        # Local fallback
        out_dir = Path("/tmp/evidence")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{job_id}.pdf"
        out_path.write_bytes(pdf_bytes)
        file_url = f"file://{out_path}"
        print(f"[EvidencePack] Saved locally: {file_url}")
        return file_url
