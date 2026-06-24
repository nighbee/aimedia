"""Pytest fixtures for media-worker integration tests."""
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config


@pytest.fixture(autouse=True)
def _mock_config(monkeypatch):
    """Patch environment variables so mock mode is reliably active during tests."""
    monkeypatch.setenv("SONIOX_API_KEY", "mock_key")
    monkeypatch.setenv("GROQ_API_KEY", "mock_key")
    monkeypatch.setenv("GEMINI_API_KEY", "mock_key")
    monkeypatch.setenv("BLACKBOX_API_KEY", "mock_key")
    monkeypatch.setenv("S3_ENDPOINT", "localhost:9000")
    monkeypatch.setenv("S3_ACCESS_KEY", "testaccess")
    monkeypatch.setenv("S3_SECRET_KEY", "testsecret")
    monkeypatch.setenv("S3_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("GO_API_BASE_URL", "http://localhost:8080")
    monkeypatch.setenv("GO_API_INTERNAL_TOKEN", "test-internal-token")
    monkeypatch.setenv("KAFKA_BROKERS", "localhost:9092")
    monkeypatch.setenv("TMP_DIR", "/tmp/mediawatch-jobs")
    # Reload Config after monkeypatching
    import importlib
    import src.config
    importlib.reload(src.config)


@pytest.fixture
def s3_mock():
    """Mock S3/MinIO with moto — returns a boto3 S3 client."""
    from moto import mock_aws
    import boto3

    with mock_aws():
        client = boto3.client(
            "s3",
            region_name="us-east-1",
            aws_access_key_id="testaccess",
            aws_secret_access_key="testsecret",
        )
        client.create_bucket(Bucket="test-bucket")
        yield client


@pytest.fixture
def mock_job():
    """Return a minimal valid job dict for testing."""
    return {
        "job_id": "test-job-000000001",
        "url": "https://www.tiktok.com/@example/video/7123456789",
        "platform": "tiktok",
        "priority": 2,
        "submitted_at": "2025-01-01T00:00:00Z",
        "inspector_id": "inspector-mock-001",
    }


@pytest.fixture
def mock_evidence_bytes():
    """Return realistic mock PDF bytes for evidence generation tests."""
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\nxref\n0 4\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n%%EOF"


@pytest.fixture
def mock_gemini_client(monkeypatch):
    """Return GeminiClient with a faked Gemini model call.

    The fixture sets _client to a non-None sentinel and monkeypatches
    _call_with_retry so it returns a canned JSON response that matches
    the expected output schemas.
    """
    from src.analyzer.gemini_client import GeminiClient
    import uuid

    PASS1_JSON = json.dumps({
        "phrases": [
            {"text": "guaranteed 100% income", "timestamp_s": 12, "category": "investment_fraud"},
            {"text": "переходи по реферальной ссылке", "timestamp_s": 34, "category": "referral_scheme"},
        ],
        "visual_markers": [
            {"frame_index": 7, "description": "1xBet logo overlay visible in top-right corner", "category": "illegal_gambling"},
            {"frame_index": 14, "description": "Aggressive call-to-action banner with phone number", "category": "referral_scheme"},
        ],
        "entities": [
            {"name": "1xBet", "type": "brand"},
            {"name": "@finance_guru", "type": "person"},
        ],
    })

    PASS2_JSON = json.dumps({
        "risk_score": 88,
        "confidence": "high",
        "categories": {
            "illegal_gambling": 91,
            "pyramid_scheme": 42,
            "investment_fraud": 65,
            "referral_scheme": 78,
        },
        "reasoning": "High risk (88/100). Soniox detected guaranteed income promise at 0:12. "
                     "Gemini identified 1xBet logo overlay at frame 7 and aggressive referral "
                     "call-to-action at frame 14.",
        "top_flags": [
            {"signal": "guaranteed income phrase at 0:12", "weight": "high"},
            {"signal": "1xBet logo frame 7", "weight": "high"},
            {"signal": "referral call-to-action frame 14", "weight": "medium"},
        ],
    })

    def fake_call_with_retry(system_prompt, contents):
        req_id = f"test-req-{uuid.uuid4().hex[:6]}"
        raw = PASS2_JSON if "fraud risk scorer" in system_prompt else PASS1_JSON
        return req_id, raw

    client = GeminiClient()
    monkeypatch.setattr(client, "_call_with_retry", fake_call_with_retry)
    monkeypatch.setattr(client, "_client", object())  # non-None to force Gemini path
    return client


@pytest.fixture
def mock_soniox_client():
    """Return SonioxClient — mock mode is guaranteed via monkeypatch."""
    from src.analyzer.soniox_client import SonioxClient
    return SonioxClient()
