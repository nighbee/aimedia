"""
Local Ollama LLM Client

Connects to a self-hosted Ollama server for local AI inference.
Uses the /api/generate endpoint (broader compatibility across Ollama versions).

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
        """Send a completion request to Ollama. Returns (request_id, json_content).

        Uses /api/generate with system prompt embedded for broad compatibility
        across Ollama versions (the /api/chat endpoint was added in 0.1.32).
        """
        payload = {
            "model": self._model,
            "prompt": f"{system_prompt}\n\n{user_prompt}",
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "num_predict": 2048,
            },
            "system": system_prompt,
        }

        logger.info(f"[Ollama] Chat request using model={self._model}")
        resp = requests.post(
            f"{self._base_url}/api/generate",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        content = data.get("response", "{}")
        model = data.get("model", self._model)

        return f"ollama-{model}", content
