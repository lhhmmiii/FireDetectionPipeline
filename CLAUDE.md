# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Package manager:** `uv` (Python 3.13, see `uv.lock`)

```bash
# Install dependencies
uv sync

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_schemas.py

# Run a single test
uv run pytest tests/test_detector.py::TestBaseDetectorInterface::test_custom_detector_implementation

# Start the full stack (Kafka + all services)
docker compose up -d

# Start only infrastructure (Kafka)
docker compose up -d kafka

# Rebuild and restart a specific service
docker compose up -d --build frame_extractor

# Follow logs
docker compose logs -f detection
```

## Architecture

Five microservices communicate exclusively through Kafka. Services never call each other directly.

```
UAV → RTSP → MediaMTX (media_gateway)
                 ├─→ RTSP → frame_extractor → Kafka[frames]
                 └─→ WebRTC → dashboard UI
                                  ↑
Kafka[frames] → detection → Kafka[detections] → tracking → Kafka[tracks] → dashboard
```

**Kafka topics and ownership:**

| Topic | Producer | Consumer |
|-------|----------|----------|
| `frames` | frame_extractor | detection |
| `detections` | detection | tracking |
| `tracks` | tracking | dashboard |

**Shared module** (`shared/`) is mounted read-only into every Python service container (`/app/shared`). Services add `/app` to `sys.path` to import from it. It contains:
- `shared/schemas/messages.py` — frozen dataclass Kafka message schemas (`FrameMessage`, `DetectionMessage`, `TrackMessage`)
- `shared/kafka/` — `KafkaJsonProducer`, `KafkaFrameProducer`, `KafkaJsonConsumer`
- `shared/config/settings.py` — frozen dataclass settings loaded from env vars
- `shared/utils/` — `encode_image`/`decode_image` (base64 JPEG), `setup_logging`

## Key Design Patterns

**Pluggable model interfaces** — `BaseDetector` (`services/detection/detector.py`) and `BaseTracker` (`services/tracking/tracker.py`) are ABCs. Swap implementations without touching services or downstream consumers. Current implementations: `RFDETRTensorRTDetector` (`services/detection/trt_detector.py`, requires a `.engine` model path) and `SimpleIoUTracker` (placeholder).

**Immutable messages** — All Kafka message schemas are `@dataclass(frozen=True)`. Never mutate them; construct a new instance instead. Serialize with `dataclasses.asdict()` → JSON.

**Configuration** — All settings come from environment variables via `shared/config/settings.py`. Reference `.env.example` for available variables. Never hardcode broker addresses, topic names, model paths, or thresholds.

**Error resilience** — Services must skip corrupted frames and retry transient Kafka/RTSP failures. A single bad frame must never crash the service loop.

## Constraints

- AI services (`detection`, `tracking`) must never depend on WebRTC.
- `dashboard` must never run inference or decode RTSP.
- Services must never share Kafka producers or communicate outside Kafka.
- Kafka message schemas in `shared/schemas/messages.py` are a contract — breaking changes require updating all producers and consumers together.
- `media_gateway` uses MediaMTX (pre-built binary in Docker), not custom Python code.
