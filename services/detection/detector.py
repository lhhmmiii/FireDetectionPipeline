"""Detection model interface.

Every detection model must implement the BaseDetector interface.
This allows swapping models (RF-DETR, YOLO, GroundingDINO, etc.)
without changing the Detection Service or downstream consumers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from shared.schemas.messages import DetectionResult


class BaseDetector(ABC):
    """Abstract base class for all fire detection models.

    Subclass this and implement `predict` to integrate a new model.
    The Detection Service only depends on this interface.
    """

    @abstractmethod
    def load(self, model_path: str, device: str = "cpu") -> None:
        """Load model weights from disk.

        Args:
            model_path: Path to the model weights file.
            device: Target device ('cpu', 'cuda', 'cuda:0', etc.).
        """

    @abstractmethod
    def predict(
        self,
        image: np.ndarray,
        confidence_threshold: float = 0.5,
    ) -> DetectionResult:
        """Run inference on a single image.

        Args:
            image: Input image as numpy array (H, W, C) in BGR format.
            confidence_threshold: Minimum confidence to keep a detection.

        Returns:
            DetectionResult with boxes, scores, and class IDs.
        """
