"""Image encoding and decoding utilities.

Converts between numpy arrays, JPEG bytes, and base64 strings
for efficient transfer through Kafka.
"""

from __future__ import annotations

import base64
import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def encode_image(
    image: np.ndarray,
    quality: int = 85,
) -> str:
    """Encode a numpy image (BGR) to a base64 JPEG string.

    Args:
        image: Input image as a numpy array (H, W, C) in BGR format.
        quality: JPEG compression quality (0-100).

    Returns:
        Base64-encoded JPEG string.

    Raises:
        ValueError: If encoding fails.
    """
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    success, buffer = cv2.imencode(".jpg", image, encode_params)
    if not success:
        raise ValueError("Failed to encode image to JPEG")
    return base64.b64encode(buffer.tobytes()).decode("utf-8")


def decode_image(image_data: str) -> np.ndarray:
    """Decode a base64 JPEG string to a numpy image (BGR).

    Args:
        image_data: Base64-encoded JPEG string.

    Returns:
        Decoded image as a numpy array (H, W, C) in BGR format.

    Raises:
        ValueError: If decoding fails.
    """
    try:
        jpeg_bytes = base64.b64decode(image_data)
        np_arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("cv2.imdecode returned None")
        return image
    except Exception as exc:
        raise ValueError(f"Failed to decode image: {exc}") from exc


def resize_image(
    image: np.ndarray,
    width: int,
    height: int,
) -> np.ndarray:
    """Resize an image to the specified dimensions.

    Args:
        image: Input image as numpy array.
        width: Target width.
        height: Target height.

    Returns:
        Resized image.
    """
    return cv2.resize(image, (width, height), interpolation=cv2.INTER_LINEAR)
