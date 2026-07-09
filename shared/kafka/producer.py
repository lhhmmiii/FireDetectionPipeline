"""Kafka producers for the pipeline.

Provides two producer types:
- KafkaFrameProducer: Publishes frame data (image bytes + metadata) to Kafka.
- KafkaJsonProducer: Publishes JSON-serialized messages (detections, tracks).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from typing import Any

from confluent_kafka import KafkaError, Producer

logger = logging.getLogger(__name__)

_DEFAULT_RETRY_DELAY = 2.0
_DEFAULT_MAX_RETRIES = 5


class KafkaJsonProducer:
    """Produces JSON-serialized messages to a Kafka topic.

    Handles serialization, delivery callbacks, and retry logic
    for transient failures.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        retry_delay: float = _DEFAULT_RETRY_DELAY,
    ) -> None:
        self._topic = topic
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._producer: Producer | None = None
        self._config = {
            "bootstrap.servers": bootstrap_servers,
            "client.id": f"producer-{topic}",
            "acks": "all",
            "retries": 3,
            "retry.backoff.ms": 500,
            "linger.ms": 5,
            "batch.num.messages": 100,
        }
        self._connect()

    def _connect(self) -> None:
        """Create the Kafka producer with retry logic."""
        for attempt in range(1, self._max_retries + 1):
            try:
                self._producer = Producer(self._config)
                logger.info(
                    "Kafka producer connected to topic '%s'", self._topic
                )
                return
            except KafkaError as exc:
                logger.warning(
                    "Producer connection attempt %d/%d failed: %s",
                    attempt,
                    self._max_retries,
                    exc,
                )
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay)
        raise ConnectionError(
            f"Failed to create Kafka producer after {self._max_retries} attempts"
        )

    @staticmethod
    def _delivery_callback(err: KafkaError | None, msg: Any) -> None:
        """Log delivery result."""
        if err is not None:
            logger.error("Message delivery failed: %s", err)
        else:
            logger.debug(
                "Message delivered to %s [%d] @ offset %d",
                msg.topic(),
                msg.partition(),
                msg.offset(),
            )

    def produce(self, message: Any, key: str | None = None) -> None:
        """Serialize and publish a message to Kafka.

        Args:
            message: A dataclass instance or dict to serialize as JSON.
            key: Optional partition key.
        """
        if self._producer is None:
            raise RuntimeError("Producer is not connected")

        try:
            if hasattr(message, "__dataclass_fields__"):
                payload = json.dumps(asdict(message)).encode("utf-8")
            elif isinstance(message, dict):
                payload = json.dumps(message).encode("utf-8")
            else:
                payload = json.dumps(message).encode("utf-8")

            self._producer.produce(
                topic=self._topic,
                value=payload,
                key=key.encode("utf-8") if key else None,
                callback=self._delivery_callback,
            )
            self._producer.poll(0)
        except BufferError:
            logger.warning("Producer queue full, flushing...")
            self._producer.flush(timeout=10)
            self._producer.produce(
                topic=self._topic,
                value=payload,
                key=key.encode("utf-8") if key else None,
                callback=self._delivery_callback,
            )
        except Exception:
            logger.exception("Failed to produce message to '%s'", self._topic)
            raise

    def flush(self, timeout: float = 10.0) -> None:
        """Flush pending messages."""
        if self._producer:
            self._producer.flush(timeout=timeout)

    def close(self) -> None:
        """Flush and close the producer."""
        if self._producer:
            logger.info("Closing Kafka producer for topic '%s'", self._topic)
            self._producer.flush(timeout=30)
            self._producer = None


class KafkaFrameProducer(KafkaJsonProducer):
    """Produces frame messages to Kafka.

    Frames are serialized as JSON with base64-encoded image data.
    Inherits retry and delivery logic from KafkaJsonProducer.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str = "frames",
        max_retries: int = _DEFAULT_MAX_RETRIES,
        retry_delay: float = _DEFAULT_RETRY_DELAY,
    ) -> None:
        super().__init__(
            bootstrap_servers=bootstrap_servers,
            topic=topic,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )
