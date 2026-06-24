"""Groq speech-to-text fallback client.

Uses Groq's OpenAI-compatible transcription API when Soniox is unavailable.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import requests
from src.config import Config

logger = logging.getLogger("media-worker")


class GroqClient:
    def __init__(self):
        self._api_key = Config.GROQ_API_KEY
        self._base_url = Config.GROQ_API_BASE_URL.rstrip("/")
        self._model = Config.GROQ_STT_MODEL

    def is_available(self) -> bool:
        return bool(self._api_key and self._api_key != "mock_key")

    def transcribe(self, audio_path: str):
        from src.analyzer.soniox_client import TranscriptResult, TranscriptToken
        if not self.is_available():
            raise RuntimeError("Groq STT is not configured")

        path = Path(audio_path)
        headers = {"Authorization": f"Bearer {self._api_key}"}
        data = {
            "model": self._model,
            "temperature": "0",
            "response_format": "verbose_json",
            "timestamp_granularities[]": "segment",
        }

        logger.info(f"[Groq STT] Transcribing audio: {audio_path}")
        with path.open("rb") as audio_file:
            files = {"file": (path.name, audio_file, "audio/mpeg")}
            response = requests.post(
                f"{self._base_url}/audio/transcriptions",
                headers=headers,
                data=data,
                files=files,
                timeout=120,
            )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()

        segments = payload.get("segments") or []
        tokens = self._segments_to_tokens(segments)
        full_text = payload.get("text") or " ".join(token.text for token in tokens if token.text.strip())

        if not tokens and full_text:
            tokens = self._text_to_tokens(full_text)

        return TranscriptResult(
            text=full_text,
            tokens=tokens,
            soniox_job_id=str(payload.get("id") or payload.get("request_id") or "groq-stt-unknown"),
        )

    @staticmethod
    def _segments_to_tokens(segments: list[dict[str, Any]]) -> list[TranscriptToken]:
        from src.analyzer.soniox_client import TranscriptToken

        tokens: list[TranscriptToken] = []
        for segment in segments:
            text = str(segment.get("text", "")).strip()
            if not text:
                continue
            start_ms = int(float(segment.get("start", 0)) * 1000)
            end_ms = int(float(segment.get("end", 0)) * 1000)
            tokens.append(
                TranscriptToken(
                    text=text,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    confidence=segment.get("avg_logprob"),
                    language=segment.get("language"),
                )
            )
        return tokens

    @staticmethod
    def _text_to_tokens(text: str) -> list[TranscriptToken]:
        from src.analyzer.soniox_client import TranscriptToken

        tokens: list[TranscriptToken] = []
        words = [word for word in text.split() if word.strip()]
        for index, word in enumerate(words):
            start_ms = index * 400
            tokens.append(TranscriptToken(text=word, start_ms=start_ms, end_ms=start_ms + 350))
        return tokens