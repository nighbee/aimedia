import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Kafka
    KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "localhost:9092")
    KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "python-worker-consumer")
    KAFKA_TOPIC_JOB_CREATED = os.getenv("KAFKA_TOPIC_JOB_CREATED", "media.job.created")
    KAFKA_TOPIC_JOB_COMPLETED = os.getenv("KAFKA_TOPIC_JOB_COMPLETED", "media.job.completed")

    # Go API Gateway (for status sync)
    GO_API_BASE_URL = os.getenv("GO_API_BASE_URL", "http://localhost:8080").rstrip("/")
    GO_API_INTERNAL_TOKEN = os.getenv("GO_API_INTERNAL_TOKEN", "internal-service-token-change-me")

    # External AI APIs
    SONIOX_API_KEY = os.getenv("SONIOX_API_KEY", "")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_API_BASE_URL = os.getenv("GROQ_API_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
    GROQ_STT_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash-latest")
    BLACKBOX_API_KEY = os.getenv("BLACKBOX_API_KEY", "")
    BLACKBOX_API_BASE_URL = os.getenv("BLACKBOX_API_BASE_URL", "https://api.blackbox.ai/v1").rstrip("/")
    BLACKBOX_MODEL = os.getenv("BLACKBOX_MODEL", "grok-code-fast")

    # S3 / MinIO (evidence pack storage)
    S3_ENDPOINT = os.getenv("S3_ENDPOINT", "localhost:9000")
    S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
    S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadminpass")
    S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "evidence-packs")
    S3_USE_SSL = os.getenv("S3_USE_SSL", "false") == "true"

    # Cobalt API (self-hosted media downloader)
    COBALT_API_URL = os.getenv("COBALT_API_URL", "").rstrip("/")
    COBALT_API_KEY = os.getenv("COBALT_API_KEY", "")

    # Local AI — Ollama
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")

    # Local AI — Whisper
    WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")

    # yt-dlp cookies file (Netscape format)
    YTDLP_COOKIES_FILE = os.getenv("YTDLP_COOKIES_FILE", "")

    # Processing
    TMP_DIR = os.getenv("TMP_DIR", "/tmp/mediawatch-jobs")
    MAX_VIDEO_DURATION_SECONDS = int(os.getenv("MAX_VIDEO_DURATION_SECONDS", "600"))
    KEYFRAME_INTERVAL_SECONDS = int(os.getenv("KEYFRAME_INTERVAL_SECONDS", "3"))
    KEYFRAME_MAX_WIDTH_PX = int(os.getenv("KEYFRAME_MAX_WIDTH_PX", "800"))
    AUDIO_SAMPLE_RATE_HZ = int(os.getenv("AUDIO_SAMPLE_RATE_HZ", "16000"))
    EVIDENCE_RISK_THRESHOLD = int(os.getenv("EVIDENCE_RISK_THRESHOLD", "70"))

    # Gemini rate limiting
    GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
    GEMINI_RETRY_BACKOFF_BASE_SECONDS = int(os.getenv("GEMINI_RETRY_BACKOFF_BASE_SECONDS", "2"))

    # Pipeline optimizations
    USE_SCENE_DETECTION = os.getenv("USE_SCENE_DETECTION", "false").lower() == "true"
    USE_PARALLEL_PASS1 = os.getenv("USE_PARALLEL_PASS1", "true").lower() == "true"


def _has_provider(key: str) -> bool:
    return bool(key and key != "mock_key")


# Derived flags (computed at import time after all env vars are loaded)
Config.HAS_SONIOX = _has_provider(Config.SONIOX_API_KEY)
Config.HAS_GROQ = _has_provider(Config.GROQ_API_KEY)
Config.HAS_GEMINI = _has_provider(Config.GEMINI_API_KEY)
Config.HAS_BLACKBOX = _has_provider(Config.BLACKBOX_API_KEY)
Config.HAS_STT_PROVIDER = Config.HAS_SONIOX or Config.HAS_GROQ
Config.HAS_LLM_PROVIDER = Config.HAS_GEMINI or Config.HAS_BLACKBOX


def _validate():
    print("--- Config Validation ---")
    print(f"KAFKA_BROKERS: {Config.KAFKA_BROKERS}")
    print(f"KAFKA_GROUP_ID: {Config.KAFKA_GROUP_ID}")
    print(f"GO_API_BASE_URL: {Config.GO_API_BASE_URL}")
    print(f"GO_API_INTERNAL_TOKEN set: {bool(Config.GO_API_INTERNAL_TOKEN)}")
    print(f"SONIOX_API_KEY set: {bool(Config.SONIOX_API_KEY and Config.SONIOX_API_KEY != 'mock_key')}")
    print(f"GROQ_API_KEY set: {bool(Config.GROQ_API_KEY and Config.GROQ_API_KEY != 'mock_key')}")
    print(f"GEMINI_API_KEY set: {bool(Config.GEMINI_API_KEY and Config.GEMINI_API_KEY != 'mock_key')}")
    print(f"BLACKBOX_API_KEY set: {bool(Config.BLACKBOX_API_KEY and Config.BLACKBOX_API_KEY != 'mock_key')}")
    print(f"S3_ENDPOINT: {Config.S3_ENDPOINT}")
    print(f"S3_BUCKET_NAME: {Config.S3_BUCKET_NAME}")
    print(f"TMP_DIR: {Config.TMP_DIR}")
    print(f"STT provider available: {Config.HAS_STT_PROVIDER}")
    print(f"LLM provider available: {Config.HAS_LLM_PROVIDER}")
    print(f"OLLAMA_URL: {Config.OLLAMA_URL}")
    print(f"OLLAMA_MODEL: {Config.OLLAMA_MODEL}")
    print(f"COBALT_API_URL: {Config.COBALT_API_URL}")
    print("------------------------------------")


Config.validate = _validate
