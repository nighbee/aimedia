"""
Soniox Speech-to-Text Client
Supports KZ/RU code-switched transcription.
Fallback chain: Soniox → Groq → Whisper (local) → Mock
"""
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from src.config import Config


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
                print("[WARN] soniox package not installed. Will use fallback STT provider if available.")

    def _fallback_transcribe(self, audio_path: str) -> TranscriptResult:
        # Layer 1: Groq API
        if self._groq_client is None and getattr(Config, "HAS_GROQ_STT", False):
            try:
                from src.analyzer.groq_client import GroqClient
                self._groq_client = GroqClient()
            except Exception as e:
                print(f"[Groq STT] Client init failed: {e}")

        if self._groq_client is not None and self._groq_client.is_available():
            try:
                return self._groq_client.transcribe(audio_path)
            except Exception as e:
                print(f"[Groq STT] API call failed: {e}")

        # Layer 2: Local Whisper (no API key needed)
        if self._whisper_client is None:
            try:
                from src.analyzer.whisper_client import WhisperClient
                self._whisper_client = WhisperClient()
            except Exception as e:
                print(f"[Whisper] Client init failed: {e}")

        if self._whisper_client is not None:
            try:
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
            except Exception as e:
                print(f"[Whisper] Local transcription failed: {e}")

        # Layer 3: Mock (last resort)
        return self._mock_transcription(audio_path)

    def transcribe(self, audio_path: str) -> TranscriptResult:
        """
        Transcribes the given audio file using Soniox API.
        Returns a TranscriptResult with full text and per-token timestamps.
        """
        if self._client is None:
            return self._fallback_transcribe(audio_path)

        print(f"[Soniox] Transcribing audio: {audio_path}")
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
            print(f"[Soniox] API call failed: {e}. Falling back to Groq or mock transcript.")
            return self._fallback_transcribe(audio_path)

    def close(self):
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass

    @staticmethod
    def _mock_transcription(audio_path: str) -> TranscriptResult:
        print(f"[MOCK] Generating mock transcript for: {audio_path}")
        mock_tokens = [
            TranscriptToken(text="Сіздің", start_ms=0, end_ms=500, confidence=0.95, language="kk"),
            TranscriptToken(text="инвестицияңыз", start_ms=500, end_ms=1200, confidence=0.93, language="kk"),
            TranscriptToken(text="100%", start_ms=1200, end_ms=1600, confidence=0.98, language="kk"),
            TranscriptToken(text="кірісті", start_ms=1600, end_ms=2100, confidence=0.91, language="kk"),
            TranscriptToken(text="қамтамасыз", start_ms=2100, end_ms=2700, confidence=0.89, language="kk"),
            TranscriptToken(text="етеді", start_ms=2700, end_ms=3000, confidence=0.94, language="kk"),
            TranscriptToken(text="Переходи", start_ms=3000, end_ms=3500, confidence=0.96, language="ru"),
            TranscriptToken(text="по", start_ms=3500, end_ms=3700, confidence=0.97, language="ru"),
            TranscriptToken(text="ссылке", start_ms=3700, end_ms=4200, confidence=0.95, language="ru"),
            TranscriptToken(text="и", start_ms=4200, end_ms=4400, confidence=0.98, language="ru"),
            TranscriptToken(text="получи", start_ms=4400, end_ms=4900, confidence=0.95, language="ru"),
            TranscriptToken(text="бонус", start_ms=4900, end_ms=5400, confidence=0.94, language="ru"),
        ]
        full_text = " ".join(t.text for t in mock_tokens)
        return TranscriptResult(
            text=full_text,
            tokens=mock_tokens,
            soniox_job_id="mock-soniox-job-001",
        )
