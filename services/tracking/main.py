"""Tracking Service.

Consumes detection results from the Kafka 'detections' topic,
associates objects across frames using a tracker, and publishes
tracked objects to the 'tracks' topic.

Features:
- Pluggable tracker interface (swap algorithms without code changes)
- Graceful shutdown on SIGTERM/SIGINT
- Skip corrupted messages
"""

from __future__ import annotations

import signal
import sys

# Add project root to path for shared imports
sys.path.insert(0, "/app")

from shared.config import KafkaSettings, TrackingSettings
from shared.kafka import KafkaJsonConsumer, KafkaJsonProducer
from shared.utils import setup_logging

from tracker import BaseTracker, SimpleIoUTracker

logger = setup_logging("tracking")


class TrackingService:
    """Consumes detections, tracks objects, publishes tracks."""

    def __init__(self, tracker: BaseTracker | None = None) -> None:
        self._kafka_settings = KafkaSettings()
        self._tracking_settings = TrackingSettings()
        self._consumer: KafkaJsonConsumer | None = None
        self._producer: KafkaJsonProducer | None = None

        # Use provided tracker or default
        if tracker is not None:
            self._tracker = tracker
        else:
            self._tracker = SimpleIoUTracker(
                max_age=self._tracking_settings.max_age,
                min_hits=self._tracking_settings.min_hits,
                iou_threshold=self._tracking_settings.iou_threshold,
            )

    def _init_kafka(self) -> None:
        """Initialize Kafka consumer and producer."""
        self._consumer = KafkaJsonConsumer(
            bootstrap_servers=self._kafka_settings.bootstrap_servers,
            topic=self._kafka_settings.topic_detections,
            group_id="tracking-service",
        )
        self._producer = KafkaJsonProducer(
            bootstrap_servers=self._kafka_settings.bootstrap_servers,
            topic=self._kafka_settings.topic_tracks,
        )

    def _process_detection(self, message: dict) -> None:
        """Process a detection message and publish tracks.

        Args:
            message: Deserialized DetectionMessage dict from Kafka.
        """
        frame_id = message.get("frame_id", "unknown")

        try:
            track_messages = self._tracker.update(message)

            for track_msg in track_messages:
                self._producer.produce(track_msg, key=str(track_msg.track_id))

            if track_messages:
                logger.debug(
                    "Frame %s: %d active tracks",
                    frame_id,
                    len(track_messages),
                )
        except Exception:
            logger.exception(
                "Error processing detections for frame %s, skipping",
                frame_id,
            )

    def run(self) -> None:
        """Start the tracking service."""
        self._init_kafka()
        logger.info(
            "Tracking Service started (max_age=%d, min_hits=%d, iou=%.2f)",
            self._tracking_settings.max_age,
            self._tracking_settings.min_hits,
            self._tracking_settings.iou_threshold,
        )

        self._consumer.consume(callback=self._process_detection)

    def shutdown(self) -> None:
        """Gracefully shut down the service."""
        logger.info("Shutting down Tracking Service...")
        if self._consumer:
            self._consumer.close()
        if self._producer:
            self._producer.close()
        logger.info("Tracking Service shut down complete")


def main() -> None:
    """Entry point for the Tracking Service."""
    service = TrackingService()

    def handle_signal(signum: int, _frame) -> None:
        logger.info("Received signal %d", signum)
        service.shutdown()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        service.run()
    except KeyboardInterrupt:
        service.shutdown()


if __name__ == "__main__":
    main()
