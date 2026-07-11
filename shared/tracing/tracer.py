"""Lightweight tracing SDK for pipeline stage instrumentation.

Emits SpanMessage records to the 'metrics' Kafka topic so the monitoring
service can compute per-stage latency, Kafka transit latency, end-to-end
latency, throughput, and dropped-frame rates.

Publishing a span must never crash or block the host service's main loop —
the same "error resilience" principle CLAUDE.md requires for the pipeline's
primary Kafka traffic applies to metrics as well.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from shared.schemas.messages import SpanMessage

logger = logging.getLogger(__name__)


class Tracer:
    """Emits SpanMessage records for a single pipeline stage.

    Args:
        stage: Name of the pipeline stage (e.g. "frame_extractor", "detection").
        producer: A KafkaJsonProducer targeting the metrics topic, or None
            to disable tracing (span()/record_dropped() become no-ops).
        enabled: Set False to disable tracing regardless of producer.
    """

    def __init__(self, stage: str, producer: Any | None, enabled: bool = True) -> None:
        self._stage = stage
        self._producer = producer
        self._enabled = enabled and producer is not None

    @contextmanager
    def span(
        self,
        operation: str,
        trace_id: str,
        source_id: str = "default",
    ) -> Iterator[None]:
        """Time a block of code and emit a span on completion.

        Emits status="ok" on clean exit, or status="error" if the block
        raises (the exception is always re-raised — tracing never swallows
        real errors).
        """
        if not self._enabled:
            yield
            return

        start_time = datetime.now(timezone.utc).isoformat()
        start = time.monotonic()
        try:
            yield
        except Exception as exc:
            self._emit(
                operation=operation,
                trace_id=trace_id,
                source_id=source_id,
                start_time=start_time,
                duration_ms=(time.monotonic() - start) * 1000,
                status="error",
                error=str(exc),
            )
            raise
        else:
            self._emit(
                operation=operation,
                trace_id=trace_id,
                source_id=source_id,
                start_time=start_time,
                duration_ms=(time.monotonic() - start) * 1000,
                status="ok",
            )

    def record_dropped(
        self,
        operation: str,
        trace_id: str | None = None,
        source_id: str = "default",
        reason: str = "",
    ) -> None:
        """Emit a zero-duration span marking a dropped frame/message."""
        if not self._enabled:
            return

        self._emit(
            operation=operation,
            trace_id=trace_id or str(uuid.uuid4()),
            source_id=source_id,
            start_time=datetime.now(timezone.utc).isoformat(),
            duration_ms=0.0,
            status="dropped",
            error=reason,
        )

    def _emit(
        self,
        operation: str,
        trace_id: str,
        source_id: str,
        start_time: str,
        duration_ms: float,
        status: str,
        error: str = "",
    ) -> None:
        message = SpanMessage(
            trace_id=trace_id,
            span_id=str(uuid.uuid4()),
            stage=self._stage,
            operation=operation,
            start_time=start_time,
            duration_ms=duration_ms,
            status=status,
            source_id=source_id,
            error=error,
        )
        try:
            self._producer.produce(message, key=trace_id)
        except Exception:
            logger.warning("Failed to emit span for '%s', dropping metric", operation)
