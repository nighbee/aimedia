"""
Local Whisper STT Client (via faster-whisper)

Runs OpenAI Whisper model locally — no API key, no internet required.
Used as a fallback when Soniox and Groq are unavailable.

Model sizes:
  tiny   — 39 MB, fastest, lowest accuracy
  base   — 74 MB, good balance (recommended for 4GB VM)
  small  — 244 MB, better accuracy, slower on CPU
  medium — 769 MB, best accuracy, needs ~1.5GB RAM
"""
import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from src.config import Config

logger = logging.getLogger("media-worker")


class WhisperToken(BaseModel):
    text: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    language: Optional[str] = None


class WhisperTranscript(BaseModel):
    text: str
    tokens: list[WhisperToken]
    language: str
    whisper_model: str


class WhisperClient:
    def __init__(self):
        self._model = None
        self._model_size = Config.WHISPER_MODEL_SIZE

    def _ensure_model(self):
        if self._model is not None:
            return

        try:
            from faster_whisper import WhisperModel
            logger.info(f"[Whisper] Loading model '{self._model_size}' (first run may download)...")
            self._model = WhisperModel(
                self._model_size,
                device="cpu",
                compute_type="int8",
            )
            logger.info(f"[Whisper] Model loaded.")
        except ImportError:
            logger.warning("[WARN] faster-whisper not installed. Install with: pip install faster-whisper")
            raise
        except Exception as e:
            logger.warning(f"[Whisper] Failed to load model: {e}")
            raise

    def transcribe(self, audio_path: str) -> WhisperTranscript:
        """Transcribe audio file using local Whisper model."""
        self._ensure_model()

        logger.info(f"[Whisper] Transcribing: {audio_path}")
        segments, info = self._model.transcribe(
            audio_path,
            beam_size=5,
            language=None,
            vad_filter=True,
        )

        tokens = []
        full_text_parts = []
        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue
            start_ms = int(segment.start * 1000)
            end_ms = int(segment.end * 1000)
            avg_logprob = getattr(segment, "avg_logprob", None)
            confidence = None
            if avg_logprob is not None:
                import math
                confidence = min(1.0, max(0.0, math.exp(avg_logprob)))

            tokens.append(WhisperToken(
                text=text,
                start_ms=start_ms,
                end_ms=end_ms,
                confidence=confidence,
                language=info.language,
            ))
            full_text_parts.append(text)

        full_text = " ".join(full_text_parts)
        detected_lang = info.language or "unknown"

        logger.info(f"[Whisper] Done: {len(tokens)} segments, language={detected_lang}")
        return WhisperTranscript(
            text=full_text,
            tokens=tokens,
            language=detected_lang,
            whisper_model=self._model_size,
        )
