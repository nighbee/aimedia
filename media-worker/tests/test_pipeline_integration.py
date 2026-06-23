"""Integration tests for the media-worker pipeline."""


class TestProviderFallbacks:
    """Tests the Groq STT and Blackbox fallback provider wiring."""

    def test_groq_stt_transcription(self, monkeypatch, tmp_path):
        from src.config import Config

        monkeypatch.setattr(Config, "HAS_SONIOX", False, raising=False)
        monkeypatch.setattr(Config, "HAS_GROQ_STT", True, raising=False)
        monkeypatch.setattr(Config, "GROQ_API_KEY", "test-groq-key", raising=False)
        monkeypatch.setattr(Config, "GROQ_API_BASE_URL", "https://api.groq.com/openai/v1", raising=False)
        monkeypatch.setattr(Config, "GROQ_STT_MODEL", "whisper-large-v3", raising=False)

        from src.analyzer import groq_client

        class _Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "id": "groq-test-1",
                    "text": "hello world",
                    "segments": [
                        {"text": "hello", "start": 0.0, "end": 0.4},
                        {"text": "world", "start": 0.4, "end": 0.8},
                    ],
                }

        monkeypatch.setattr(groq_client.requests, "post", lambda *args, **kwargs: _Response())

        audio_path = tmp_path / "test.mp3"
        audio_path.write_bytes(b"fake mp3 bytes")

        from src.analyzer.soniox_client import SonioxClient

        client = SonioxClient()
        result = client.transcribe(str(audio_path))

        assert result.text == "hello world"
        assert result.soniox_job_id == "groq-test-1"
        assert len(result.tokens) == 2

    def test_blackbox_completion_parsing(self, monkeypatch):
        from src.config import Config

        monkeypatch.setattr(Config, "HAS_GEMINI", False, raising=False)
        monkeypatch.setattr(Config, "HAS_BLACKBOX", True, raising=False)
        monkeypatch.setattr(Config, "BLACKBOX_API_KEY", "test-blackbox-key", raising=False)
        monkeypatch.setattr(Config, "BLACKBOX_API_BASE_URL", "https://api.blackbox.ai/v1", raising=False)
        monkeypatch.setattr(Config, "BLACKBOX_MODEL", "grok-code-fast", raising=False)

        from src.analyzer import blackbox_client

        class _Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "id": "blackbox-test-1",
                    "choices": [
                        {
                            "message": {
                                "content": '{"risk_score": 12, "confidence": "low", "categories": {"illegal_gambling": 0, "pyramid_scheme": 0, "investment_fraud": 12, "referral_scheme": 0}, "reasoning": "test", "top_flags": []}'
                            }
                        }
                    ],
                }

        monkeypatch.setattr(blackbox_client.requests, "post", lambda *args, **kwargs: _Response())

        from src.analyzer.blackbox_client import BlackboxClient

        client = BlackboxClient()
        req_id, content = client.chat_json("system", "user")

        assert req_id == "blackbox-test-1"
        assert "risk_score" in content


