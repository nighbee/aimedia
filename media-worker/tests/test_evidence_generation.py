"""Tests for evidence PDF generation integrity."""

import json
from unittest.mock import patch, MagicMock


class TestEvidenceTemplate:
    """Tests that the Jinja2 template renders without errors."""

    def test_template_renders_with_mock_data(self, mock_job, mock_gemini_client, mock_soniox_client, mock_evidence_bytes, monkeypatch):
        monkeypatch.setenv("S3_ENDPOINT", "")
        from src.pdfgen.generator import EvidencePackGenerator

        gen = EvidencePackGenerator()
        transcript = mock_soniox_client.transcribe("/tmp/test.mp3")
        signals = mock_gemini_client.pass1_extract_signals("", [])
        scoring = mock_gemini_client.pass2_score_risk(signals)

        with patch.object(gen, "_html_to_pdf", return_value=mock_evidence_bytes):
            url = gen.generate(
                job_id=mock_job["job_id"],
                source_url=mock_job["url"],
                platform=mock_job["platform"],
                inspector_id=mock_job["inspector_id"],
                transcript=transcript,
                signals=signals,
                scoring=scoring,
                keyframe_paths=[],
                custody_log=[
                    {"timestamp": "2025-01-01T00:00:00Z", "stage": "ingestion", "status": "OK"},
                    {"timestamp": "2025-01-01T00:01:00Z", "stage": "download", "status": "OK"},
                ],
            )
            assert url is not None
            assert url.startswith("file://") or "evidence-packs" in url

    def test_risk_tier_classification(self, mock_job, mock_gemini_client, mock_soniox_client, mock_evidence_bytes, monkeypatch):
        monkeypatch.setenv("S3_ENDPOINT", "")
        from src.pdfgen.generator import EvidencePackGenerator

        gen = EvidencePackGenerator()
        assert gen._risk_tier(85) == ("high", "High")
        assert gen._risk_tier(55) == ("medium", "Medium")
        assert gen._risk_tier(25) == ("low", "Low")
        assert gen._risk_tier(70) == ("high", "High")
        assert gen._risk_tier(40) == ("medium", "Medium")


class TestMockStatusServer:
    """Tests the mock HTTP server integration from main.py."""

    def test_mock_server_handles_patch(self, monkeypatch):
        import threading
        import requests
        import json

        monkeypatch.setenv("SONIOX_API_KEY", "mock_key")
        monkeypatch.setenv("GEMINI_API_KEY", "mock_key")
        monkeypatch.setenv("GO_API_BASE_URL", "http://localhost:9800")

        from src.main import _start_mock_server, _status_log

        _status_log.clear()
        port = 9800
        server = _start_mock_server(host="127.0.0.1", port=port)

        import time
        time.sleep(0.1)  # let server thread start

        try:
            resp = requests.patch(
                f"http://127.0.0.1:{port}/internal/v1/jobs/test-id/status",
                json={"status": "downloading"},
                headers={"Content-Type": "application/json"},
            )
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}

            assert "test-id" in _status_log
            assert _status_log["test-id"][0]["status"] == "downloading"
        finally:
            server.shutdown()
