"""
Kafka Consumer — listens on the `media.job.created` topic.

Message schema (JSON):
  {
    "job_id":       str  (UUID),
    "url":          str,
    "priority":     int  (1=high, 2=normal, 3=low),
    "submitted_at": str  (ISO8601)
  }
"""
import json
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.config import Config


class JobMessage(BaseModel):
    """Validated schema for incoming Kafka job-created messages."""
    job_id: str
    url: str = Field(max_length=2048)
    platform: str = ""
    priority: int = Field(default=2, ge=1, le=3)
    submitted_at: str = ""
    inspector_id: str = "system"

    @field_validator("job_id")
    @classmethod
    def validate_job_id(cls, v: str) -> str:
        try:
            UUID(v)
        except ValueError:
            raise ValueError(f"Invalid job_id: {v} is not a valid UUID")
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"Invalid URL: {v[:100]}")
        return v


class JobConsumer:
    def __init__(self):
        self._consumer = None
        self._mock = Config.IS_MOCK_MODE

        if not self._mock:
            try:
                from confluent_kafka import Consumer, KafkaError

                self._consumer = Consumer({
                    "bootstrap.servers": Config.KAFKA_BROKERS,
                    "group.id": Config.KAFKA_GROUP_ID,
                    "auto.offset.reset": "earliest",
                    "enable.auto.commit": False,
                })
                self._consumer.subscribe([Config.KAFKA_TOPIC_JOB_CREATED])
                print(f"[Kafka Consumer] Subscribed to {Config.KAFKA_TOPIC_JOB_CREATED} @ {Config.KAFKA_BROKERS} (group={Config.KAFKA_GROUP_ID})")
            except ImportError:
                print("[WARN] confluent-kafka not installed. Switching to mock mode.")
                self._mock = True

    def poll(self, timeout_s: float = 5.0) -> Optional[dict]:
        """
        Poll for one message.
        Returns the validated dict payload, or None if no message is available.
        Malformed messages are logged and skipped.
        """
        if self._mock:
            return None   # mock polling always returns nothing; main.py drives mock jobs directly

        from confluent_kafka import KafkaError

        msg = self._consumer.poll(timeout=timeout_s)
        if msg is None:
            return None
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                return None
            raise RuntimeError(f"Kafka consumer error: {msg.error()}")

        raw = msg.value()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"[Kafka Consumer] Malformed message (invalid JSON), skipping: {e}")
            self._consumer.commit(msg)
            return None

        try:
            validated = JobMessage(**payload)
        except Exception as e:
            print(f"[Kafka Consumer] Message validation failed, skipping: {e}")
            self._consumer.commit(msg)
            return None

        self._consumer.commit(msg)
        print(f"[Kafka Consumer] Received job: {validated.job_id}")
        return validated.model_dump()

    def close(self):
        if self._consumer:
            try:
                self._consumer.close()
            except Exception:
                pass