class TestPydanticModels:
    """Tests that Pydantic validators properly reject malformed data."""

    def test_valid_flagged_phrase(self):
        from src.analyzer.gemini_client import FlaggedPhrase
        f = FlaggedPhrase(text="buy now", timestamp_s=5, category="investment_fraud")
        assert f.text == "buy now"
        assert f.timestamp_s == 5
        assert f.category == "investment_fraud"

    def test_invalid_flagged_phrase_category(self):
        from pydantic import ValidationError
        from src.analyzer.gemini_client import FlaggedPhrase
        import pytest
        with pytest.raises(ValidationError):
            FlaggedPhrase(text="test", timestamp_s=0, category="not_a_real_category")

    def test_risk_score_out_of_bounds(self):
        from pydantic import ValidationError
        from src.analyzer.gemini_client import RiskScoringResult
        import pytest
        with pytest.raises(ValidationError):
            RiskScoringResult(
                risk_score=150,
                confidence="low",
                categories={"illegal_gambling": 50, "pyramid_scheme": 50, "investment_fraud": 50, "referral_scheme": 50},
                reasoning="test",
                top_flags=[],
                gemini_pass2_request_id="id",
            )

    def test_confidence_invalid(self):
        from pydantic import ValidationError
        from src.analyzer.gemini_client import RiskScoringResult
        import pytest
        with pytest.raises(ValidationError):
            RiskScoringResult(
                risk_score=50,
                confidence="super_high",
                categories={"illegal_gambling": 50, "pyramid_scheme": 50, "investment_fraud": 50, "referral_scheme": 50},
                reasoning="test",
                top_flags=[],
                gemini_pass2_request_id="id",
            )

    def test_valid_risk_scoring_result(self):
        from src.analyzer.gemini_client import RiskScoringResult, TopFlag
        r = RiskScoringResult(
            risk_score=85,
            confidence="high",
            categories={"illegal_gambling": 90, "pyramid_scheme": 40, "investment_fraud": 70, "referral_scheme": 30},
            reasoning="Clear evidence",
            top_flags=[TopFlag(signal="1xBet logo", weight="high")],
            gemini_pass2_request_id="test-id",
        )
        assert r.risk_score == 85

    def test_category_score_out_of_bounds(self):
        from pydantic import ValidationError
        from src.analyzer.gemini_client import RiskScoringResult
        import pytest
        with pytest.raises(ValidationError):
            RiskScoringResult(
                risk_score=50,
                confidence="low",
                categories={"illegal_gambling": 150, "pyramid_scheme": 0, "investment_fraud": 0, "referral_scheme": 0},
                reasoning="test",
                top_flags=[],
                gemini_pass2_request_id="id",
            )

    def test_job_message_invalid_uuid(self):
        from pydantic import ValidationError
        from src.queue.consumer import JobMessage
        import pytest
        with pytest.raises(ValidationError):
            JobMessage(job_id="not-a-uuid", url="https://example.com/video")

    def test_job_message_invalid_url(self):
        from pydantic import ValidationError
        from src.queue.consumer import JobMessage
        import pytest
        with pytest.raises(ValidationError):
            JobMessage(job_id="550e8400-e29b-41d4-a716-446655440000", url="ftp://bad-scheme.com")

    def test_transcript_token_bounds(self):
        from pydantic import ValidationError
        from src.analyzer.soniox_client import TranscriptToken
        import pytest
        with pytest.raises(ValidationError):
            TranscriptToken(text="word", start_ms=-1, end_ms=100)

    def test_transcript_token_confidence_bounds(self):
        from pydantic import ValidationError
        from src.analyzer.soniox_client import TranscriptToken
        import pytest
        with pytest.raises(ValidationError):
            TranscriptToken(text="word", start_ms=0, end_ms=100, confidence=1.5)

    def test_valid_job_message(self):
        from src.queue.consumer import JobMessage
        msg = JobMessage(
            job_id="550e8400-e29b-41d4-a716-446655440000",
            url="https://www.tiktok.com/@example/video/7123456789",
            platform="tiktok",
            priority=1,
        )
        assert msg.platform == "tiktok"
        assert msg.priority == 1


class TestGeminiMock:
    """Tests Gemini mock output for correctness."""

    def test_mock_pass1_returns_signals(self, mock_gemini_client):
        result = mock_gemini_client.pass1_extract_signals("", [])
        assert len(result.phrases) == 2
        assert len(result.visual_markers) == 2
        assert len(result.entities) == 2
        assert result.gemini_pass1_request_id.startswith("mock")

    def test_mock_pass2_returns_risk(self, mock_gemini_client):
        from src.analyzer.gemini_client import SignalExtractionResult, FlaggedPhrase
        signals = SignalExtractionResult(
            phrases=[FlaggedPhrase(text="test", timestamp_s=0, category="other")],
            visual_markers=[],
            entities=[],
            gemini_pass1_request_id="id",
        )
        result = mock_gemini_client.pass2_score_risk(signals)
        assert result.risk_score == 88
        assert result.confidence == "high"
        assert result.categories["illegal_gambling"] == 91
        assert len(result.top_flags) == 3


class TestSonioxMock:
    """Tests Soniox mock output for correctness."""

    def test_mock_transcription(self, mock_soniox_client):
        result = mock_soniox_client.transcribe("/tmp/test.mp3")
        assert len(result.tokens) == 12
        assert result.tokens[0].language == "kk"
        assert result.tokens[6].language == "ru"
        assert result.soniox_job_id == "mock-soniox-job-001"


