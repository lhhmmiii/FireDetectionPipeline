"""Unit tests for message schemas.

Tests serialization, deserialization, and immutability of all Kafka message schemas.
"""

import json
from dataclasses import asdict

import pytest

from shared.schemas.messages import (
    DetectionMessage,
    DetectionResult,
    FrameMessage,
    TrackMessage,
)


class TestFrameMessage:
    """Tests for FrameMessage schema."""

    def test_create_frame_message(self):
        """Frame message should be created with all fields."""
        msg = FrameMessage(
            frame_id="abc-123",
            timestamp="2025-01-01T00:00:00Z",
            image_data="base64data",
            width=640,
            height=480,
            source_id="uav-1",
        )
        assert msg.frame_id == "abc-123"
        assert msg.width == 640
        assert msg.height == 480
        assert msg.source_id == "uav-1"

    def test_frame_message_default_source_id(self):
        """Frame message should have default source_id."""
        msg = FrameMessage(
            frame_id="test",
            timestamp="2025-01-01T00:00:00Z",
            image_data="data",
            width=100,
            height=100,
        )
        assert msg.source_id == "default"

    def test_frame_message_immutable(self):
        """Frame message should be immutable (frozen)."""
        msg = FrameMessage(
            frame_id="test",
            timestamp="2025-01-01T00:00:00Z",
            image_data="data",
            width=100,
            height=100,
        )
        with pytest.raises(AttributeError):
            msg.frame_id = "changed"

    def test_frame_message_serialization(self):
        """Frame message should serialize to JSON correctly."""
        msg = FrameMessage(
            frame_id="abc-123",
            timestamp="2025-01-01T00:00:00Z",
            image_data="base64data",
            width=640,
            height=480,
        )
        data = asdict(msg)
        json_str = json.dumps(data)
        parsed = json.loads(json_str)

        assert parsed["frame_id"] == "abc-123"
        assert parsed["width"] == 640
        assert parsed["image_data"] == "base64data"

    def test_frame_message_deserialization(self):
        """Frame message should deserialize from JSON dict."""
        data = {
            "frame_id": "xyz-789",
            "timestamp": "2025-01-01T12:00:00Z",
            "image_data": "base64data",
            "width": 1920,
            "height": 1080,
            "source_id": "uav-2",
        }
        msg = FrameMessage(**data)
        assert msg.frame_id == "xyz-789"
        assert msg.width == 1920


class TestDetectionResult:
    """Tests for DetectionResult schema."""

    def test_empty_detection_result(self):
        """Empty detection result should have empty lists."""
        result = DetectionResult()
        assert result.boxes == []
        assert result.scores == []
        assert result.classes == []

    def test_detection_result_with_data(self):
        """Detection result should store boxes, scores, classes."""
        result = DetectionResult(
            boxes=[[10.0, 20.0, 100.0, 200.0]],
            scores=[0.95],
            classes=[0],
        )
        assert len(result.boxes) == 1
        assert result.scores[0] == 0.95
        assert result.classes[0] == 0


class TestDetectionMessage:
    """Tests for DetectionMessage schema."""

    def test_create_detection_message(self):
        """Detection message should be created with all fields."""
        msg = DetectionMessage(
            frame_id="frame-1",
            timestamp="2025-01-01T00:00:00Z",
            boxes=[[10, 20, 100, 200], [50, 60, 150, 250]],
            scores=[0.9, 0.8],
            classes=[0, 1],
        )
        assert msg.frame_id == "frame-1"
        assert len(msg.boxes) == 2
        assert len(msg.scores) == 2

    def test_detection_message_empty(self):
        """Detection message should support empty detections."""
        msg = DetectionMessage(
            frame_id="frame-2",
            timestamp="2025-01-01T00:00:00Z",
        )
        assert msg.boxes == []
        assert msg.scores == []

    def test_detection_message_serialization_roundtrip(self):
        """Detection message should survive JSON roundtrip."""
        msg = DetectionMessage(
            frame_id="frame-1",
            timestamp="2025-01-01T00:00:00Z",
            boxes=[[10.0, 20.0, 100.0, 200.0]],
            scores=[0.95],
            classes=[0],
            source_id="uav-1",
        )
        json_str = json.dumps(asdict(msg))
        parsed = json.loads(json_str)
        restored = DetectionMessage(**parsed)

        assert restored.frame_id == msg.frame_id
        assert restored.boxes == msg.boxes
        assert restored.scores == msg.scores


class TestTrackMessage:
    """Tests for TrackMessage schema."""

    def test_create_track_message(self):
        """Track message should be created with all fields."""
        msg = TrackMessage(
            track_id=5,
            frame_id="frame-1",
            timestamp="2025-01-01T00:00:00Z",
            bbox=[10.0, 20.0, 100.0, 200.0],
            confidence=0.93,
            class_id=0,
            class_name="fire",
        )
        assert msg.track_id == 5
        assert msg.confidence == 0.93
        assert msg.class_name == "fire"

    def test_track_message_immutable(self):
        """Track message should be immutable."""
        msg = TrackMessage(
            track_id=1,
            frame_id="test",
            timestamp="2025-01-01T00:00:00Z",
        )
        with pytest.raises(AttributeError):
            msg.track_id = 999

    def test_track_message_serialization_roundtrip(self):
        """Track message should survive JSON roundtrip."""
        msg = TrackMessage(
            track_id=3,
            frame_id="frame-5",
            timestamp="2025-01-01T00:00:00Z",
            bbox=[50.0, 60.0, 150.0, 250.0],
            confidence=0.88,
            class_id=1,
            class_name="smoke",
        )
        json_str = json.dumps(asdict(msg))
        parsed = json.loads(json_str)
        restored = TrackMessage(**parsed)

        assert restored.track_id == msg.track_id
        assert restored.bbox == msg.bbox
        assert restored.class_name == "smoke"
