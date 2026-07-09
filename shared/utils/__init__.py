"""Shared utility functions."""

from shared.utils.logging import setup_logging

__all__ = ["setup_logging", "encode_image", "decode_image"]


def __getattr__(name: str):
    # Lazy import: encode_image/decode_image require cv2, which is only
    # installed by services that actually handle image data.
    if name in ("encode_image", "decode_image"):
        from shared.utils import image

        return getattr(image, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
