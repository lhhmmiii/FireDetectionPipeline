"""Unit tests for the monitoring service's MetricsAggregator."""

import os
import sys

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.monitoring.aggregator import MetricsAggregator


def _span(stage, operation, start_time, duration_ms=10.0, status="ok", trace_id="frame-1", source_id="uav-1"):
    return {
        "trace_id": trace_id,
        "span_id": f"{stage}-span",
        "stage": stage,
        "operation": operation,
        "start_time": start_time,
        "duration_ms": duration_ms,
        "status": status,
        "source_id": source_id,
        "error": "",
    }


class TestPerStageStats:
    def test_counts_and_latency_percentiles(self):
        agg = MetricsAggregator(window_seconds=60.0)
        for i, dur in enumerate([10.0, 20.0, 30.0, 40.0]):
            agg.record(_span("detection", "detect", "2025-01-01T00:00:00+00:00", duration_ms=dur, trace_id=f"f{i}"))

        snap = agg.snapshot()
        stage = snap["stages"]["detection"]
        assert stage["count"] == 4
        # Nearest-rank percentile over the sorted [10, 20, 30, 40] durations.
        assert stage["p50_ms"] == 20.0
        assert stage["p95_ms"] == 30.0
        assert stage["throughput_fps"] == 4 / 60.0

    def test_dropped_and_error_count_as_failures(self):
        agg = MetricsAggregator(window_seconds=60.0)
        agg.record(_span("frame_extractor", "extract_frame", "2025-01-01T00:00:00+00:00", status="ok", trace_id="f1"))
        agg.record(_span("frame_extractor", "extract_frame", "2025-01-01T00:00:01+00:00", status="dropped", trace_id="f2"))
        agg.record(_span("frame_extractor", "extract_frame", "2025-01-01T00:00:02+00:00", status="error", trace_id="f3"))

        snap = agg.snapshot()
        stage = snap["stages"]["frame_extractor"]
        assert stage["count"] == 1
        assert stage["dropped_count"] == 2
        assert stage["drop_rate"] == 2 / 3

    def test_empty_stage_reports_none_percentiles(self):
        agg = MetricsAggregator(window_seconds=60.0)
        snap = agg.snapshot()
        stage = snap["stages"]["dashboard"]
        assert stage["count"] == 0
        assert stage["p50_ms"] is None
        assert stage["p95_ms"] is None
        assert stage["drop_rate"] == 0.0


class TestCorrelatedLatency:
    def test_kafka_transit_and_end_to_end_latency(self):
        agg = MetricsAggregator(window_seconds=60.0)

        # Same trace_id across all four stages, 100ms apart, each span takes 10ms.
        agg.record(_span("frame_extractor", "extract_frame", "2025-01-01T00:00:00.000000+00:00", duration_ms=10.0))
        agg.record(_span("detection", "detect", "2025-01-01T00:00:00.110000+00:00", duration_ms=10.0))
        agg.record(_span("tracking", "track", "2025-01-01T00:00:00.220000+00:00", duration_ms=10.0))
        agg.record(_span("dashboard", "dashboard_receive", "2025-01-01T00:00:00.330000+00:00", duration_ms=10.0))

        snap = agg.snapshot()

        # frame_extractor span ends at .010, detection starts at .110 -> ~100ms transit.
        assert snap["kafka_transit"]["frames"]["p50_ms"] == pytest.approx(100.0, abs=0.5)
        assert snap["kafka_transit"]["detections"]["p50_ms"] == pytest.approx(100.0, abs=0.5)
        assert snap["kafka_transit"]["tracks"]["p50_ms"] == pytest.approx(100.0, abs=0.5)

        # end-to-end: dashboard start (.330) - frame_extractor start (.000) = 330ms.
        assert snap["end_to_end"]["p50_ms"] == pytest.approx(330.0, abs=0.5)
        assert snap["end_to_end"]["count"] == 1

    def test_incomplete_trace_does_not_produce_e2e_latency(self):
        agg = MetricsAggregator(window_seconds=60.0)
        agg.record(_span("frame_extractor", "extract_frame", "2025-01-01T00:00:00.000000+00:00"))
        agg.record(_span("detection", "detect", "2025-01-01T00:00:00.100000+00:00"))
        # No tracking/dashboard span for this trace_id.

        snap = agg.snapshot()
        assert snap["end_to_end"]["count"] == 0
        assert snap["kafka_transit"]["frames"]["count"] == 1
        assert snap["kafka_transit"]["detections"]["count"] == 0


class TestWindowEviction:
    def test_stale_spans_are_evicted_from_snapshot(self, monkeypatch):
        import time as time_module

        agg = MetricsAggregator(window_seconds=5.0)

        current = [1_000_000.0]
        monkeypatch.setattr(time_module, "time", lambda: current[0])

        agg.record(_span("detection", "detect", "2025-01-01T00:00:00+00:00", trace_id="old"))
        assert agg.snapshot()["stages"]["detection"]["count"] == 1

        current[0] += 10.0  # advance well past the 5s window
        assert agg.snapshot()["stages"]["detection"]["count"] == 0
