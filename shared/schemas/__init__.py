"""Message schemas for Kafka communication."""

from shared.schemas.messages import (
    DetectionMessage,
    DetectionResult,
    FrameMessage,
    SpanMessage,
    TrackMessage,
)

__all__ = [
    "FrameMessage",
    "DetectionMessage",
    "DetectionResult",
    "TrackMessage",
    "SpanMessage",
]
