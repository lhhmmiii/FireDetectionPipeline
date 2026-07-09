"""Configuration management."""

from shared.config.settings import (
    DashboardSettings,
    DetectionSettings,
    KafkaSettings,
    RTSPSettings,
    TrackingSettings,
)

__all__ = [
    "KafkaSettings",
    "RTSPSettings",
    "DetectionSettings",
    "TrackingSettings",
    "DashboardSettings",
]
