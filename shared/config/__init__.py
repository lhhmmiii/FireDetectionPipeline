"""Configuration management."""

from shared.config.settings import (
    DashboardSettings,
    DetectionSettings,
    KafkaSettings,
    MetricsSettings,
    MonitoringSettings,
    RTSPSettings,
    TrackingSettings,
)

__all__ = [
    "KafkaSettings",
    "RTSPSettings",
    "DetectionSettings",
    "TrackingSettings",
    "DashboardSettings",
    "MetricsSettings",
    "MonitoringSettings",
]
