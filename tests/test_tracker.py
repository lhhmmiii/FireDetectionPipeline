"""Unit tests for the tracker interface and SimpleIoUTracker."""

import sys
import os

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.tracking.tracker import BaseTracker, SimpleIoUTracker, _iou
from shared.schemas.messages import DetectionMessage, TrackMessage


class TestIoU:
    """Tests for the IoU computation function."""

    def test_identical_boxes(self):
        """Identical boxes should have IoU of 1.0."""
        box = [0, 0, 100, 100]
        assert _iou(box, box) == pytest.approx(1.0)

    def test_no_overlap(self):
        """Non-overlapping boxes should have IoU of 0.0."""
        box_a = [0, 0, 50, 50]
        box_b = [100, 100, 200, 200]
        assert _iou(box_a, box_b) == pytest.approx(0.0)

    def test_partial_overlap(self):
        """Partially overlapping boxes should have IoU between 0 and 1."""
        box_a = [0, 0, 100, 100]
        box_b = [50, 50, 150, 150]
        iou = _iou(box_a, box_b)
        assert 0 < iou < 1

    def test_contained_box(self):
        """Box contained within another should have non-zero IoU."""
        outer = [0, 0, 100, 100]
        inner = [25, 25, 75, 75]
        iou = _iou(outer, inner)
        assert iou > 0

    def test_zero_area_box(self):
        """Zero-area box should return IoU of 0."""
        box_a = [50, 50, 50, 50]  # zero area
        box_b = [0, 0, 100, 100]
        assert _iou(box_a, box_b) == pytest.approx(0.0)


class TestSimpleIoUTracker:
    """Tests for SimpleIoUTracker."""

    def _make_detection(self, boxes, scores=None, classes=None, frame_id="f1", source_id="test"):
        """Helper to create a detection dict."""
        if scores is None:
            scores = [0.9] * len(boxes)
        if classes is None:
            classes = [0] * len(boxes)
        return {
            "frame_id": frame_id,
            "timestamp": "2025-01-01T00:00:00Z",
            "boxes": boxes,
            "scores": scores,
            "classes": classes,
            "source_id": source_id,
        }

    def test_empty_detection(self):
        """Empty detection should return no tracks."""
        tracker = SimpleIoUTracker(min_hits=1)
        detection = self._make_detection(boxes=[])
        tracks = tracker.update(detection)
        assert tracks == []

    def test_single_detection_creates_track(self):
        """Single detection should create a track after min_hits."""
        tracker = SimpleIoUTracker(min_hits=1)
        detection = self._make_detection(
            boxes=[[10, 20, 100, 200]],
            scores=[0.9],
            classes=[0],
        )
        tracks = tracker.update(detection)
        assert len(tracks) == 1
        assert tracks[0].track_id == 1
        assert tracks[0].confidence == 0.9

    def test_track_assignment_across_frames(self):
        """Same object across frames should keep the same track ID."""
        tracker = SimpleIoUTracker(min_hits=1, iou_threshold=0.3)

        # Frame 1
        det1 = self._make_detection(
            boxes=[[10, 20, 100, 200]],
            frame_id="f1",
        )
        tracks1 = tracker.update(det1)
        track_id = tracks1[0].track_id

        # Frame 2 — slightly moved
        det2 = self._make_detection(
            boxes=[[15, 25, 105, 205]],
            frame_id="f2",
        )
        tracks2 = tracker.update(det2)
        assert len(tracks2) == 1
        assert tracks2[0].track_id == track_id

    def test_new_object_gets_new_id(self):
        """A new non-overlapping object should get a new track ID."""
        tracker = SimpleIoUTracker(min_hits=1)

        det1 = self._make_detection(
            boxes=[[0, 0, 50, 50]],
            frame_id="f1",
        )
        tracks1 = tracker.update(det1)

        # Completely different location
        det2 = self._make_detection(
            boxes=[[0, 0, 50, 50], [500, 500, 600, 600]],
            frame_id="f2",
        )
        tracks2 = tracker.update(det2)
        track_ids = {t.track_id for t in tracks2}
        assert len(track_ids) == 2

    def test_track_dies_after_max_age(self):
        """Track should be removed after max_age frames without updates."""
        tracker = SimpleIoUTracker(min_hits=1, max_age=2)

        # Create a track
        det = self._make_detection(boxes=[[10, 20, 100, 200]])
        tracker.update(det)

        # Feed empty detections to age out the track
        for i in range(3):
            tracker.update(self._make_detection(boxes=[], frame_id=f"f{i+2}"))

        # New detection should get a new ID
        det_new = self._make_detection(
            boxes=[[10, 20, 100, 200]],
            frame_id="f10",
        )
        tracks = tracker.update(det_new)
        assert len(tracks) == 1
        assert tracks[0].track_id > 1  # New ID

    def test_min_hits_threshold(self):
        """Track should not be reported until min_hits is reached."""
        tracker = SimpleIoUTracker(min_hits=3, iou_threshold=0.3)

        box = [10, 20, 100, 200]

        # First two frames — should not report
        for i in range(2):
            tracks = tracker.update(
                self._make_detection(boxes=[box], frame_id=f"f{i}")
            )
            assert len(tracks) == 0

        # Third frame — should report
        tracks = tracker.update(
            self._make_detection(boxes=[box], frame_id="f3")
        )
        assert len(tracks) == 1

    def test_output_is_track_message(self):
        """Output should be list of TrackMessage instances."""
        tracker = SimpleIoUTracker(min_hits=1)
        det = self._make_detection(
            boxes=[[10, 20, 100, 200]],
            scores=[0.85],
            classes=[1],
        )
        tracks = tracker.update(det)
        assert len(tracks) == 1

        track = tracks[0]
        assert isinstance(track, TrackMessage)
        assert track.class_id == 1
        assert track.class_name == "smoke"
        assert track.confidence == 0.85


