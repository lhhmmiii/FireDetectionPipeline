"""Rolling-window aggregation of SpanMessage records into dashboard-ready metrics.

Pure Python, no FastAPI/Kafka imports, so it can be unit tested in isolation
(mirrors the services/tracking/tracker.py separation of business logic from
service wiring).

Correlates spans across stages using trace_id (== the originating frame_id)
to derive Kafka topic-hop transit latency and end-to-end latency, without
any instrumentation inside Kafka itself.
"""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque

STAGE_ORDER = ["frame_extractor", "detection", "tracking", "dashboard"]

# Kafka topic that carries messages between each pair of adjacent stages.
HOP_TOPICS = {
    ("frame_extractor", "detection"): "frames",
    ("detection", "tracking"): "detections",
    ("tracking", "dashboard"): "tracks",
}

_FAILURE_STATUSES = ("dropped", "error")


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def _percentile(sorted_values: list[float], p: float) -> float | None:
    """Nearest-rank percentile over an already-sorted list."""
    if not sorted_values:
        return None
    idx = min(len(sorted_values) - 1, int(p * (len(sorted_values) - 1)))
    return sorted_values[idx]


class MetricsAggregator:
    """Maintains a rolling window of spans and computes aggregate stats.

    Args:
        window_seconds: How far back to keep spans/derived stats for.
    """

    def __init__(self, window_seconds: float = 60.0) -> None:
        self._window_seconds = max(window_seconds, 1e-6)
        self._spans: Deque[tuple[float, dict[str, Any]]] = deque()
        self._transit: dict[str, Deque[tuple[float, float]]] = {
            topic: deque() for topic in HOP_TOPICS.values()
        }
        self._e2e: Deque[tuple[float, float]] = deque()
        # trace_id -> {"first_seen": monotonic_time, stage: span_dict}
        self._pending: dict[str, dict[str, Any]] = {}
        self._pending_order: Deque[tuple[float, str]] = deque()

    def record(self, span: dict[str, Any]) -> None:
        """Record a single deserialized SpanMessage."""
        now = time.time()
        self._spans.append((now, span))

        status = span.get("status")
        stage = span.get("stage")
        trace_id = span.get("trace_id")

        if status == "ok" and stage in STAGE_ORDER and trace_id:
            entry = self._pending.get(trace_id)
            if entry is None:
                entry = {"first_seen": now}
                self._pending[trace_id] = entry
                self._pending_order.append((now, trace_id))
            entry[stage] = span

            idx = STAGE_ORDER.index(stage)
            if idx > 0:
                prev_stage = STAGE_ORDER[idx - 1]
                prev_span = entry.get(prev_stage)
                if prev_span is not None:
                    hop_topic = HOP_TOPICS[(prev_stage, stage)]
                    transit_ms = self._transit_ms(prev_span, span)
                    self._transit[hop_topic].append((now, transit_ms))

            if stage == STAGE_ORDER[-1]:
                first_span = entry.get(STAGE_ORDER[0])
                if first_span is not None:
                    e2e_ms = self._start_delta_ms(first_span, span)
                    self._e2e.append((now, e2e_ms))
                self._pending.pop(trace_id, None)

        self._evict(now)

    @staticmethod
    def _transit_ms(prev_span: dict[str, Any], span: dict[str, Any]) -> float:
        prev_end = _parse_iso(prev_span["start_time"])
        prev_end = prev_end.timestamp() + prev_span.get("duration_ms", 0.0) / 1000.0
        cur_start = _parse_iso(span["start_time"]).timestamp()
        return max(0.0, (cur_start - prev_end) * 1000.0)

    @staticmethod
    def _start_delta_ms(first_span: dict[str, Any], last_span: dict[str, Any]) -> float:
        first_start = _parse_iso(first_span["start_time"]).timestamp()
        last_start = _parse_iso(last_span["start_time"]).timestamp()
        return max(0.0, (last_start - first_start) * 1000.0)

    def _evict(self, now: float) -> None:
        cutoff = now - self._window_seconds

        while self._spans and self._spans[0][0] < cutoff:
            self._spans.popleft()

        for hop_queue in self._transit.values():
            while hop_queue and hop_queue[0][0] < cutoff:
                hop_queue.popleft()

        while self._e2e and self._e2e[0][0] < cutoff:
            self._e2e.popleft()

        while self._pending_order and self._pending_order[0][0] < cutoff:
            _, trace_id = self._pending_order.popleft()
            entry = self._pending.get(trace_id)
            if entry is not None and entry["first_seen"] < cutoff:
                self._pending.pop(trace_id, None)

    def snapshot(self) -> dict[str, Any]:
        """Compute the current window's aggregate stats."""
        now = time.time()
        self._evict(now)

        stages: dict[str, Any] = {}
        for stage in STAGE_ORDER:
            stage_spans = [s for _, s in self._spans if s.get("stage") == stage]
            ok = [s for s in stage_spans if s.get("status") == "ok"]
            failed = [s for s in stage_spans if s.get("status") in _FAILURE_STATUSES]
            durations = sorted(s.get("duration_ms", 0.0) for s in ok)
            total = len(ok) + len(failed)

            stages[stage] = {
                "count": len(ok),
                "throughput_fps": len(ok) / self._window_seconds,
                "p50_ms": _percentile(durations, 0.5),
                "p95_ms": _percentile(durations, 0.95),
                "dropped_count": len(failed),
                "drop_rate": (len(failed) / total) if total else 0.0,
            }

        kafka_transit: dict[str, Any] = {}
        for hop_topic, values in self._transit.items():
            vals = sorted(v for _, v in values)
            kafka_transit[hop_topic] = {
                "p50_ms": _percentile(vals, 0.5),
                "p95_ms": _percentile(vals, 0.95),
                "count": len(vals),
            }

        e2e_vals = sorted(v for _, v in self._e2e)

        return {
            "window_seconds": self._window_seconds,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "stages": stages,
            "kafka_transit": kafka_transit,
            "end_to_end": {
                "p50_ms": _percentile(e2e_vals, 0.5),
                "p95_ms": _percentile(e2e_vals, 0.95),
                "count": len(e2e_vals),
            },
        }
