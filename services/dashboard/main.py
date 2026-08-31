"""Dashboard Service.

Serves the dashboard frontend and provides a WebSocket endpoint
that forwards tracking results from Kafka to connected browsers.

The dashboard is a visualization layer only — it never runs inference,
decodes RTSP, or performs tracking.

Features:
- Serves static HTML/CSS/JS frontend
- WebSocket endpoint /ws/tracks for real-time track updates
- Background Kafka consumer thread
- Health check endpoint
- Graceful shutdown
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
import threading
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Add project root to path for shared imports
sys.path.insert(0, "/app")

from shared.config import DashboardSettings, KafkaSettings, MetricsSettings
from shared.kafka import KafkaJsonConsumer, KafkaJsonProducer
from shared.tracing import Tracer
from shared.utils import setup_logging

logger = setup_logging("dashboard")

# --- Connection Manager ---


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
        logger.info("WebSocket client connected (%d total)", len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
        logger.info("WebSocket client disconnected (%d total)", len(self._connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a message to all connected clients."""
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


class KafkaTrackConsumer:
    """Background thread that consumes tracks from Kafka and pushes to an asyncio queue."""

    def __init__(
        self,
        kafka_settings: KafkaSettings,
        queue: asyncio.Queue,
        loop: asyncio.AbstractEventLoop,
        tracer: Tracer,
    ) -> None:
        self._kafka_settings = kafka_settings
        self._queue = queue
        self._loop = loop
        self._tracer = tracer
        self._consumer: KafkaJsonConsumer | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        """Start the background consumer thread."""
        self._running = True
        self._thread = threading.Thread(
            target=self._consume_loop,
            daemon=True,
            name="kafka-track-consumer",
        )
        self._thread.start()
        logger.info("Kafka track consumer thread started")

    def _consume_loop(self) -> None:
        """Blocking consume loop running in a background thread."""
        try:
            self._consumer = KafkaJsonConsumer(
                bootstrap_servers=self._kafka_settings.bootstrap_servers,
                topic=self._kafka_settings.topic_tracks,
                group_id="dashboard-service",
            )

            def on_message(message: dict) -> None:
                if self._running:
                    with self._tracer.span(
                        "dashboard_receive",
                        trace_id=message.get("frame_id", "unknown"),
                        source_id=message.get("source_id", "default"),
                    ):
                        asyncio.run_coroutine_threadsafe(
                            self._queue.put(message), self._loop
                        )

            self._consumer.consume(callback=on_message)
        except Exception:
            logger.exception("Kafka consumer thread crashed")

    def stop(self) -> None:
        """Stop the consumer thread."""
        self._running = False
        if self._consumer:
            self._consumer.stop()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Kafka track consumer thread stopped")


# --- Application ---

manager = ConnectionManager()
track_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
kafka_consumer: KafkaTrackConsumer | None = None
broadcast_task: asyncio.Task | None = None
metrics_producer: KafkaJsonProducer | None = None


async def broadcast_tracks() -> None:
    """Continuously read from the track queue and broadcast to WebSocket clients."""
    while True:
        try:
            message = await track_queue.get()
            await manager.broadcast(message)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Error broadcasting track")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: start/stop Kafka consumer and broadcast task."""
    global kafka_consumer, broadcast_task, metrics_producer

    loop = asyncio.get_event_loop()
    kafka_settings = KafkaSettings()
    metrics_settings = MetricsSettings()

    if metrics_settings.enabled:
        metrics_producer = KafkaJsonProducer(
            bootstrap_servers=kafka_settings.bootstrap_servers,
            topic=kafka_settings.topic_metrics,
        )
        tracer = Tracer(stage="dashboard", producer=metrics_producer)
    else:
        tracer = Tracer(stage="dashboard", producer=None, enabled=False)

    kafka_consumer = KafkaTrackConsumer(kafka_settings, track_queue, loop, tracer)
    kafka_consumer.start()

    broadcast_task = asyncio.create_task(broadcast_tracks())

    logger.info("Dashboard service started")
    yield

    # Shutdown
    if broadcast_task:
        broadcast_task.cancel()
        try:
            await broadcast_task
        except asyncio.CancelledError:
            pass
    if kafka_consumer:
        kafka_consumer.stop()
    if metrics_producer:
        metrics_producer.close()
    logger.info("Dashboard service stopped")


app = FastAPI(
    title="Fire Detection Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

# Static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def index():
    """Serve the dashboard HTML page."""
    return FileResponse(str(static_dir / "index.html"))


@app.get("/health")
async def health():
    """Health check endpoint."""
    return JSONResponse({"status": "healthy", "service": "dashboard"})


@app.get("/api/streams")
async def streams():
    """Configured video streams and the WebRTC gateway base URL."""
    settings = DashboardSettings()
    return JSONResponse(
        {"webrtc_url": settings.webrtc_url, "streams": list(settings.streams)}
    )


@app.websocket("/ws/tracks")
async def websocket_tracks(websocket: WebSocket):
    """WebSocket endpoint for streaming track updates to the browser."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; client can also send messages
            data = await websocket.receive_text()
            logger.debug("Received from client: %s", data)
    except WebSocketDisconnect:
        await manager.disconnect(websocket)


def main() -> None:
    """Entry point for the Dashboard service."""
    settings = DashboardSettings()
    logger.info("Starting Dashboard on %s:%d", settings.host, settings.port)

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
