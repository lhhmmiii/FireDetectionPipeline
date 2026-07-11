"""Frame Extractor Service.

Connects to an RTSP stream from the Media Gateway, decodes video frames,
and publishes them to the Kafka 'frames' topic.

Features:
- Configurable FPS extraction rate
- Optional frame resizing
- Frame skipping when Kafka producer is overloaded
- Automatic RTSP reconnection with backoff
- Graceful shutdown on SIGTERM/SIGINT
"""

from __future__ import annotations

import signal
import sys
import time
import uuid
from datetime import datetime, timezone

import cv2

# Add project root to path for shared imports
sys.path.insert(0, "/app")

from shared.config import KafkaSettings, MetricsSettings, RTSPSettings
from shared.kafka import KafkaFrameProducer, KafkaJsonProducer
from shared.schemas import FrameMessage
from shared.tracing import Tracer
from shared.utils import encode_image, setup_logging

logger = setup_logging("frame_extractor")


class FrameExtractorService:
    """Extracts frames from an RTSP stream and publishes to Kafka."""

    def __init__(self) -> None:
        self._rtsp_settings = RTSPSettings()
        self._kafka_settings = KafkaSettings()
        self._metrics_settings = MetricsSettings()
        self._running = False
        self._capture: cv2.VideoCapture | None = None
        self._producer: KafkaFrameProducer | None = None
        self._metrics_producer: KafkaJsonProducer | None = None
        self._tracer: Tracer | None = None

    def _connect_rtsp(self) -> cv2.VideoCapture:
        """Connect to the RTSP stream with retry logic."""
        attempt = 0
        max_retries = self._rtsp_settings.max_retries
        # max_retries == 0 means infinite retries
        infinite = max_retries == 0

        while self._running and (infinite or attempt < max_retries):
            attempt += 1
            logger.info(
                "Connecting to RTSP stream: %s (attempt %d)",
                self._rtsp_settings.url,
                attempt,
            )
            cap = cv2.VideoCapture(self._rtsp_settings.url)
            if cap.isOpened():
                logger.info("RTSP stream connected successfully")
                return cap

            logger.warning(
                "Failed to connect to RTSP stream, retrying in %ds...",
                self._rtsp_settings.reconnect_delay,
            )
            cap.release()
            time.sleep(self._rtsp_settings.reconnect_delay)

        raise ConnectionError(
            f"Failed to connect to RTSP stream after {attempt} attempts"
        )

    def _init_producer(self) -> KafkaFrameProducer:
        """Initialize the Kafka frame producer."""
        return KafkaFrameProducer(
            bootstrap_servers=self._kafka_settings.bootstrap_servers,
            topic=self._kafka_settings.topic_frames,
        )

    def _init_tracer(self) -> Tracer:
        """Initialize the metrics producer and tracer for this stage."""
        if not self._metrics_settings.enabled:
            return Tracer(stage="frame_extractor", producer=None, enabled=False)

        self._metrics_producer = KafkaJsonProducer(
            bootstrap_servers=self._kafka_settings.bootstrap_servers,
            topic=self._kafka_settings.topic_metrics,
        )
        return Tracer(stage="frame_extractor", producer=self._metrics_producer)

    def _process_frame(self, frame: any) -> None:
        """Encode and publish a single frame to Kafka."""
        frame_id = str(uuid.uuid4())
        uav_id = self._rtsp_settings.uav_id

        with self._tracer.span("extract_frame", trace_id=frame_id, source_id=uav_id):
            # Resize if configured
            width = self._rtsp_settings.resize_width
            height = self._rtsp_settings.resize_height
            if width > 0 and height > 0:
                frame = cv2.resize(frame, (width, height))

            h, w = frame.shape[:2]

            message = FrameMessage(
                frame_id=frame_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                image_data=encode_image(frame),
                width=w,
                height=h,
                source_id=uav_id,
            )

            self._producer.produce(message, key=message.frame_id)

    def run(self) -> None:
        """Main service loop: connect RTSP → extract frames → publish to Kafka."""
        self._running = True
        self._producer = self._init_producer()
        self._tracer = self._init_tracer()

        uav_id = self._rtsp_settings.uav_id
        target_fps = self._rtsp_settings.extract_fps
        frame_interval = 1.0 / target_fps if target_fps > 0 else 0

        logger.info(
            "Frame Extractor [%s] targeting %s at %d FPS",
            uav_id,
            self._rtsp_settings.url,
            target_fps,
        )

        while self._running:
            try:
                self._capture = self._connect_rtsp()
                logger.info("[%s] Starting frame extraction", uav_id)

                last_frame_time = 0.0
                frames_extracted = 0

                while self._running:
                    ret, frame = self._capture.read()
                    if not ret:
                        logger.warning("Failed to read frame, reconnecting...")
                        self._tracer.record_dropped(
                            "extract_frame", source_id=uav_id, reason="rtsp_read_failed"
                        )
                        break

                    # Frame rate limiting
                    now = time.monotonic()
                    if now - last_frame_time < frame_interval:
                        continue
                    last_frame_time = now

                    try:
                        self._process_frame(frame)
                        frames_extracted += 1
                        if frames_extracted % 100 == 0:
                            logger.info(
                                "Extracted %d frames so far", frames_extracted
                            )
                    except Exception:
                        if self._rtsp_settings.skip_on_overload:
                            logger.warning(
                                "Failed to process frame, skipping"
                            )
                            continue
                        raise

            except ConnectionError:
                if not self._running:
                    break
                logger.error("RTSP connection lost, will retry...")
                time.sleep(self._rtsp_settings.reconnect_delay)
            except Exception:
                logger.exception("Unexpected error in frame extractor")
                if not self._running:
                    break
                time.sleep(self._rtsp_settings.reconnect_delay)
            finally:
                if self._capture:
                    self._capture.release()
                    self._capture = None

    def shutdown(self) -> None:
        """Gracefully shut down the service."""
        logger.info("Shutting down Frame Extractor...")
        self._running = False
        if self._capture:
            self._capture.release()
        if self._producer:
            self._producer.close()
        if self._metrics_producer:
            self._metrics_producer.close()
        logger.info("Frame Extractor shut down complete")


def main() -> None:
    """Entry point for the Frame Extractor service."""
    service = FrameExtractorService()

    def handle_signal(signum: int, _frame: any) -> None:
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
