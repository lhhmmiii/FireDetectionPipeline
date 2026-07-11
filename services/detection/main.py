"""Detection Service.

Consumes frames from the Kafka 'frames' topic, runs fire detection
inference, and publishes detection results to the 'detections' topic.

Features:
- Pluggable detector interface (swap models without code changes)
- Skip corrupted frames gracefully
- Graceful shutdown on SIGTERM/SIGINT
"""

from __future__ import annotations

import signal
import sys
from datetime import datetime, timezone

# Add project root to path for shared imports
sys.path.insert(0, "/app")

from shared.config import DetectionSettings, KafkaSettings, MetricsSettings
from shared.kafka import KafkaJsonConsumer, KafkaJsonProducer
from shared.schemas import DetectionMessage
from shared.tracing import Tracer
from shared.utils import decode_image, setup_logging

from detector import BaseDetector

logger = setup_logging("detection")


def _build_detector(model_path: str) -> BaseDetector:
    """Select detector implementation based on model file extension."""
    if not model_path.endswith(".engine"):
        raise ValueError(
            f"Unsupported model path {model_path!r}: DETECTION_MODEL_PATH must "
            "point to a TensorRT .engine file."
        )
    from trt_detector import RFDETRTensorRTDetector
    return RFDETRTensorRTDetector()


class DetectionService:
    """Consumes frames, runs detection, publishes results."""

    def __init__(self, detector: BaseDetector | None = None) -> None:
        self._kafka_settings = KafkaSettings()
        self._detection_settings = DetectionSettings()
        self._metrics_settings = MetricsSettings()
        self._consumer: KafkaJsonConsumer | None = None
        self._producer: KafkaJsonProducer | None = None
        self._metrics_producer: KafkaJsonProducer | None = None
        self._tracer: Tracer | None = None

        self._detector = detector if detector is not None else _build_detector(
            self._detection_settings.model_path
        )

    def _init_detector(self) -> None:
        """Load the detection model."""
        self._detector.load(
            model_path=self._detection_settings.model_path,
            device=self._detection_settings.device,
        )
        logger.info(
            "Detector loaded: %s (device=%s, threshold=%.2f)",
            type(self._detector).__name__,
            self._detection_settings.device,
            self._detection_settings.confidence_threshold,
        )

    def _init_kafka(self) -> None:
        """Initialize Kafka consumer and producer."""
        self._consumer = KafkaJsonConsumer(
            bootstrap_servers=self._kafka_settings.bootstrap_servers,
            topic=self._kafka_settings.topic_frames,
            group_id="detection-service",
        )
        self._producer = KafkaJsonProducer(
            bootstrap_servers=self._kafka_settings.bootstrap_servers,
            topic=self._kafka_settings.topic_detections,
        )

        if self._metrics_settings.enabled:
            self._metrics_producer = KafkaJsonProducer(
                bootstrap_servers=self._kafka_settings.bootstrap_servers,
                topic=self._kafka_settings.topic_metrics,
            )
            self._tracer = Tracer(stage="detection", producer=self._metrics_producer)
        else:
            self._tracer = Tracer(stage="detection", producer=None, enabled=False)

    def _process_frame(self, message: dict) -> None:
        """Process a single frame message.

        Args:
            message: Deserialized FrameMessage dict from Kafka.
        """
        frame_id = message.get("frame_id", "unknown")
        source_id = message.get("source_id", "default")

        try:
            # Decode the image from base64
            image = decode_image(message["image_data"])
        except (KeyError, ValueError):
            logger.warning("Corrupted frame %s, skipping", frame_id)
            self._tracer.record_dropped(
                "decode", trace_id=frame_id, source_id=source_id, reason="corrupted_frame"
            )
            return

        with self._tracer.span("detect", trace_id=frame_id, source_id=source_id):
            # Run detection
            result = self._detector.predict(
                image,
                confidence_threshold=self._detection_settings.confidence_threshold,
            )

            # Publish detection results
            detection_msg = DetectionMessage(
                frame_id=frame_id,
                timestamp=message.get(
                    "timestamp", datetime.now(timezone.utc).isoformat()
                ),
                boxes=result.boxes,
                scores=result.scores,
                classes=result.classes,
                source_id=source_id,
            )

            self._producer.produce(detection_msg, key=frame_id)
            logger.debug(
                "Frame %s: %d detections", frame_id, len(result.boxes)
            )

    def run(self) -> None:
        """Start the detection service."""
        self._init_detector()
        self._init_kafka()
        logger.info("Detection Service started, consuming from '%s'", self._kafka_settings.topic_frames)

        self._consumer.consume(callback=self._process_frame)

    def shutdown(self) -> None:
        """Gracefully shut down the service."""
        logger.info("Shutting down Detection Service...")
        if self._consumer:
            self._consumer.close()
        if self._producer:
            self._producer.close()
        if self._metrics_producer:
            self._metrics_producer.close()
        logger.info("Detection Service shut down complete")


def main() -> None:
    """Entry point for the Detection Service."""
    service = DetectionService()

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
