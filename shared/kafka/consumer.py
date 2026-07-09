"""Kafka consumers for the pipeline.

Provides two consumer types:
- KafkaFrameConsumer: Consumes frame messages from Kafka.
- KafkaJsonConsumer: Consumes JSON-serialized messages (detections, tracks).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable

from confluent_kafka import Consumer, KafkaError, KafkaException

logger = logging.getLogger(__name__)

_DEFAULT_RETRY_DELAY = 2.0
_DEFAULT_MAX_RETRIES = 5


class KafkaJsonConsumer:
    """Consumes JSON-serialized messages from a Kafka topic.

    Supports graceful shutdown, automatic offset commits,
    and retry on transient failures.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        group_id: str,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        retry_delay: float = _DEFAULT_RETRY_DELAY,
    ) -> None:
        self._topic = topic
        self._group_id = group_id
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._running = False
        self._consumer: Consumer | None = None
        self._config = {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "client.id": f"consumer-{group_id}-{topic}",
            "auto.offset.reset": "latest",
            "enable.auto.commit": True,
            "auto.commit.interval.ms": 5000,
            "max.poll.interval.ms": 300000,
            "session.timeout.ms": 30000,
        }
        self._connect()

    def _connect(self) -> None:
        """Create the Kafka consumer and subscribe to topic."""
        for attempt in range(1, self._max_retries + 1):
            try:
                self._consumer = Consumer(self._config)
                self._consumer.subscribe([self._topic])
                logger.info(
                    "Kafka consumer subscribed to topic '%s' (group: %s)",
                    self._topic,
                    self._group_id,
                )
                return
            except KafkaException as exc:
                logger.warning(
                    "Consumer connection attempt %d/%d failed: %s",
                    attempt,
                    self._max_retries,
                    exc,
                )
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay)
        raise ConnectionError(
            f"Failed to create Kafka consumer after {self._max_retries} attempts"
        )

    def consume(
        self,
        callback: Callable[[dict[str, Any]], None],
        poll_timeout: float = 1.0,
    ) -> None:
        """Start consuming messages in a blocking loop.

        Args:
            callback: Function to call with each deserialized message.
            poll_timeout: Seconds to wait for new messages per poll cycle.
        """
        if self._consumer is None:
            raise RuntimeError("Consumer is not connected")

        self._running = True
        logger.info("Starting consume loop for topic '%s'", self._topic)

        while self._running:
            try:
                msg = self._consumer.poll(timeout=poll_timeout)

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.debug(
                            "End of partition reached: %s [%d]",
                            msg.topic(),
                            msg.partition(),
                        )
                        continue
                    logger.error("Consumer error: %s", msg.error())
                    continue

                try:
                    payload = json.loads(msg.value().decode("utf-8"))
                    callback(payload)
                except json.JSONDecodeError:
                    logger.warning(
                        "Failed to decode message at offset %d, skipping",
                        msg.offset(),
                    )
                except Exception:
                    logger.exception(
                        "Error processing message at offset %d, skipping",
                        msg.offset(),
                    )

            except KafkaException as exc:
                logger.error("Kafka exception during consume: %s", exc)
                time.sleep(self._retry_delay)

    def stop(self) -> None:
        """Signal the consume loop to stop."""
        logger.info("Stopping consumer for topic '%s'", self._topic)
        self._running = False

    def close(self) -> None:
        """Stop consuming and close the consumer."""
        self.stop()
        if self._consumer:
            self._consumer.close()
            self._consumer = None
            logger.info("Kafka consumer closed for topic '%s'", self._topic)


class KafkaFrameConsumer(KafkaJsonConsumer):
    """Consumes frame messages from Kafka.

    Inherits all consume logic from KafkaJsonConsumer.
    Frame messages contain base64-encoded image data.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str = "frames",
        group_id: str = "frame-consumers",
        max_retries: int = _DEFAULT_MAX_RETRIES,
        retry_delay: float = _DEFAULT_RETRY_DELAY,
    ) -> None:
        super().__init__(
            bootstrap_servers=bootstrap_servers,
            topic=topic,
            group_id=group_id,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )
