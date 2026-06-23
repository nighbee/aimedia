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
import logging
from typing import Optional

from src.config import Config

logger = logging.getLogger("media-worker")


class JobProducer:
    def __init__(self):
        self._producer = None

        try:
            from confluent_kafka import Producer

            self._producer = Producer({
                "bootstrap.servers": Config.KAFKA_BROKERS,
                "acks": "all",
            })
            logger.info(f"[Kafka Producer] Ready → {Config.KAFKA_TOPIC_JOB_COMPLETED} @ {Config.KAFKA_BROKERS}")
        except ImportError:
            logger.warning("[WARN] confluent-kafka not installed. Kafka producer disabled.")
        except Exception as e:
            logger.warning(f"[WARN] Kafka connection failed: {e}. Producer disabled.")

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

        if self._producer is None:
            logger.warning(f"[Kafka Producer] No producer available, discarding message for {job_id}")
            return

        def _delivery_report(err, msg):
            if err:
                logger.error(f"[Kafka Producer] Delivery FAILED for {job_id}: {err}")
            else:
                logger.info(f"[Kafka Producer] Delivered {job_id} → partition {msg.partition()} @ offset {msg.offset()}")

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
