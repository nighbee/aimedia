"""
Soniox Speech-to-Text Client
Supports KZ/RU code-switched transcription.
Falls back to mock data when SONIOX_API_KEY is not set.
"""
import os
from dataclasses import dataclass
from typing import Optional
from src.config import Config


@dataclass
class TranscriptToken:
    text: str
    start_ms: int
    end_ms: int
    confidence: Optional[float] = None
    language: Optional[str] = None


@dataclass
class TranscriptResult:
    text: str
    tokens: list[TranscriptToken]
    soniox_job_id: str


class SonioxClient:
    def __init__(self):
        self._client = None
        if not Config.IS_MOCK_MODE:
            try:
                from soniox import SonioxClient as _SonioxClient
                self._client = _SonioxClient()
            except ImportError:
                print("[WARN] soniox package not installed. Falling back to mock mode.")

    def transcribe(self, audio_path: str) -> TranscriptResult:
        """
        Transcribes the given audio file using Soniox API.
        Returns a TranscriptResult with full text and per-token timestamps.
        """
        if Config.IS_MOCK_MODE or self._client is None:
            return self._mock_transcription(audio_path)

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
            print(f"[Soniox] API call failed: {e}. Using mock transcript.")
            return self._mock_transcription(audio_path)

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
            TranscriptToken("Сіздің", 0, 500, 0.95, "kk"),
            TranscriptToken("инвестицияңыз", 500, 1200, 0.93, "kk"),
            TranscriptToken("100%", 1200, 1600, 0.98, "kk"),
            TranscriptToken("кірісті", 1600, 2100, 0.91, "kk"),
            TranscriptToken("қамтамасыз", 2100, 2700, 0.89, "kk"),
            TranscriptToken("етеді", 2700, 3000, 0.94, "kk"),
            TranscriptToken("Переходи", 3000, 3500, 0.96, "ru"),
            TranscriptToken("по", 3500, 3700, 0.97, "ru"),
            TranscriptToken("ссылке", 3700, 4200, 0.95, "ru"),
            TranscriptToken("и", 4200, 4400, 0.98, "ru"),
            TranscriptToken("получи", 4400, 4900, 0.95, "ru"),
            TranscriptToken("бонус", 4900, 5400, 0.94, "ru"),
        ]
        full_text = " ".join(t.text for t in mock_tokens)
        return TranscriptResult(
            text=full_text,
            tokens=mock_tokens,
            soniox_job_id="mock-soniox-job-001",
        )
