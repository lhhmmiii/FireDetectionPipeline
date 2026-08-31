"""Unit tests for the shared tracing SDK (shared/tracing/tracer.py).

Uses a fake producer instead of a real Kafka connection so these tests
have no network/broker dependency.
"""

import pytest

from shared.tracing import Tracer


class FakeProducer:
    """Records every message passed to produce() for assertions."""

    def __init__(self) -> None:
        self.messages = []

    def produce(self, message, key=None):
        self.messages.append((message, key))


class RaisingProducer:
    """A producer whose produce() always raises, to test failure isolation."""

    def produce(self, message, key=None):
        raise ConnectionError("kafka unavailable")


class TestTracerSpan:
    def test_span_emits_ok_status(self):
        producer = FakeProducer()
        tracer = Tracer(stage="detection", producer=producer)

        with tracer.span("detect", trace_id="frame-1", source_id="camera-1"):
            pass

        assert len(producer.messages) == 1
        message, key = producer.messages[0]
        assert key == "frame-1"
        assert message.trace_id == "frame-1"
        assert message.stage == "detection"
        assert message.operation == "detect"
        assert message.status == "ok"
        assert message.source_id == "camera-1"
        assert message.duration_ms >= 0.0

    def test_span_measures_duration(self):
        import time

        producer = FakeProducer()
        tracer = Tracer(stage="detection", producer=producer)

        with tracer.span("detect", trace_id="frame-1"):
            time.sleep(0.01)

        message, _ = producer.messages[0]
        assert message.duration_ms >= 10.0

    def test_span_emits_error_status_and_reraises(self):
        producer = FakeProducer()
        tracer = Tracer(stage="tracking", producer=producer)

        with pytest.raises(ValueError):
            with tracer.span("track", trace_id="frame-2"):
                raise ValueError("bad detection payload")

        message, _ = producer.messages[0]
        assert message.status == "error"
        assert "bad detection payload" in message.error

    def test_disabled_tracer_span_is_noop(self):
        producer = FakeProducer()
        tracer = Tracer(stage="detection", producer=producer, enabled=False)

        with tracer.span("detect", trace_id="frame-1"):
            pass

        assert producer.messages == []

    def test_tracer_with_no_producer_is_noop(self):
        tracer = Tracer(stage="detection", producer=None)

        with tracer.span("detect", trace_id="frame-1"):
            pass  # should not raise even though there's no producer

    def test_span_publish_failure_does_not_crash_caller(self):
        tracer = Tracer(stage="detection", producer=RaisingProducer())

        with tracer.span("detect", trace_id="frame-1"):
            pass  # the span's own emit failure must be swallowed, not raised


class TestTracerRecordDropped:
    def test_record_dropped_emits_dropped_status(self):
        producer = FakeProducer()
        tracer = Tracer(stage="frame_extractor", producer=producer)

        tracer.record_dropped(
            "extract_frame", trace_id="frame-3", source_id="camera-1", reason="rtsp_read_failed"
        )

        assert len(producer.messages) == 1
        message, key = producer.messages[0]
        assert key == "frame-3"
        assert message.status == "dropped"
        assert message.error == "rtsp_read_failed"
        assert message.duration_ms == 0.0

    def test_record_dropped_generates_trace_id_when_missing(self):
        producer = FakeProducer()
        tracer = Tracer(stage="frame_extractor", producer=producer)

        tracer.record_dropped("extract_frame", source_id="camera-1", reason="rtsp_read_failed")

        message, key = producer.messages[0]
        assert message.trace_id  # non-empty generated UUID
        assert key == message.trace_id

    def test_disabled_tracer_record_dropped_is_noop(self):
        producer = FakeProducer()
        tracer = Tracer(stage="frame_extractor", producer=producer, enabled=False)

        tracer.record_dropped("extract_frame", reason="rtsp_read_failed")

        assert producer.messages == []
