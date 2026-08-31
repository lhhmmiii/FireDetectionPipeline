"""Tracker interface and simple IoU-based implementation.

Every tracker must implement the BaseTracker interface.
This allows swapping algorithms (DeepSORT, ByteTrack, BoT-SORT, etc.)
without changing the Tracking Service or downstream consumers.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

from shared.schemas.messages import DetectionMessage, TrackMessage

logger = logging.getLogger(__name__)

# Class name lookup
CLASS_NAMES = {0: "fire", 1: "smoke"}


@dataclass
class Track:
    """Internal track state."""

    track_id: int
    bbox: list[float]
    confidence: float
    class_id: int
    hits: int = 1 # The number of times this track has been updated with a detection
    age: int = 0 # The total number of frames since the track was created
    time_since_update: int = 0 # The number of frames since the track was last updated with a detection


class BaseTracker(ABC):
    """Abstract base class for multi-object trackers.

    Subclass this and implement `update` to integrate a new tracking algorithm.
    """

    @abstractmethod
    def update(
        self,
        detection: DetectionMessage,
    ) -> list[TrackMessage]:
        """Update tracks with new detections.

        Args:
            detection: DetectionMessage containing boxes, scores, classes.

        Returns:
            List of TrackMessage for active tracks.
        """


def _iou(box_a: list[float], box_b: list[float]) -> float:
    """Compute Intersection over Union between two boxes [x1, y1, x2, y2]."""
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])

    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    union = area_a + area_b - inter

    return inter / union if union > 0 else 0.0


class SimpleIoUTracker(BaseTracker):
    """Simple IoU-based multi-object tracker.

    Associates detections to existing tracks based on IoU overlap.
    This is a basic placeholder tracker - for production, consider
    replacing with DeepSORT, ByteTrack, or BoT-SORT.

    Args:
        max_age: Maximum frames a track survives without updates.
        min_hits: Minimum hits before a track is reported.
        iou_threshold: Minimum IoU to associate a detection with a track.
    """

    def __init__(
        self,
        max_age: int = 30,
        min_hits: int = 3,
        iou_threshold: float = 0.3,
    ) -> None:
        self._max_age = max_age
        self._min_hits = min_hits
        self._iou_threshold = iou_threshold
        self._tracks_by_source: dict[str, list[Track]] = {}
        self._next_id = 1

    def update(
        self,
        detection: DetectionMessage,
    ) -> list[TrackMessage]:
        """Update tracks with new detections using greedy IoU matching.

        Matching and aging are scoped to the detection's source_id, so each
        source is tracked independently even though all sources share one tracker.

        Args:
            detection: DetectionMessage from the 'detections' topic.

        Returns:
            List of TrackMessage for tracks that meet min_hits threshold.
        """
        boxes = detection.boxes if isinstance(detection, DetectionMessage) else detection.get("boxes", [])
        scores = detection.scores if isinstance(detection, DetectionMessage) else detection.get("scores", [])
        classes = detection.classes if isinstance(detection, DetectionMessage) else detection.get("classes", [])
        frame_id = detection.frame_id if isinstance(detection, DetectionMessage) else detection.get("frame_id", "")
        timestamp = detection.timestamp if isinstance(detection, DetectionMessage) else detection.get("timestamp", "")
        source_id = detection.source_id if isinstance(detection, DetectionMessage) else detection.get("source_id", "default")
        frame_width = detection.frame_width if isinstance(detection, DetectionMessage) else detection.get("frame_width", 0)
        frame_height = detection.frame_height if isinstance(detection, DetectionMessage) else detection.get("frame_height", 0)

        # Operate only on this source's track bucket.
        tracks = self._tracks_by_source.setdefault(source_id, [])

        # Age all existing tracks for this source
        for track in tracks:
            track.age += 1
            track.time_since_update += 1

        # Match detections to tracks (greedy, highest IoU first)
        matched_dets: set[int] = set()

        if tracks and boxes:
            # Build IoU matrix
            iou_matrix = np.zeros((len(tracks), len(boxes)))
            for t_idx, track in enumerate(tracks):
                for d_idx, box in enumerate(boxes):
                    iou_matrix[t_idx, d_idx] = _iou(track.bbox, box)

            # Greedy matching
            while True:
                max_val = iou_matrix.max()
                if max_val < self._iou_threshold:
                    break
                t_idx, d_idx = np.unravel_index(
                    iou_matrix.argmax(), iou_matrix.shape
                )
                t_idx, d_idx = int(t_idx), int(d_idx)

                # Update matched track
                tracks[t_idx].bbox = boxes[d_idx]
                tracks[t_idx].confidence = scores[d_idx] if d_idx < len(scores) else 0.0
                tracks[t_idx].class_id = classes[d_idx] if d_idx < len(classes) else 0
                tracks[t_idx].hits += 1
                tracks[t_idx].time_since_update = 0

                matched_dets.add(d_idx)

                # Remove row and column from consideration
                iou_matrix[t_idx, :] = 0
                iou_matrix[:, d_idx] = 0

        # Create new tracks for unmatched detections
        for d_idx in range(len(boxes)):
            if d_idx not in matched_dets:
                new_track = Track(
                    track_id=self._next_id,
                    bbox=boxes[d_idx],
                    confidence=scores[d_idx] if d_idx < len(scores) else 0.0,
                    class_id=classes[d_idx] if d_idx < len(classes) else 0,
                )
                tracks.append(new_track)
                self._next_id += 1

        # Remove dead tracks
        tracks = [
            t for t in tracks
            if t.time_since_update <= self._max_age
        ]
        self._tracks_by_source[source_id] = tracks

        # Build output for tracks that meet min_hits
        results: list[TrackMessage] = []
        for track in tracks:
            if track.hits >= self._min_hits and track.time_since_update == 0:
                results.append(
                    TrackMessage(
                        track_id=track.track_id,
                        frame_id=frame_id,
                        timestamp=timestamp,
                        bbox=track.bbox,
                        confidence=track.confidence,
                        class_id=track.class_id,
                        class_name=CLASS_NAMES.get(track.class_id, "unknown"),
                        source_id=source_id,
                        frame_width=frame_width,
                        frame_height=frame_height,
                    )
                )

        return results