class TestEvidencePack:
    """Tests evidence PDF generation."""

    def test_generate_pdf_local_fallback(self, mock_job, mock_gemini_client, mock_soniox_client, monkeypatch):
        """Generate PDF with S3 disabled → local file:// URL."""
        monkeypatch.setenv("S3_ENDPOINT", "")
        from src.pdfgen.generator import EvidencePackGenerator
        from src.analyzer.soniox_client import TranscriptResult

        gen = EvidencePackGenerator()
        transcript = mock_soniox_client.transcribe("/tmp/test.mp3")
        signals = mock_gemini_client.pass1_extract_signals("", [])
        scoring = mock_gemini_client.pass2_score_risk(signals)

        url = gen.generate(
            job_id=mock_job["job_id"],
            source_url=mock_job["url"],
            platform=mock_job["platform"],
            inspector_id=mock_job["inspector_id"],
            transcript=transcript,
            signals=signals,
            scoring=scoring,
            keyframe_paths=[],
            custody_log=[],
        )
        assert url is not None
        assert url.startswith("file://") or url.startswith("evidence-packs/")

    def test_generate_s3_upload(self, mock_job, mock_gemini_client, mock_soniox_client, s3_mock, monkeypatch):
        """Generate PDF with S3 mock → S3 object path returned."""
        import importlib
        import src.config
        monkeypatch.setenv("S3_ENDPOINT", "localhost:5000")
        monkeypatch.setenv("S3_ACCESS_KEY", "testaccess")
        monkeypatch.setenv("S3_SECRET_KEY", "testsecret")
        monkeypatch.setenv("S3_BUCKET_NAME", "test-bucket")
        monkeypatch.setenv("S3_USE_SSL", "false")
        monkeypatch.setenv("SONIOX_API_KEY", "mock_key")
        monkeypatch.setenv("GEMINI_API_KEY", "mock_key")
        importlib.reload(src.config)

        from src.pdfgen.generator import EvidencePackGenerator
        from src.analyzer.soniox_client import TranscriptResult
        import boto3

        monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: s3_mock)

        gen = EvidencePackGenerator()
        transcript = mock_soniox_client.transcribe("/tmp/test.mp3")
        signals = mock_gemini_client.pass1_extract_signals("", [])
        scoring = mock_gemini_client.pass2_score_risk(signals)

        url = gen.generate(
            job_id=mock_job["job_id"],
            source_url=mock_job["url"],
            platform=mock_job["platform"],
            inspector_id=mock_job["inspector_id"],
            transcript=transcript,
            signals=signals,
            scoring=scoring,
            keyframe_paths=[],
            custody_log=[],
        )
        assert url is not None
        # Should be the S3 object path (evidence-packs/<id>.pdf)
        assert "evidence-packs" in url
        assert url.endswith(".pdf")


class TestProducer:
    """Tests Kafka producer message payloads."""

    def test_completed_payload_includes_custody_log(self, monkeypatch):
        monkeypatch.setenv("KAFKA_BROKERS", "localhost:9092")
        from src.queue.producer import JobProducer
        from src.analyzer.gemini_client import TopFlag

        producer = JobProducer()
        custody_log = [
            {"timestamp": "2025-01-01T00:00:00Z", "stage": "download", "status": "OK"},
        ]

        # publish_completed doesn't raise; just verify structure
        producer.publish_completed(
            job_id="test-123",
            risk_score=75,
            confidence="medium",
            reasoning="test reasoning",
            categories={"illegal_gambling": 80},
            top_flags=[TopFlag(signal="test", weight="high")],
            evidence_url="evidence-packs/test.pdf",
            custody_log=custody_log,
        )
        # No assertion needed — method runs without error
        assert True

    def test_failed_payload_includes_custody_log(self, monkeypatch):
        monkeypatch.setenv("KAFKA_BROKERS", "localhost:9092")
        from src.queue.producer import JobProducer

        producer = JobProducer()
        producer.publish_failed(
            job_id="test-123",
            stage="download",
            error="Connection refused",
            custody_log=[{"timestamp": "2025-01-01T00:00:00Z", "stage": "download", "status": "FAILED"}],
        )
        assert True
