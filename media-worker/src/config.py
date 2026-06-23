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

    # Mode determination
    IS_MOCK_MODE = (
        (not SONIOX_API_KEY or SONIOX_API_KEY == "mock_key")
        and (not GROQ_API_KEY or GROQ_API_KEY == "mock_key")
        and (not GEMINI_API_KEY or GEMINI_API_KEY == "mock_key")
        and (not BLACKBOX_API_KEY or BLACKBOX_API_KEY == "mock_key")
    )

    HAS_SONIOX = bool(SONIOX_API_KEY and SONIOX_API_KEY != "mock_key")
    HAS_GROQ = bool(GROQ_API_KEY and GROQ_API_KEY != "mock_key")
    HAS_GEMINI = bool(GEMINI_API_KEY and GEMINI_API_KEY != "mock_key")
    HAS_BLACKBOX = bool(BLACKBOX_API_KEY and BLACKBOX_API_KEY != "mock_key")

    HAS_STT_PROVIDER = HAS_SONIOX or HAS_GROQ
    HAS_LLM_PROVIDER = HAS_GEMINI or HAS_BLACKBOX

    @classmethod
    def validate(cls):
        print("--- Config Validation ---")
        print(f"KAFKA_BROKERS: {cls.KAFKA_BROKERS}")
        print(f"KAFKA_GROUP_ID: {cls.KAFKA_GROUP_ID}")
        print(f"GO_API_BASE_URL: {cls.GO_API_BASE_URL}")
        print(f"GO_API_INTERNAL_TOKEN set: {bool(cls.GO_API_INTERNAL_TOKEN)}")
        print(f"SONIOX_API_KEY set: {bool(cls.SONIOX_API_KEY and cls.SONIOX_API_KEY != 'mock_key')}")
        print(f"GROQ_API_KEY set: {bool(cls.GROQ_API_KEY and cls.GROQ_API_KEY != 'mock_key')}")
        print(f"GEMINI_API_KEY set: {bool(cls.GEMINI_API_KEY and cls.GEMINI_API_KEY != 'mock_key')}")
        print(f"BLACKBOX_API_KEY set: {bool(cls.BLACKBOX_API_KEY and cls.BLACKBOX_API_KEY != 'mock_key')}")
        print(f"S3_ENDPOINT: {cls.S3_ENDPOINT}")
        print(f"S3_BUCKET_NAME: {cls.S3_BUCKET_NAME}")
        print(f"TMP_DIR: {cls.TMP_DIR}")
        print(f"STT provider available: {cls.HAS_STT_PROVIDER}")
        print(f"LLM provider available: {cls.HAS_LLM_PROVIDER}")
        print(f"MOCK MODE ACTIVE: {cls.IS_MOCK_MODE}")
        print("------------------------------------")
