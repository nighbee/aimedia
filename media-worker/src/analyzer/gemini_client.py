"""
Gemini 2.0 Flash Two-Pass Analysis Client

Pass 1 — Signal Extraction:  keyframes + transcript  → fraud signals JSON
  - Split into parallel sub-calls: visual scan + audio scan
Pass 2 — Risk Scoring:       signals JSON            → risk score + categories JSON

Falls back to deterministic mock output when GEMINI_API_KEY is not set.
"""
import base64
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import BaseModel, Field, field_validator

from src.analyzer.blackbox_client import BlackboxClient
from src.config import Config

logger = logging.getLogger("media-worker")


# ─── Validated data models ─────────────────────────────────────────────────────

class FlaggedPhrase(BaseModel):
    text: str
    timestamp_s: int = Field(ge=0)
    category: str

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        allowed = {"illegal_gambling", "pyramid_scheme", "investment_fraud", "referral_scheme", "other"}
        if v not in allowed:
            raise ValueError(f"Invalid category: {v}. Must be one of {allowed}")
        return v


class VisualMarker(BaseModel):
    frame_index: int = Field(ge=0)
    description: str
    category: str

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        allowed = {"illegal_gambling", "pyramid_scheme", "investment_fraud", "referral_scheme", "other"}
        if v not in allowed:
            raise ValueError(f"Invalid category: {v}. Must be one of {allowed}")
        return v


class DetectedEntity(BaseModel):
    name: str
    entity_type: str  # brand | person | platform

    @field_validator("entity_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"brand", "person", "platform"}
        if v not in allowed:
            raise ValueError(f"Invalid entity_type: {v}. Must be one of {allowed}")
        return v


class SignalExtractionResult(BaseModel):
    phrases: list[FlaggedPhrase]
    visual_markers: list[VisualMarker]
    entities: list[DetectedEntity]
    gemini_pass1_request_id: str


class TopFlag(BaseModel):
    signal: str
    weight: str  # high | medium | low

    @field_validator("weight")
    @classmethod
    def validate_weight(cls, v: str) -> str:
        allowed = {"high", "medium", "low"}
        if v not in allowed:
            raise ValueError(f"Invalid weight: {v}. Must be one of {allowed}")
        return v


class RiskScoringResult(BaseModel):
    risk_score: int = Field(ge=0, le=100)
    confidence: str  # low | medium | high
    categories: dict[str, int]
    reasoning: str
    top_flags: list[TopFlag]
    gemini_pass2_request_id: str

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: str) -> str:
        allowed = {"low", "medium", "high"}
        if v not in allowed:
            raise ValueError(f"Invalid confidence: {v}. Must be one of {allowed}")
        return v

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, v: dict[str, int]) -> dict[str, int]:
        allowed = {"illegal_gambling", "pyramid_scheme", "investment_fraud", "referral_scheme"}
        for key, score in v.items():
            if key not in allowed:
                raise ValueError(f"Invalid category key: {key}. Must be one of {allowed}")
            if not (0 <= score <= 100):
                raise ValueError(f"Category {key} score out of range [0, 100]: {score}")
        return v


# ─── Client ────────────────────────────────────────────────────────────────────

