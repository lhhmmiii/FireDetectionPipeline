"""Monitoring Service.

Consumes SpanMessage records from the Kafka 'metrics' topic (produced by
every other service via the shared/tracing SDK), aggregates them into
per-stage latency/throughput/drop-rate stats plus Kafka transit and
end-to-end latency, and serves a small dashboard over WebSocket + REST.

Also supports saving a labeled "baseline" snapshot to disk and comparing
it against the live window, so a model/code change can be measured
before vs. after.

Features:
- Background Kafka consumer thread feeding a MetricsAggregator
- Periodic WebSocket broadcast of the live aggregate snapshot
- Baseline save/list/get/compare endpoints backed by JSON files
- Health check endpoint
- Graceful shutdown
"""

from __future__ import annotations

import asyncio
import json
import re
import signal
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add project root to path for shared imports
sys.path.insert(0, "/app")

from shared.config import KafkaSettings, MonitoringSettings
from shared.kafka import KafkaJsonConsumer
from shared.utils import setup_logging

from aggregator import MetricsAggregator

logger = setup_logging("monitoring")

_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# --- Connection Manager ---


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
        logger.info("WebSocket client connected (%d total)", len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
        logger.info("WebSocket client disconnected (%d total)", len(self._connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        disconnected: list[WebSocket] = []
        async with self._lock:
            for ws in self._connections:
                try:
                    await ws.send_json(message)
                except Exception:
                    disconnected.append(ws)
            for ws in disconnected:
                self._connections.remove(ws)


# --- Kafka Consumer Thread ---


class KafkaMetricsConsumer:
    """Background thread that consumes spans from Kafka into the aggregator."""

    def __init__(
        self,
        kafka_settings: KafkaSettings,
        aggregator: MetricsAggregator,
        lock: threading.Lock,
    ) -> None:
        self._kafka_settings = kafka_settings
        self._aggregator = aggregator
        self._lock = lock
        self._consumer: KafkaJsonConsumer | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(
            target=self._consume_loop,
            daemon=True,
            name="kafka-metrics-consumer",
        )
        self._thread.start()
        logger.info("Kafka metrics consumer thread started")

    def _consume_loop(self) -> None:
        try:
            self._consumer = KafkaJsonConsumer(
                bootstrap_servers=self._kafka_settings.bootstrap_servers,
                topic=self._kafka_settings.topic_metrics,
                group_id="monitoring-service",
            )

            def on_message(message: dict) -> None:
                with self._lock:
                    self._aggregator.record(message)

            self._consumer.consume(callback=on_message)
        except Exception:
            logger.exception("Kafka metrics consumer thread crashed")

    def stop(self) -> None:
        self._running = False
        if self._consumer:
            self._consumer.stop()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Kafka metrics consumer thread stopped")


# --- Baseline storage ---


def _validate_label(label: str) -> None:
    if not _LABEL_PATTERN.match(label):
        raise HTTPException(
            status_code=400,
            detail="label must match [A-Za-z0-9_-]{1,64}",
        )


def _baseline_path(baseline_dir: str, label: str) -> Path:
    _validate_label(label)
    return Path(baseline_dir) / f"{label}.json"


def _diff(baseline: Any, live: Any) -> Any:
    """Recursively diff two snapshot structures, adding deltas at numeric leaves."""
    if isinstance(baseline, dict) and isinstance(live, dict):
        keys = set(baseline) | set(live)
        return {k: _diff(baseline.get(k), live.get(k)) for k in keys}
    if isinstance(baseline, (int, float)) and isinstance(live, (int, float)):
        return {"baseline": baseline, "live": live, "delta": live - baseline}
    return {"baseline": baseline, "live": live}


# --- Application ---

manager = ConnectionManager()
aggregator_lock = threading.Lock()
aggregator: MetricsAggregator | None = None
kafka_consumer: KafkaMetricsConsumer | None = None
broadcast_task: asyncio.Task | None = None

BROADCAST_INTERVAL_SECONDS = 1.0


async def broadcast_snapshots() -> None:
    """Periodically push the live aggregate snapshot to WebSocket clients."""
    while True:
        try:
            await asyncio.sleep(BROADCAST_INTERVAL_SECONDS)
            with aggregator_lock:
                snapshot = aggregator.snapshot()
            await manager.broadcast(snapshot)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Error broadcasting metrics snapshot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: start/stop Kafka consumer and broadcast task."""
    global aggregator, kafka_consumer, broadcast_task

    kafka_settings = KafkaSettings()
    monitoring_settings = MonitoringSettings()

    Path(monitoring_settings.baseline_dir).mkdir(parents=True, exist_ok=True)

    aggregator = MetricsAggregator(window_seconds=monitoring_settings.window_seconds)

    kafka_consumer = KafkaMetricsConsumer(kafka_settings, aggregator, aggregator_lock)
    kafka_consumer.start()

    broadcast_task = asyncio.create_task(broadcast_snapshots())

    logger.info("Monitoring service started")
    yield

    if broadcast_task:
        broadcast_task.cancel()
        try:
            await broadcast_task
        except asyncio.CancelledError:
            pass
    if kafka_consumer:
        kafka_consumer.stop()
    logger.info("Monitoring service stopped")


app = FastAPI(
    title="Fire Detection Pipeline Monitoring",
    version="1.0.0",
    lifespan=lifespan,
)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def index():
    """Serve the monitoring dashboard HTML page."""
    return FileResponse(str(static_dir / "index.html"))


@app.get("/health")
async def health():
    """Health check endpoint."""
    return JSONResponse({"status": "healthy", "service": "monitoring"})


@app.get("/api/metrics/live")
async def live_metrics():
    """Current aggregated snapshot over the rolling window."""
    with aggregator_lock:
        return JSONResponse(aggregator.snapshot())


class BaselineRequest(BaseModel):
    label: str


@app.post("/api/baseline")
async def save_baseline(body: BaselineRequest):
    """Save the current live snapshot as a labeled baseline."""
    settings = MonitoringSettings()
    path = _baseline_path(settings.baseline_dir, body.label)
    with aggregator_lock:
        snapshot = aggregator.snapshot()
    path.write_text(json.dumps(snapshot, indent=2))
    logger.info("Saved baseline '%s'", body.label)
    return JSONResponse(snapshot)


@app.get("/api/baseline")
async def list_baselines():
    """List saved baseline labels."""
    settings = MonitoringSettings()
    baseline_dir = Path(settings.baseline_dir)
    if not baseline_dir.exists():
        return JSONResponse({"labels": []})
    labels = sorted(p.stem for p in baseline_dir.glob("*.json"))
    return JSONResponse({"labels": labels})


@app.get("/api/baseline/{label}")
async def get_baseline(label: str):
    """Return a previously saved baseline snapshot."""
    settings = MonitoringSettings()
    path = _baseline_path(settings.baseline_dir, label)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No baseline named '{label}'")
    return JSONResponse(json.loads(path.read_text()))


@app.get("/api/baseline/{label}/compare")
async def compare_baseline(label: str):
    """Compare a saved baseline against the current live snapshot."""
    settings = MonitoringSettings()
    path = _baseline_path(settings.baseline_dir, label)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No baseline named '{label}'")

    baseline_snapshot = json.loads(path.read_text())
    with aggregator_lock:
        live_snapshot = aggregator.snapshot()

    return JSONResponse(
        {
            "baseline": baseline_snapshot,
            "live": live_snapshot,
            "diff": _diff(baseline_snapshot, live_snapshot),
        }
    )


@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    """WebSocket endpoint for streaming aggregate metric snapshots to the browser."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug("Received from client: %s", data)
    except WebSocketDisconnect:
        await manager.disconnect(websocket)


def main() -> None:
    """Entry point for the Monitoring service."""
    settings = MonitoringSettings()
    logger.info("Starting Monitoring service on %s:%d", settings.host, settings.port)

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
