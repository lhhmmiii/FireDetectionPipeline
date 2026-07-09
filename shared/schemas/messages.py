"""Immutable message schemas for the pipeline Kafka topics.

All messages are dataclasses designed to be serialized as JSON.
Messages are immutable by design (frozen=True).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FrameMessage:
    """A single video frame published to the 'frames' topic.

    Attributes:
        frame_id: Unique identifier for this frame (UUID).
        timestamp: ISO-8601 timestamp of when the frame was captured.
        image_data: Base64-encoded image bytes (JPEG).
        width: Frame width in pixels.
        height: Frame height in pixels.
        source_id: Identifier for the video source / UAV.
    """

    frame_id: str
    timestamp: str
    image_data: str
    width: int
    height: int
    source_id: str = "default"


@dataclass(frozen=True)
class DetectionResult:
    """Result container for a single frame's detections.

    Used internally by the detector before publishing to Kafka.
    """

    boxes: list[list[float]] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    classes: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class DetectionMessage:
    """Detection results published to the 'detections' topic.

    Attributes:
        frame_id: ID of the source frame.
        timestamp: ISO-8601 timestamp.
        boxes: List of bounding boxes, each as [x1, y1, x2, y2].
        scores: Confidence scores corresponding to each box.
        classes: Class IDs corresponding to each box.
        source_id: Identifier for the video source / UAV.
    """

    frame_id: str
    timestamp: str
    boxes: list[list[float]] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    classes: list[int] = field(default_factory=list)
    source_id: str = "default"


@dataclass(frozen=True)
class TrackMessage:
    """A single tracked object published to the 'tracks' topic.

    Attributes:
        track_id: Persistent ID assigned by the tracker.
        frame_id: ID of the source frame.
        timestamp: ISO-8601 timestamp.
        bbox: Bounding box as [x1, y1, x2, y2].
        confidence: Tracker confidence score.
        class_id: Object class ID.
        class_name: Human-readable class name.
        source_id: Identifier for the video source / UAV.
    """

    track_id: int
    frame_id: str
    timestamp: str
    bbox: list[float] = field(default_factory=list)
    confidence: float = 0.0
    class_id: int = 0
    class_name: str = ""
    source_id: str = "default"
