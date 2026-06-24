"""
Soniox Speech-to-Text Client
Supports KZ/RU code-switched transcription.
Fallback chain: Soniox → Groq → Whisper (local)
"""
import logging
from typing import Optional

from pydantic import BaseModel, Field

from src.config import Config

logger = logging.getLogger("media-worker")


class TranscriptToken(BaseModel):
    text: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    language: Optional[str] = None


class TranscriptResult(BaseModel):
    text: str
    tokens: list[TranscriptToken]
    soniox_job_id: str


class SonioxClient:
    def __init__(self):
        self._client = None
        self._groq_client = None
        self._whisper_client = None
        if getattr(Config, "HAS_SONIOX", False):
            try:
                from soniox import SonioxClient as _SonioxClient
                self._client = _SonioxClient()
            except ImportError:
                logger.warning("[WARN] soniox package not installed. Will use fallback STT provider if available.")

    def _fallback_transcribe(self, audio_path: str) -> TranscriptResult:
        # Layer 1: Groq API
        if self._groq_client is None and getattr(Config, "HAS_GROQ_STT", False):
            try:
                from src.analyzer.groq_client import GroqClient
                self._groq_client = GroqClient()
            except Exception as e:
                logger.warning(f"[Groq STT] Client init failed: {e}")

        if self._groq_client is not None and self._groq_client.is_available():
            try:
                return self._groq_client.transcribe(audio_path)
            except Exception as e:
                logger.warning(f"[Groq STT] API call failed: {e}")

        # Layer 2: Local Whisper (no API key needed)
        if self._whisper_client is None:
            try:
                from src.analyzer.whisper_client import WhisperClient
                self._whisper_client = WhisperClient()
            except Exception as e:
                logger.warning(f"[Whisper] Client init failed: {e}")

        if self._whisper_client is not None:
            wt = self._whisper_client.transcribe(audio_path)
            return TranscriptResult(
                text=wt.text,
                tokens=[
                    TranscriptToken(
                        text=t.text,
                        start_ms=t.start_ms,
                        end_ms=t.end_ms,
                        confidence=t.confidence,
                        language=t.language,
                    )
                    for t in wt.tokens
                ],
                soniox_job_id=f"whisper-{wt.whisper_model}",
            )

        # All STT providers exhausted
        raise RuntimeError("No STT provider available (Soniox, Groq, and local Whisper all failed)")

    def transcribe(self, audio_path: str) -> TranscriptResult:
        """
        Transcribes the given audio file using Soniox API.
        Returns a TranscriptResult with full text and per-token timestamps.
        """
        if self._client is None:
            return self._fallback_transcribe(audio_path)

        logger.info(f"[Soniox] Transcribing audio: {audio_path}")
        try:
            transcript = self._client.stt.transcribe_and_wait_with_tokens(
                file=audio_path,
                delete_after=True,
            )

            tokens = [
                TranscriptToken(
                    text=t.text,
                    start_ms=getattr(t, "start_ms", 0),
                    end_ms=getattr(t, "end_ms", 0),
                    confidence=getattr(t, "confidence", None),
                    language=getattr(t, "language", None),
                )
                for t in (transcript.tokens or [])
            ]

            full_text = " ".join(t.text for t in tokens if t.text.strip())
            job_id = getattr(transcript, "id", "soniox-unknown")

            return TranscriptResult(
                text=full_text,
                tokens=tokens,
                soniox_job_id=str(job_id),
            )

        except Exception as e:
            logger.warning(f"[Soniox] API call failed: {e}. Falling back to Groq or mock transcript.")
            return self._fallback_transcribe(audio_path)

    def close(self):
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
