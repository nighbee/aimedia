"""
Gemini 2.0 Flash Two-Pass Analysis Client

Pass 1 — Signal Extraction:  keyframes + transcript  → fraud signals JSON
Pass 2 — Risk Scoring:       signals JSON            → risk score + categories JSON

Falls back to deterministic mock output when GEMINI_API_KEY is not set.
"""
import base64
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional

from src.config import Config


# ─── Pydantic-style data models ────────────────────────────────────────────────

@dataclass
class FlaggedPhrase:
    text: str
    timestamp_s: int
    category: str


@dataclass
class VisualMarker:
    frame_index: int
    description: str
    category: str


@dataclass
class DetectedEntity:
    name: str
    entity_type: str   # brand | person | platform


@dataclass
class SignalExtractionResult:
    phrases: list[FlaggedPhrase]
    visual_markers: list[VisualMarker]
    entities: list[DetectedEntity]
    gemini_pass1_request_id: str


@dataclass
class TopFlag:
    signal: str
    weight: str   # high | medium | low


@dataclass
class RiskScoringResult:
    risk_score: int
    confidence: str           # low | medium | high
    categories: dict[str, int]
    reasoning: str
    top_flags: list[TopFlag]
    gemini_pass2_request_id: str


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
        if not Config.IS_MOCK_MODE:
            try:
                from google import genai
                self._client = genai.Client(api_key=Config.GEMINI_API_KEY)
            except ImportError:
                print("[WARN] google-genai package not installed. Falling back to mock mode.")

    def pass1_extract_signals(
        self,
        transcript_text: str,
        keyframe_paths: list[str],
    ) -> SignalExtractionResult:
        """Pass 1: extract fraud signals from keyframes + transcript."""
        if Config.IS_MOCK_MODE or self._client is None:
            return self._mock_pass1()

        # Build content parts: images then transcript
        contents = self._build_image_parts(keyframe_paths)
        contents.append({
            "role": "user",
            "parts": [
                {"text": f"TRANSCRIPT:\n{transcript_text}\n\nExtract all fraud signals per the schema."}
            ]
        })

        req_id, raw = self._call_gemini(self.PASS1_SYSTEM_PROMPT, contents)
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

    def pass2_score_risk(self, signals: SignalExtractionResult) -> RiskScoringResult:
        """Pass 2: score risk from extracted signals."""
        if Config.IS_MOCK_MODE or self._client is None:
            return self._mock_pass2()

        signals_payload = {
            "phrases": [{"text": p.text, "timestamp_s": p.timestamp_s, "category": p.category} for p in signals.phrases],
            "visual_markers": [{"frame_index": v.frame_index, "description": v.description, "category": v.category} for v in signals.visual_markers],
            "entities": [{"name": e.name, "type": e.entity_type} for e in signals.entities],
        }

        contents = [{
            "role": "user",
            "parts": [{"text": f"SIGNALS:\n{json.dumps(signals_payload, ensure_ascii=False)}\n\nScore the risk per the schema."}]
        }]

        req_id, raw = self._call_gemini(self.PASS2_SYSTEM_PROMPT, contents)
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

    def _call_gemini(
        self,
        system_prompt: str,
        contents: list,
        retries: int = 3,
    ) -> tuple[str, str]:
        """Call the Gemini API with exponential backoff. Returns (request_id, raw_text)."""
        from google.genai import types

        for attempt in range(retries):
            try:
                response = self._client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.1,
                        response_mime_type="application/json",
                    ),
                )
                req_id = getattr(response, "metadata", {}).get("request_id", f"gemini-req-{attempt}")
                return str(req_id), response.text
            except Exception as e:
                wait = (2 ** attempt) + 0.5
                print(f"[Gemini] API error (attempt {attempt + 1}/{retries}): {e}. Retrying in {wait}s …")
                time.sleep(wait)

        print("[Gemini] All retries exhausted. Returning empty result.")
        return "gemini-failed", "{}"

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
                print(f"[Gemini] Could not encode frame {path}: {e}")
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
            print(f"[Gemini] JSON parse error: {e}. Raw: {raw[:200]}")
            return {}

    # ── Mock helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _mock_pass1() -> SignalExtractionResult:
        print("[MOCK] Returning mock Pass-1 signal extraction result.")
        return SignalExtractionResult(
            phrases=[
                FlaggedPhrase("guaranteed 100% income", 12, "investment_fraud"),
                FlaggedPhrase("переходи по реферальной ссылке", 34, "referral_scheme"),
            ],
            visual_markers=[
                VisualMarker(7, "1xBet logo overlay visible in top-right corner", "illegal_gambling"),
                VisualMarker(14, "Aggressive call-to-action banner with phone number", "referral_scheme"),
            ],
            entities=[
                DetectedEntity("1xBet", "brand"),
                DetectedEntity("@finance_guru", "person"),
            ],
            gemini_pass1_request_id="mock-gemini-pass1-001",
        )

    @staticmethod
    def _mock_pass2() -> RiskScoringResult:
        print("[MOCK] Returning mock Pass-2 risk scoring result.")
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
                TopFlag("guaranteed income phrase at 0:12", "high"),
                TopFlag("1xBet logo frame 7", "high"),
                TopFlag("referral call-to-action frame 14", "medium"),
            ],
            gemini_pass2_request_id="mock-gemini-pass2-001",
        )
