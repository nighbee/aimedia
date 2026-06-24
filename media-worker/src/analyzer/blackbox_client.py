"""Blackbox chat-completions fallback client.

Uses an OpenAI-compatible HTTP API for text-only fallback generation when the
primary LLM provider is unavailable.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from src.config import Config

logger = logging.getLogger("media-worker")


class BlackboxClient:
    def __init__(self):
        self._api_key = Config.BLACKBOX_API_KEY
        self._base_url = Config.BLACKBOX_API_BASE_URL.rstrip("/")
        self._model = Config.BLACKBOX_MODEL

    def is_available(self) -> bool:
        return bool(self._api_key and self._api_key != "mock_key")

    def chat_json(self, system_prompt: str, user_prompt: str) -> tuple[str, str]:
        if not self.is_available():
            raise RuntimeError("Blackbox is not configured")

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            #"response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        logger.info(f"[Blackbox] Chat completion request using model={self._model}")
        response = requests.post(
            f"{self._base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content") or "{}"
        request_id = str(data.get("id") or data.get("request_id") or "blackbox-unknown")
        return request_id, content