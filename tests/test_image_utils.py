"""Unit tests for image encoding/decoding utilities."""

import numpy as np
import pytest

from shared.utils.image import decode_image, encode_image, resize_image


class TestEncodeImage:
    """Tests for encode_image."""

    def test_encode_returns_string(self):
        """Encoded image should be a base64 string."""
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        result = encode_image(image)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_encode_different_qualities(self):
        """Higher quality should produce larger output."""
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        low_q = encode_image(image, quality=10)
        high_q = encode_image(image, quality=95)
        # Higher quality generally produces larger output
        assert len(high_q) >= len(low_q)

    def test_encode_handles_single_pixel(self):
        """Should encode a 1x1 image."""
        image = np.array([[[128, 128, 128]]], dtype=np.uint8)
        result = encode_image(image)
        assert isinstance(result, str)


class TestDecodeImage:
    """Tests for decode_image."""

    def test_roundtrip(self):
        """Encoding then decoding should produce similar image."""
        # Use a larger image with smooth gradients (less JPEG distortion)
        original = np.zeros((200, 200, 3), dtype=np.uint8)
        original[:, :, 0] = np.tile(np.arange(200, dtype=np.uint8), (200, 1))
        original[:, :, 1] = np.tile(np.arange(200, dtype=np.uint8).reshape(-1, 1), (1, 200))
        original[:, :, 2] = 128

        encoded = encode_image(original, quality=100)
        decoded = decode_image(encoded)

        assert decoded.shape == original.shape
        # JPEG is lossy even at quality=100, allow reasonable tolerance
        assert np.allclose(original, decoded, atol=5)

    def test_decode_preserves_dimensions(self):
        """Decoded image should have same dimensions as original."""
        for shape in [(100, 200, 3), (480, 640, 3), (1, 1, 3)]:
            original = np.zeros(shape, dtype=np.uint8)
            encoded = encode_image(original)
            decoded = decode_image(encoded)
            assert decoded.shape == shape

    def test_decode_invalid_data_raises(self):
        """Invalid base64 data should raise ValueError."""
        with pytest.raises(ValueError):
            decode_image("not_valid_base64!!!")

    def test_decode_empty_string_raises(self):
        """Empty string should raise ValueError."""
        with pytest.raises(ValueError):
            decode_image("")


class TestResizeImage:
    """Tests for resize_image."""

    def test_resize_to_target_dimensions(self):
        """Resize should produce exact target dimensions."""
        image = np.zeros((480, 640, 3), dtype=np.uint8)
        resized = resize_image(image, width=320, height=240)
        assert resized.shape == (240, 320, 3)

    def test_resize_upscale(self):
        """Resize should handle upscaling."""
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        resized = resize_image(image, width=500, height=500)
        assert resized.shape == (500, 500, 3)

    def test_resize_preserves_channels(self):
        """Resize should preserve number of channels."""
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        resized = resize_image(image, width=50, height=50)
        assert resized.shape[2] == 3
