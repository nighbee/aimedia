"""Pytest fixtures for media-worker integration tests."""
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
def mock_gemini_client():
    """Return GeminiClient — mock mode is guaranteed via monkeypatch."""
    from src.analyzer.gemini_client import GeminiClient
    return GeminiClient()


@pytest.fixture
def mock_soniox_client():
    """Return SonioxClient — mock mode is guaranteed via monkeypatch."""
    from src.analyzer.soniox_client import SonioxClient
    return SonioxClient()