class TestMultiSourceTracking:
    """Tests that tracker state is isolated per source_id (multi-source / multi-stream)."""

    def _make_detection(self, boxes, source_id, frame_id="f1", scores=None, classes=None):
        if scores is None:
            scores = [0.9] * len(boxes)
        if classes is None:
            classes = [0] * len(boxes)
        return {
            "frame_id": frame_id,
            "timestamp": "2025-01-01T00:00:00Z",
            "boxes": boxes,
            "scores": scores,
            "classes": classes,
            "source_id": source_id,
        }

    def test_overlapping_boxes_from_different_sources_do_not_match(self):
        """Identical boxes from two sources must stay separate tracks."""
        tracker = SimpleIoUTracker(min_hits=1, iou_threshold=0.3)
        box = [[10, 20, 100, 200]]

        tracks_a = tracker.update(self._make_detection(box, source_id="cam-a", frame_id="a1"))
        tracks_b = tracker.update(self._make_detection(box, source_id="cam-b", frame_id="b1"))

        assert len(tracks_a) == 1
        assert len(tracks_b) == 1
        # Same image-space box but different sources → distinct track IDs.
        assert tracks_a[0].track_id != tracks_b[0].track_id
        assert tracks_a[0].source_id == "cam-a"
        assert tracks_b[0].source_id == "cam-b"

    def test_track_ids_stable_per_source_when_interleaved(self):
        """Interleaved updates keep each source's track ID across frames."""
        tracker = SimpleIoUTracker(min_hits=1, iou_threshold=0.3)

        a1 = tracker.update(self._make_detection([[10, 20, 100, 200]], "cam-a", "a1"))
        b1 = tracker.update(self._make_detection([[500, 500, 600, 700]], "cam-b", "b1"))
        # Move each object slightly and interleave again.
        a2 = tracker.update(self._make_detection([[15, 25, 105, 205]], "cam-a", "a2"))
        b2 = tracker.update(self._make_detection([[505, 505, 605, 705]], "cam-b", "b2"))

        assert a2[0].track_id == a1[0].track_id
        assert b2[0].track_id == b1[0].track_id
        assert a2[0].track_id != b2[0].track_id

    def test_source_not_aged_by_other_source_updates(self):
        """One source's frames must not age out another source's tracks."""
        tracker = SimpleIoUTracker(min_hits=1, max_age=2)

        # Establish a track on cam-b.
        b1 = tracker.update(self._make_detection([[10, 20, 100, 200]], "cam-b", "b1"))
        original_id = b1[0].track_id

        # Hammer cam-a with more frames than max_age; cam-b must be untouched.
        for i in range(5):
            tracker.update(self._make_detection([[0, 0, 50, 50]], "cam-a", f"a{i}"))

        # cam-b sees the same object again → same track ID (not aged out).
        b2 = tracker.update(self._make_detection([[10, 20, 100, 200]], "cam-b", "b2"))
        assert b2[0].track_id == original_id


class TestBaseTrackerInterface:
    """Tests for the BaseTracker abstract interface."""

    def test_cannot_instantiate_base_tracker(self):
        """BaseTracker should not be instantiable directly."""
        with pytest.raises(TypeError):
            BaseTracker()
