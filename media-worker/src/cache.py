"""
Content-hash cache for skipping redundant downloads and analysis.

Stores a mapping of URL hash → result summary. On cache hit, the entire
pipeline (download, extract, transcribe, analyze) is skipped.
"""
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional

from src.config import Config


class ContentCache:
    def __init__(self, cache_dir: str = None):
        self._cache_dir = Path(cache_dir or os.path.join(Config.TMP_DIR, ".cache"))
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._cache_dir / "index.json"
        self._index: dict[str, dict] = self._load_index()

    def _load_index(self) -> dict:
        if self._index_path.exists():
            try:
                return json.loads(self._index_path.read_text())
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_index(self):
        try:
            self._index_path.write_text(json.dumps(self._index, indent=2))
        except OSError as e:
            print(f"[Cache] Failed to save index: {e}")

    @staticmethod
    def _url_hash(url: str) -> str:
        normalized = url.strip().lower()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def get(self, url: str) -> Optional[dict]:
        key = self._url_hash(url)
        entry = self._index.get(key)
        if not entry:
            return None

        ttl_hours = 24
        created = entry.get("created_at", 0)
        if time.time() - created > ttl_hours * 3600:
            del self._index[key]
            self._save_index()
            print(f"[Cache] Expired entry for {url[:60]}...")
            return None

        print(f"[Cache] HIT for {url[:60]}... (age {int((time.time() - created) / 60)}min)")
        return entry.get("result")

    def put(self, url: str, result: dict):
        key = self._url_hash(url)
        self._index[key] = {
            "url": url,
            "result": result,
            "created_at": time.time(),
        }
        self._save_index()
        print(f"[Cache] Stored result for {url[:60]}...")

    def clear(self):
        self._index.clear()
        self._save_index()
        print("[Cache] Cleared all entries")
