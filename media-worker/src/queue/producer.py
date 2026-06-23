"""
Kafka Producer — publishes to the `media.job.completed` topic.

Message schema (JSON):
  {
    "job_id":       str,
    "status":       "completed" | "failed",
    "risk_score":   int,
    "confidence":   str,
    "reasoning":    str,
    "categories":   { illegal_gambling, pyramid_scheme, investment_fraud, referral_scheme },
    "top_flags":    [{ signal, weight }],
    "evidence_url": str | null,     # S3 object path (e.g. "evidence-packs/<uuid>.pdf")
    "custody_log":  [{ timestamp, stage, status }],
    "error":        str | null
  }

The evidence_url is stored as an S3 object path so the Go API can
regenerate a fresh presigned URL on each evidence download request.
"""
import json
from typing import Optional

from src.config import Config


class JobProducer:
    def __init__(self):
        self._producer = None
        self._mock = Config.IS_MOCK_MODE

        if not self._mock:
            try:
                from confluent_kafka import Producer

                self._producer = Producer({
                    "bootstrap.servers": Config.KAFKA_BROKERS,
                    "acks": "all",
                })
                print(f"[Kafka Producer] Ready → {Config.KAFKA_TOPIC_JOB_COMPLETED} @ {Config.KAFKA_BROKERS}")
            except ImportError:
                print("[WARN] confluent-kafka not installed. Switching to mock mode.")
                self._mock = True

    def publish_completed(
        self,
        job_id: str,
        risk_score: int,
        confidence: str,
        reasoning: str,
        categories: dict,
        top_flags: list,
        evidence_url: Optional[str],
        custody_log: Optional[list] = None,
    ) -> None:
        payload = {
            "job_id": job_id,
            "status": "completed",
            "risk_score": risk_score,
            "confidence": confidence,
            "reasoning": reasoning,
            "categories": categories,
            "top_flags": [
                {"signal": f.signal, "weight": f.weight} for f in top_flags
            ],
            "evidence_url": evidence_url,
            "custody_log": custody_log or [],
            "error": None,
        }
        self._send(payload)

    def publish_failed(self, job_id: str, stage: str, error: str, custody_log: Optional[list] = None) -> None:
        payload = {
            "job_id": job_id,
            "status": "failed",
            "risk_score": 0,
            "confidence": "low",
            "reasoning": "",
            "categories": {},
            "top_flags": [],
            "evidence_url": None,
            "custody_log": custody_log or [],
            "error": f"{stage}: {error}",
        }
        self._send(payload)

    def _send(self, payload: dict) -> None:
        job_id = payload.get("job_id", "unknown")
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        if self._mock:
            print(f"[MOCK Kafka Producer] Would publish to {Config.KAFKA_TOPIC_JOB_COMPLETED}:")
            print(f"  job_id={job_id}, status={payload['status']}, risk_score={payload['risk_score']}")
            return

        def _delivery_report(err, msg):
            if err:
                print(f"[Kafka Producer] Delivery failed for {job_id}: {err}")
            else:
                print(f"[Kafka Producer] Delivered {job_id} → partition {msg.partition()} @ offset {msg.offset()}")

        self._producer.produce(
            Config.KAFKA_TOPIC_JOB_COMPLETED,
            key=job_id.encode("utf-8"),
            value=raw,
            callback=_delivery_report,
        )
        self._producer.flush(timeout=10)

    def close(self):
        if self._producer:
            self._producer.flush(timeout=10)
