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
from typing import Callable, Optional

from src.config import Config


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
        Returns the parsed dict payload, or None if no message is available.
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

        try:
            payload = json.loads(msg.value().decode("utf-8"))
            self._consumer.commit(msg)
            print(f"[Kafka Consumer] Received job: {payload.get('job_id')}")
            return payload
        except json.JSONDecodeError as e:
            print(f"[Kafka Consumer] Malformed message, skipping: {e}")
            self._consumer.commit(msg)
            return None

    def close(self):
        if self._consumer:
            try:
                self._consumer.close()
            except Exception:
                pass
