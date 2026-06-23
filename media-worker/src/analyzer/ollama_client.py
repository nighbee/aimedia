"""
Local Ollama LLM Client

Connects to a self-hosted Ollama server for local AI inference.
Uses OpenAI-compatible API — drop-in fallback for Gemini/Blackbox.

Recommended models for 4GB VM:
  qwen2.5:0.5b  — 400MB, fastest, basic quality
  qwen2.5:1.5b  — 1GB, good balance
  phi3:mini      — 2.3GB, best quality that fits in 4GB
"""
import json

import requests

from src.config import Config


class OllamaClient:
    def __init__(self):
        self._base_url = Config.OLLAMA_URL.rstrip("/")
        self._model = Config.OLLAMA_MODEL

    def is_available(self) -> bool:
        if not self._base_url:
            return False
        try:
            resp = requests.get(f"{self._base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def chat_json(self, system_prompt: str, user_prompt: str) -> tuple[str, str]:
        """Send a chat completion request to Ollama. Returns (request_id, json_content)."""
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "num_predict": 2048,
            },
        }

        print(f"[Ollama] Chat request using model={self._model}")
        resp = requests.post(
            f"{self._base_url}/api/chat",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        message = data.get("message", {})
        content = message.get("content", "{}")
        model = data.get("model", self._model)

        return f"ollama-{model}", content
