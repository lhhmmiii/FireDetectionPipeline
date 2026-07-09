"""Unit tests for the detector interface."""

import numpy as np
import pytest

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.detection.detector import BaseDetector
from shared.schemas.messages import DetectionResult


class TestBaseDetectorInterface:
    """Tests for the BaseDetector abstract interface."""

    def test_cannot_instantiate_base_detector(self):
        """BaseDetector should not be instantiable directly."""
        with pytest.raises(TypeError):
            BaseDetector()

    def test_subclass_must_implement_methods(self):
        """Subclass without implementations should raise TypeError."""

        class IncompleteDetector(BaseDetector):
            pass

        with pytest.raises(TypeError):
            IncompleteDetector()

    def test_custom_detector_implementation(self):
        """Custom detector implementing interface should work."""

        class MockDetector(BaseDetector):
            def load(self, model_path, device="cpu"):
                self.loaded = True

            def predict(self, image, confidence_threshold=0.5):
                return DetectionResult(
                    boxes=[[0, 0, 100, 100]],
                    scores=[0.99],
                    classes=[0],
                )

        detector = MockDetector()
        detector.load("mock.pt")
        assert detector.loaded

        result = detector.predict(np.zeros((100, 100, 3), dtype=np.uint8))
        assert len(result.boxes) == 1
        assert result.scores[0] == 0.99