class GeminiClient:
    PASS1_SYSTEM_PROMPT = """You are a fraud-signal extractor. Given video keyframes and a transcript, identify and return ONLY a JSON object with no preamble or markdown.
Schema:
{
  "phrases": [{"text": str, "timestamp_s": int, "category": str}],
  "visual_markers": [{"frame_index": int, "description": str, "category": str}],
  "entities": [{"name": str, "type": "brand|person|platform"}]
}
Categories: illegal_gambling | pyramid_scheme | investment_fraud | referral_scheme | other
If nothing suspicious is found, return empty arrays."""

    PASS2_SYSTEM_PROMPT = """You are a fraud risk scorer. Given extracted fraud signals, return ONLY JSON with no preamble or markdown.
Schema:
{
  "risk_score": int (0-100),
  "confidence": "low"|"medium"|"high",
  "categories": {
    "illegal_gambling": int,
    "pyramid_scheme": int,
    "investment_fraud": int,
    "referral_scheme": int
  },
  "reasoning": str,
  "top_flags": [{"signal": str, "weight": "high"|"medium"|"low"}]
}
Score 0 if no evidence. Score 70+ only for clear, direct violations."""

    def __init__(self):
        self._client = None
        self._blackbox_client = BlackboxClient()
        self._ollama_client = None
        if getattr(Config, "HAS_GEMINI", False):
            try:
                from google import genai
                self._client = genai.Client(api_key=Config.GEMINI_API_KEY)
                logger.info("[Gemini] Client initialized with API key")
            except ImportError:
                logger.warning("[WARN] google-genai package not installed. Will use fallback providers.")

    def _use_blackbox(self) -> bool:
        return self._blackbox_client.is_available()

    def _use_ollama(self) -> bool:
        if self._ollama_client is not None:
            return self._ollama_client.is_available()
        try:
            from src.analyzer.ollama_client import OllamaClient
            self._ollama_client = OllamaClient()
            return self._ollama_client.is_available()
        except Exception:
            return False

    def pass1_extract_signals(
        self,
        transcript_text: str,
        keyframe_paths: list[str],
    ) -> SignalExtractionResult:
        """Pass 1: extract fraud signals from keyframes + transcript."""
        if self._client is None and not self._use_blackbox() and not self._use_ollama():
            return self._mock_pass1()

        if self._client is None and self._use_blackbox():
            return self._blackbox_pass1(transcript_text, keyframe_paths)

        if self._client is None and self._use_ollama():
            return self._ollama_pass1(transcript_text, keyframe_paths)

        # Build content parts: images then transcript
        contents = self._build_image_parts(keyframe_paths)
        contents.append({
            "role": "user",
            "parts": [
                {"text": f"TRANSCRIPT:\n{transcript_text}\n\nExtract all fraud signals per the schema."}
            ]
        })

        try:
            req_id, raw = self._call_with_retry(self.PASS1_SYSTEM_PROMPT, contents)
        except Exception:
            logger.warning("[Gemini] Pass 1 all retries exhausted. Falling back to Blackbox, Ollama, or mock output.")
            if self._use_blackbox():
                return self._blackbox_pass1(transcript_text, keyframe_paths)
            if self._use_ollama():
                return self._ollama_pass1(transcript_text, keyframe_paths)
            return self._mock_pass1()

        data = self._parse_json(raw)

        phrases = [
            FlaggedPhrase(
                text=p.get("text", ""),
                timestamp_s=int(p.get("timestamp_s", 0)),
                category=p.get("category", "other"),
            )
            for p in data.get("phrases", [])
        ]
        visual_markers = [
            VisualMarker(
                frame_index=int(v.get("frame_index", 0)),
                description=v.get("description", ""),
                category=v.get("category", "other"),
            )
            for v in data.get("visual_markers", [])
        ]
        entities = [
            DetectedEntity(
                name=e.get("name", ""),
                entity_type=e.get("type", "brand"),
            )
            for e in data.get("entities", [])
        ]

        return SignalExtractionResult(
            phrases=phrases,
            visual_markers=visual_markers,
            entities=entities,
            gemini_pass1_request_id=req_id,
        )

    def pass1_extract_signals_parallel(
        self,
        transcript_text: str,
        keyframe_paths: list[str],
    ) -> SignalExtractionResult:
        """Pass 1 split into two parallel sub-calls: visual scan + audio scan."""
        if self._client is None and not self._use_blackbox() and not self._use_ollama():
            return self._mock_pass1()

        if self._client is None and self._use_blackbox():
            return self._blackbox_pass1(transcript_text, keyframe_paths)

        if self._client is None and self._use_ollama():
            return self._ollama_pass1(transcript_text, keyframe_paths)

        def _visual_scan() -> tuple[list[VisualMarker], list[DetectedEntity], str]:
            system_prompt = """You are a fraud-signal extractor. Given ONLY video keyframes (no transcript), identify suspicious visual elements and return ONLY JSON.
Schema:
{
  "visual_markers": [{"frame_index": int, "description": str, "category": str}],
  "entities": [{"name": str, "type": "brand|person|platform"}]
}
Categories: illegal_gambling | pyramid_scheme | investment_fraud | referral_scheme | other
If nothing suspicious is found, return empty arrays."""
            contents = self._build_image_parts(keyframe_paths)
            contents.append({
                "role": "user",
                "parts": [{"text": "Analyze these video keyframes for fraud-related visual signals. Return ONLY JSON."}]
            })

            try:
                req_id, raw = self._call_with_retry(system_prompt, contents)
            except Exception:
                logger.warning("[Gemini] Visual scan retries exhausted.")
                return [], [], "visual-scan-failed"

            data = self._parse_json(raw)
            markers = [
                VisualMarker(
                    frame_index=int(v.get("frame_index", 0)),
                    description=v.get("description", ""),
                    category=v.get("category", "other"),
                )
                for v in data.get("visual_markers", [])
            ]
            entities = [
                DetectedEntity(
                    name=e.get("name", ""),
                    entity_type=e.get("type", "brand"),
                )
                for e in data.get("entities", [])
            ]
            return markers, entities, req_id

        def _audio_scan() -> tuple[list[FlaggedPhrase], str]:
            system_prompt = """You are a fraud-signal extractor. Given ONLY a video transcript (no images), identify suspicious spoken phrases and return ONLY JSON.
Schema:
{
  "phrases": [{"text": str, "timestamp_s": int, "category": str}]
}
Categories: illegal_gambling | pyramid_scheme | investment_fraud | referral_scheme | other
If nothing suspicious is found, return empty phrases array."""
            contents = [{
                "role": "user",
                "parts": [{"text": f"TRANSCRIPT:\n{transcript_text}\n\nExtract fraud-related spoken phrases. Return ONLY JSON."}]
            }]

            try:
                req_id, raw = self._call_with_retry(system_prompt, contents)
            except Exception:
                logger.warning("[Gemini] Audio scan retries exhausted.")
                return [], "audio-scan-failed"

            data = self._parse_json(raw)
            phrases = [
                FlaggedPhrase(
                    text=p.get("text", ""),
                    timestamp_s=int(p.get("timestamp_s", 0)),
                    category=p.get("category", "other"),
                )
                for p in data.get("phrases", [])
            ]
            return phrases, req_id

        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="gemini-pass1") as pool:
            visual_future = pool.submit(_visual_scan)
            audio_future = pool.submit(_audio_scan)

            markers, entities, visual_req_id = visual_future.result()
            phrases, audio_req_id = audio_future.result()

        merged_req_id = f"v:{visual_req_id}+a:{audio_req_id}"
        logger.info(f"[Gemini] Parallel Pass 1 complete: {len(phrases)} phrases, {len(markers)} markers")

        return SignalExtractionResult(
            phrases=phrases,
            visual_markers=markers,
            entities=entities,
            gemini_pass1_request_id=merged_req_id,
        )

    def pass2_score_risk(self, signals: SignalExtractionResult) -> RiskScoringResult:
        """Pass 2: score risk from extracted signals."""
        if self._client is None and not self._use_blackbox() and not self._use_ollama():
            return self._mock_pass2()

        if self._client is None and self._use_blackbox():
            return self._blackbox_pass2(signals)

        if self._client is None and self._use_ollama():
            return self._ollama_pass2(signals)

        signals_payload = {
            "phrases": [{"text": p.text, "timestamp_s": p.timestamp_s, "category": p.category} for p in signals.phrases],
            "visual_markers": [{"frame_index": v.frame_index, "description": v.description, "category": v.category} for v in signals.visual_markers],
            "entities": [{"name": e.name, "type": e.entity_type} for e in signals.entities],
        }

        contents = [{
            "role": "user",
            "parts": [{"text": f"SIGNALS:\n{json.dumps(signals_payload, ensure_ascii=False)}\n\nScore the risk per the schema."}]
        }]

        try:
            req_id, raw = self._call_with_retry(self.PASS2_SYSTEM_PROMPT, contents)
        except Exception:
            logger.warning("[Gemini] Pass 2 all retries exhausted. Falling back to Blackbox, Ollama, or mock output.")
            if self._use_blackbox():
                return self._blackbox_pass2(signals)
            if self._use_ollama():
                return self._ollama_pass2(signals)
            return self._mock_pass2()

        data = self._parse_json(raw)

        top_flags = [
            TopFlag(signal=f.get("signal", ""), weight=f.get("weight", "low"))
            for f in data.get("top_flags", [])
        ]

        return RiskScoringResult(
            risk_score=int(data.get("risk_score", 0)),
            confidence=data.get("confidence", "low"),
            categories={
                "illegal_gambling": int(data.get("categories", {}).get("illegal_gambling", 0)),
                "pyramid_scheme": int(data.get("categories", {}).get("pyramid_scheme", 0)),
                "investment_fraud": int(data.get("categories", {}).get("investment_fraud", 0)),
                "referral_scheme": int(data.get("categories", {}).get("referral_scheme", 0)),
            },
            reasoning=data.get("reasoning", ""),
            top_flags=top_flags,
            gemini_pass2_request_id=req_id,
        )

    def _ollama_pass1(self, transcript_text: str, keyframe_paths: list[str]) -> SignalExtractionResult:
        user_prompt = (
            "TRANSCRIPT:\n"
            f"{transcript_text}\n\n"
            f"KEYFRAMES: {len(keyframe_paths)} image(s) available, but local LLM is text-only. "
            "Use the transcript to extract fraud signals. Return ONLY JSON."
        )
        req_id, raw = self._ollama_client.chat_json(self.PASS1_SYSTEM_PROMPT, user_prompt)
        data = self._parse_json(raw)
        phrases = [
            FlaggedPhrase(
                text=p.get("text", ""),
                timestamp_s=int(p.get("timestamp_s", 0)),
                category=p.get("category", "other"),
            )
            for p in data.get("phrases", [])
        ]
        visual_markers = [
            VisualMarker(
                frame_index=int(v.get("frame_index", 0)),
                description=v.get("description", ""),
                category=v.get("category", "other"),
            )
            for v in data.get("visual_markers", [])
        ]
        entities = [
            DetectedEntity(
                name=e.get("name", ""),
                entity_type=e.get("type", "brand"),
            )
            for e in data.get("entities", [])
        ]
        return SignalExtractionResult(
            phrases=phrases,
            visual_markers=visual_markers,
            entities=entities,
            gemini_pass1_request_id=req_id,
        )

    def _ollama_pass2(self, signals: SignalExtractionResult) -> RiskScoringResult:
        signals_payload = {
            "phrases": [{"text": p.text, "timestamp_s": p.timestamp_s, "category": p.category} for p in signals.phrases],
            "visual_markers": [{"frame_index": v.frame_index, "description": v.description, "category": v.category} for v in signals.visual_markers],
            "entities": [{"name": e.name, "type": e.entity_type} for e in signals.entities],
        }
        user_prompt = (
            f"SIGNALS:\n{json.dumps(signals_payload, ensure_ascii=False)}\n\n"
            "Score the risk per the schema and return ONLY JSON."
        )
        req_id, raw = self._ollama_client.chat_json(self.PASS2_SYSTEM_PROMPT, user_prompt)
        data = self._parse_json(raw)
        top_flags = [
            TopFlag(signal=f.get("signal", ""), weight=f.get("weight", "low"))
            for f in data.get("top_flags", [])
        ]
        return RiskScoringResult(
            risk_score=int(data.get("risk_score", 0)),
            confidence=data.get("confidence", "low"),
            categories={
                "illegal_gambling": int(data.get("categories", {}).get("illegal_gambling", 0)),
                "pyramid_scheme": int(data.get("categories", {}).get("pyramid_scheme", 0)),
                "investment_fraud": int(data.get("categories", {}).get("investment_fraud", 0)),
                "referral_scheme": int(data.get("categories", {}).get("referral_scheme", 0)),
            },
            reasoning=data.get("reasoning", ""),
            top_flags=top_flags,
            gemini_pass2_request_id=req_id,
        )

    def _call_with_retry(
        self,
        system_prompt: str,
        contents: list,
    ) -> tuple[str, str]:
        """Call Gemini API with exponential backoff. Returns (request_id, raw_text)."""
        from google.genai import types

        max_retries = Config.GEMINI_MAX_RETRIES
        base_backoff = Config.GEMINI_RETRY_BACKOFF_BASE_SECONDS
        last_error = None

        for attempt in range(max_retries):
            try:
                response = self._client.models.generate_content(
                    model=Config.GEMINI_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.1,
                        response_mime_type="application/json",
                    ),
                )
                req_id = getattr(response, "response_id", None) or f"gemini-req-{attempt}"
                return str(req_id), response.text
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait = base_backoff ** attempt
                    logger.info(f"[Gemini] API error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait}s …")
                    time.sleep(wait)
                else:
                    logger.error(f"[Gemini] All {max_retries} attempts exhausted. Last error: {e}")

        raise RuntimeError(f"Gemini API call failed after {max_retries} attempts") from last_error

    def _blackbox_pass1(self, transcript_text: str, keyframe_paths: list[str]) -> SignalExtractionResult:
        user_prompt = (
            "TRANSCRIPT:\n"
            f"{transcript_text}\n\n"
            f"KEYFRAMES: {len(keyframe_paths)} image(s) are available, but this fallback LLM is text-only. "
            "Use the transcript and any obvious textual clues to extract fraud signals. Return ONLY JSON."
        )
        req_id, raw = self._blackbox_client.chat_json(self.PASS1_SYSTEM_PROMPT, user_prompt)
        data = self._parse_json(raw)
        phrases = [
            FlaggedPhrase(
                text=p.get("text", ""),
                timestamp_s=int(p.get("timestamp_s", 0)),
                category=p.get("category", "other"),
            )
            for p in data.get("phrases", [])
        ]
        visual_markers = [
            VisualMarker(
                frame_index=int(v.get("frame_index", 0)),
                description=v.get("description", ""),
                category=v.get("category", "other"),
            )
            for v in data.get("visual_markers", [])
        ]
        entities = [
            DetectedEntity(
                name=e.get("name", ""),
                entity_type=e.get("type", "brand"),
            )
            for e in data.get("entities", [])
        ]
        return SignalExtractionResult(
            phrases=phrases,
            visual_markers=visual_markers,
            entities=entities,
            gemini_pass1_request_id=req_id,
        )

    def _blackbox_pass2(self, signals: SignalExtractionResult) -> RiskScoringResult:
        signals_payload = {
            "phrases": [{"text": p.text, "timestamp_s": p.timestamp_s, "category": p.category} for p in signals.phrases],
            "visual_markers": [{"frame_index": v.frame_index, "description": v.description, "category": v.category} for v in signals.visual_markers],
            "entities": [{"name": e.name, "type": e.entity_type} for e in signals.entities],
        }
        user_prompt = (
            f"SIGNALS:\n{json.dumps(signals_payload, ensure_ascii=False)}\n\n"
            "Score the risk per the schema and return ONLY JSON."
        )
        req_id, raw = self._blackbox_client.chat_json(self.PASS2_SYSTEM_PROMPT, user_prompt)
        data = self._parse_json(raw)
        top_flags = [
            TopFlag(signal=f.get("signal", ""), weight=f.get("weight", "low"))
            for f in data.get("top_flags", [])
        ]
        return RiskScoringResult(
            risk_score=int(data.get("risk_score", 0)),
            confidence=data.get("confidence", "low"),
            categories={
                "illegal_gambling": int(data.get("categories", {}).get("illegal_gambling", 0)),
                "pyramid_scheme": int(data.get("categories", {}).get("pyramid_scheme", 0)),
                "investment_fraud": int(data.get("categories", {}).get("investment_fraud", 0)),
                "referral_scheme": int(data.get("categories", {}).get("referral_scheme", 0)),
            },
            reasoning=data.get("reasoning", ""),
            top_flags=top_flags,
            gemini_pass2_request_id=req_id,
        )

    def _build_image_parts(self, keyframe_paths: list[str]) -> list:
        """Encode up to 20 keyframes as base64 inline images."""
        contents = [{"role": "user", "parts": []}]
        for path in keyframe_paths[:20]:
            if not os.path.exists(path):
                continue
            try:
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                contents[0]["parts"].append({
                    "inline_data": {"mime_type": "image/jpeg", "data": b64}
                })
            except Exception as e:
                logger.warning(f"[Gemini] Could not encode frame {path}: {e}")
        return contents

    @staticmethod
    def _parse_json(raw: str) -> dict:
        """Strip markdown fences and parse JSON."""
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning(f"[Gemini] JSON parse error: {e}. Raw: {raw[:200]}")
            return {}

    # ── Mock helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _mock_pass1() -> SignalExtractionResult:
        logger.info("[MOCK] Returning mock Pass-1 signal extraction result.")
        return SignalExtractionResult(
            phrases=[
                FlaggedPhrase(text="guaranteed 100% income", timestamp_s=12, category="investment_fraud"),
                FlaggedPhrase(text="переходи по реферальной ссылке", timestamp_s=34, category="referral_scheme"),
            ],
            visual_markers=[
                VisualMarker(frame_index=7, description="1xBet logo overlay visible in top-right corner", category="illegal_gambling"),
                VisualMarker(frame_index=14, description="Aggressive call-to-action banner with phone number", category="referral_scheme"),
            ],
            entities=[
                DetectedEntity(name="1xBet", entity_type="brand"),
                DetectedEntity(name="@finance_guru", entity_type="person"),
            ],
            gemini_pass1_request_id="mock-gemini-pass1-001",
        )

    @staticmethod
    def _mock_pass2() -> RiskScoringResult:
        logger.info("[MOCK] Returning mock Pass-2 risk scoring result.")
        return RiskScoringResult(
            risk_score=88,
            confidence="high",
            categories={
                "illegal_gambling": 91,
                "pyramid_scheme": 42,
                "investment_fraud": 65,
                "referral_scheme": 78,
            },
            reasoning=(
                "High risk (88/100). Soniox detected guaranteed income promise at 0:12. "
                "Gemini identified 1xBet logo overlay at frame 7 and aggressive referral "
                "call-to-action at frame 14."
            ),
            top_flags=[
                TopFlag(signal="guaranteed income phrase at 0:12", weight="high"),
                TopFlag(signal="1xBet logo frame 7", weight="high"),
                TopFlag(signal="referral call-to-action frame 14", weight="medium"),
            ],
            gemini_pass2_request_id="mock-gemini-pass2-001",
        )
