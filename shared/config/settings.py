"""Centralized settings loaded from environment variables.

All configuration is loaded via os.environ so that values can be
injected through Docker Compose, .env files, or CI/CD pipelines.
Nothing is hardcoded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(key: str, default: str = "") -> str:
    """Read an environment variable with a default."""
    return os.environ.get(key, default)


def _env_int(key: str, default: int = 0) -> int:
    """Read an integer environment variable."""
    return int(os.environ.get(key, str(default)))


def _env_float(key: str, default: float = 0.0) -> float:
    """Read a float environment variable."""
    return float(os.environ.get(key, str(default)))


def _env_bool(key: str, default: bool = False) -> bool:
    """Read a boolean environment variable."""
    return os.environ.get(key, str(default)).lower() in ("true", "1", "yes")


@dataclass(frozen=True)
class KafkaSettings:
    """Kafka broker and topic configuration."""

    bootstrap_servers: str = field(
        default_factory=lambda: _env("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    )
    topic_frames: str = field(
        default_factory=lambda: _env("KAFKA_TOPIC_FRAMES", "frames")
    )
    topic_detections: str = field(
        default_factory=lambda: _env("KAFKA_TOPIC_DETECTIONS", "detections")
    )
    topic_tracks: str = field(
        default_factory=lambda: _env("KAFKA_TOPIC_TRACKS", "tracks")
    )
    topic_metrics: str = field(
        default_factory=lambda: _env("KAFKA_TOPIC_METRICS", "metrics")
    )


@dataclass(frozen=True)
class MetricsSettings:
    """Tracing/metrics emission configuration, used by producing services."""

    enabled: bool = field(
        default_factory=lambda: _env_bool("METRICS_ENABLED", True)
    )


@dataclass(frozen=True)
class RTSPSettings:
    """RTSP stream configuration."""

    source_id: str = field(
        default_factory=lambda: _env("SOURCE_ID", "default")
    )
    url: str = field(
        default_factory=lambda: _env("RTSP_URL", "rtsp://localhost:8554/stream")
    )
    reconnect_delay: float = field(
        default_factory=lambda: _env_float("RTSP_RECONNECT_DELAY", 5.0)
    )
    max_retries: int = field(
        default_factory=lambda: _env_int("RTSP_MAX_RETRIES", 0)
    )
    extract_fps: int = field(
        default_factory=lambda: _env_int("FRAME_EXTRACT_FPS", 20)
    )
    resize_width: int = field(
        default_factory=lambda: _env_int("FRAME_RESIZE_WIDTH", 384)
    )
    resize_height: int = field(
        default_factory=lambda: _env_int("FRAME_RESIZE_HEIGHT", 384)
    )
    skip_on_overload: bool = field(
        default_factory=lambda: _env_bool("FRAME_SKIP_ON_OVERLOAD", True)
    )


@dataclass(frozen=True)
class DetectionSettings:
    """Detection model configuration."""

    model_path: str = field(
        default_factory=lambda: _env("DETECTION_MODEL_PATH", "")
    )
    confidence_threshold: float = field(
        default_factory=lambda: _env_float("DETECTION_CONFIDENCE_THRESHOLD", 0.5)
    )
    device: str = field(
        default_factory=lambda: _env("DETECTION_DEVICE", "cpu")
    )
    batch_size: int = field(
        default_factory=lambda: _env_int("DETECTION_BATCH_SIZE", 1)
    )


@dataclass(frozen=True)
class TrackingSettings:
    """Tracking algorithm configuration."""

    max_age: int = field(
        default_factory=lambda: _env_int("TRACKING_MAX_AGE", 30)
    )
    min_hits: int = field(
        default_factory=lambda: _env_int("TRACKING_MIN_HITS", 3)
    )
    iou_threshold: float = field(
        default_factory=lambda: _env_float("TRACKING_IOU_THRESHOLD", 0.3)
    )


def _parse_streams(raw: str) -> tuple[dict[str, str], ...]:
    """Parse "source_id:stream_name,source_id:stream_name" into stream configs."""
    streams = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        source_id, _, stream_name = entry.partition(":")
        streams.append({"source_id": source_id, "stream_name": stream_name or source_id})
    return tuple(streams)


@dataclass(frozen=True)
class DashboardSettings:
    """Dashboard server configuration."""

    host: str = field(
        default_factory=lambda: _env("DASHBOARD_HOST", "0.0.0.0")
    )
    port: int = field(
        default_factory=lambda: _env_int("DASHBOARD_PORT", 8080)
    )
    webrtc_url: str = field(
        default_factory=lambda: _env("WEBRTC_URL", "http://localhost:8889")
    )
    streams: tuple[dict[str, str], ...] = field(
        default_factory=lambda: _parse_streams(
            _env("DASHBOARD_STREAMS", "camera-1:stream1,camera-2:stream2")
        )
    )


@dataclass(frozen=True)
class MonitoringSettings:
    """Monitoring service configuration."""

    host: str = field(
        default_factory=lambda: _env("MONITORING_HOST", "0.0.0.0")
    )
    port: int = field(
        default_factory=lambda: _env_int("MONITORING_PORT", 8090)
    )
    window_seconds: float = field(
        default_factory=lambda: _env_float("METRICS_WINDOW_SECONDS", 60.0)
    )
    baseline_dir: str = field(
        default_factory=lambda: _env("MONITORING_BASELINE_DIR", "/app/data/baselines")
    )
