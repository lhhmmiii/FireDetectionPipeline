# 🚁 UAV Real-Time Fire & Smoke Detection Pipeline

[![Python](https://img.shields.io/badge/Python-3.13%2B-blue.svg)](https://www.python.org/)
[![Kafka](https://img.shields.io/badge/Apache%20Kafka-KRaft%20mode-black.svg)](https://kafka.apache.org/)
[![TensorRT](https://img.shields.io/badge/NVIDIA-TensorRT%2010-76B900.svg)](https://developer.nvidia.com/tensorrt)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18%20%2B%20Vite-61DAFB.svg)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Docker-Compose%20v2-2496ED.svg)](https://www.docker.com/)

A high-performance, distributed, real-time fire and smoke detection and tracking pipeline designed for multi-UAV (drone) video streams. Built on an event-driven microservices architecture using **Apache Kafka**, **NVIDIA TensorRT** hardware acceleration, **MediaMTX** for low-latency WebRTC video streaming, and modern **FastAPI + React** interactive dashboards with end-to-end latency telemetry monitoring.

---

## 📑 Table of Contents

- [System Architecture](#-system-architecture)
- [Key Features](#-key-features)
- [Microservices Overview](#-microservices-overview)
- [Kafka Topics & Message Contracts](#-kafka-topics--message-contracts)
- [Port & Service Mapping](#-port--service-mapping)
- [Quick Start Guide](#-quick-start-guide)
  - [Prerequisites](#prerequisites)
  - [1. Clone & Configuration](#1-clone--configuration)
  - [2. Launch with Docker Compose](#2-launch-with-docker-compose)
  - [3. Ingest Video Streams (FFmpeg Simulation)](#3-ingest-video-streams-ffmpeg-simulation)
  - [4. Access Dashboards](#4-access-dashboards)
- [Configuration Reference](#-configuration-reference)
- [Local Development & Testing](#-local-development--testing)
- [Design Principles](#-design-principles)
- [License](#-license)

---

## 🏗 System Architecture

The pipeline decouples media streaming from AI processing using an event-driven architecture where microservices communicate strictly via Apache Kafka.

```
                              ┌───────────────┐
                              │   UAV Fleet   │
                              │ (RTSP Streams)│
                              └───────┬───────┘
                                      │ RTSP
                                      ▼
                        ┌───────────────────────────┐
                        │   Media Gateway (MediaMTX)│
                        │    RTSP & WebRTC Relay    │
                        └─────┬───────────────┬─────┘
                 RTSP Streams │               │ WebRTC (WHEP)
                              ▼               │
                    ┌───────────────────┐     │
                    │  Frame Extractor  │     │
                    │  (Multi-instance) │     │
                    └─────────┬─────────┘     │
                              │ Kafka [frames]│
                              ▼               │
                    ┌───────────────────┐     │
                    │ Detection Service │     │
                    │(TensorRT RF-DETR) │     │
                    └─────────┬─────────┘     │
                              │ Kafka [detections]
                              ▼               │
                    ┌───────────────────┐     │
                    │ Tracking Service  │     │
                    │ (Multi-Object MOT)│     │
                    └─────────┬─────────┘     │
                              │ Kafka [tracks]│
                              ▼               ▼
                    ┌───────────────────────────────┐
                    │      Dashboard Service        │
                    │   (FastAPI + React WebRTC UI) │
                    └───────────────────────────────┘

═════════════════════════════════════════════════════════════════════════════
  All Services ──► Kafka [metrics] ──► Monitoring Dashboard (Port 8090)
  (Frame Extractor, Detection, Tracking, Dashboard)
```

---

## ✨ Key Features

- **Decoupled Media & AI Pipelines**: RTSP streams are ingested into MediaMTX and forwarded to frame extractors for decoding, while simultaneously transcoded into ultra-low-latency WebRTC streams for browser rendering.
- **NVIDIA TensorRT Acceleration**: Sub-millisecond fire and smoke inference powered by an INT8/FP16 optimized RF-DETR architecture.
- **Multi-Object Tracking (MOT)**: Temporal consistency across frames with per-UAV tracking state, assigning persistent IDs to localized fire and smoke regions.
- **Multi-UAV / Multi-Stream Support**: Independent frame ingestion and tracking partitioned across multiple UAV sources (`uav-1`, `uav-2`, etc.).
- **Live Interactive Dashboard**: Real-time video canvas with synchronized bounding box overlays, confidence indicators, active tracks inventory, and alert logs.
- **End-to-End Distributed Tracing & Telemetry**: Every frame is tagged with a trace ID that tracks processing times across all pipeline stages, Kafka transit delays, dropped frames, and system throughput in a dedicated monitoring UI.
- **Baseline Performance Comparison**: Capture and compare runtime latency/throughput snapshots before and after code or model changes.
- **Pluggable & Extensible Interfaces**: Abstract base classes (`BaseDetector` and `BaseTracker`) allow effortless swapping of detection models (e.g. YOLO, GroundingDINO) and tracking algorithms (e.g. ByteTrack, DeepSORT).

---

## 🧩 Microservices Overview

| Microservice | Path | Description |
| :--- | :--- | :--- |
| **Media Gateway** | `services/media_gateway/` | Pre-configured [MediaMTX](https://github.com/bluenviron/mediamtx) server. Relays incoming RTSP feeds from UAVs and provides WebRTC (WHEP) endpoints. |
| **Frame Extractor** | `services/frame_extractor/` | Pulls RTSP video feeds, samples frames at a configurable FPS/resolution, encodes them to base64 JPEG, and publishes `FrameMessage` records to Kafka. |
| **Detection Service** | `services/detection/` | Consumes raw frames, performs TensorRT-accelerated RF-DETR object detection (`fire` / `smoke`), and publishes `DetectionMessage` records. |
| **Tracking Service** | `services/tracking/` | Consumes detection boxes, performs IoU-based multi-object association per UAV source, filters false positives, and publishes `TrackMessage` records. |
| **Dashboard Service** | `services/dashboard/` | FastAPI backend + React frontend. Consumes `tracks` from Kafka and broadcasts them via WebSocket to render real-time bounding boxes over WebRTC video feeds. |
| **Monitoring Service** | `services/monitoring/` | Consumes `SpanMessage` telemetry from the `metrics` topic, aggregates stage latencies, Kafka transit times, and FPS, and serves an observability dashboard. |
| **Shared Library** | `shared/` | Common Python package containing immutable schemas, Kafka producers/consumers, configuration loaders, logging helpers, and the `Tracer` SDK. |

---

## 📬 Kafka Topics & Message Contracts

All Kafka messages use immutable, frozen dataclasses serialized to JSON.

```
[frames] ──► [detections] ──► [tracks]
    │              │              │
    └──────────────┼──────────────┘
                   ▼
               [metrics]
```

### Topic Specifications

| Topic | Producer | Consumer | Schema | Key Payload Fields |
| :--- | :--- | :--- | :--- | :--- |
| `frames` | Frame Extractor | Detection | `FrameMessage` | `frame_id`, `source_id`, `timestamp`, `width`, `height`, `image_data` (Base64 JPEG) |
| `detections` | Detection Service | Tracking | `DetectionMessage` | `frame_id`, `source_id`, `timestamp`, `boxes` (`[[x1,y1,x2,y2]]`), `scores`, `classes` |
| `tracks` | Tracking Service | Dashboard | `TrackMessage` | `track_id`, `frame_id`, `source_id`, `timestamp`, `bbox`, `confidence`, `class_name` |
| `metrics` | All Services | Monitoring | `SpanMessage` | `trace_id` (= `frame_id`), `span_id`, `stage`, `operation`, `duration_ms`, `status` |

---

## 🌐 Port & Service Mapping

| Service | Port | Protocol | Purpose |
| :--- | :--- | :--- | :--- |
| **Dashboard UI** | `8080` | HTTP / WebSocket | Live UAV video stream + detection overlay (`/ws/tracks`) |
| **Monitoring Dashboard** | `8090` | HTTP / WebSocket | Pipeline telemetry, stage latencies, and baseline benchmarking |
| **Kafka UI** | `8081` | HTTP | Kafka cluster, topic, and consumer group inspector |
| **MediaMTX RTSP** | `8554` | RTSP (TCP/UDP) | RTSP video stream ingest & relay (`rtsp://localhost:8554/<stream>`) |
| **MediaMTX WebRTC** | `8889` | HTTP / UDP | WebRTC WHEP signalling & ICE media transmission |
| **MediaMTX API** | `9997` | HTTP | MediaMTX management API |
| **Kafka Broker** | `9092` / `29092` | TCP | Kafka broker (internal container / host listener) |

---

## 🚀 Quick Start Guide

### Prerequisites

- **Docker** & **Docker Compose** (v2+)
- **NVIDIA GPU** + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) (for TensorRT detection)
- **Python 3.13+** and [`uv`](https://docs.astral.sh/uv/) (optional, for local development)
- **FFmpeg** (for streaming test video files)

### 1. Clone & Configuration

```bash
git clone https://github.com/your-username/FireDetectionPipeline.git
cd FireDetectionPipeline

# Copy environment template
cp .env.example .env
```

### 2. Launch with Docker Compose

Start the complete pipeline with a single command:

```bash
# Start all infrastructure and pipeline services
docker compose up -d

# Verify running containers
docker compose ps

# Follow logs from all services or a specific service
docker compose logs -f
# docker compose logs -f detection
```

> [!NOTE]
> If running in an environment without an NVIDIA GPU, you can customize the detection service to use a CPU-compatible detector implementation.

### 3. Ingest Video Streams (FFmpeg Simulation)

Stream local video files or a webcam to the Media Gateway using FFmpeg:

```bash
# Stream UAV-1 video feed
ffmpeg -re -stream_loop -1 -i path/to/fire_video_1.mp4 -c copy -f rtsp rtsp://localhost:8554/uav1

# Stream UAV-2 video feed (in a separate terminal)
ffmpeg -re -stream_loop -1 -i path/to/fire_video_2.mp4 -c copy -f rtsp rtsp://localhost:8554/uav2

# Stream from local webcam (Linux)
ffmpeg -f v4l2 -i /dev/video0 -c:v libx264 -preset ultrafast -f rtsp rtsp://localhost:8554/uav1

# Stream from local webcam (macOS)
ffmpeg -f avfoundation -framerate 30 -i "0" -c:v libx264 -preset ultrafast -f rtsp rtsp://localhost:8554/uav1
```

### 4. Access Dashboards

- **Live Fire Detection Dashboard**: Open [http://localhost:8080](http://localhost:8080)
- **Latency & Telemetry Monitoring**: Open [http://localhost:8090](http://localhost:8090)
- **Kafka Cluster Explorer**: Open [http://localhost:8081](http://localhost:8081)

---

## ⚙️ Configuration Reference

All pipeline settings are loaded dynamically via environment variables configured in `.env` or `docker-compose.yml`:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Kafka broker connection string |
| `KAFKA_TOPIC_FRAMES` | `frames` | Topic name for extracted video frames |
| `KAFKA_TOPIC_DETECTIONS` | `detections` | Topic name for raw detection bounding boxes |
| `KAFKA_TOPIC_TRACKS` | `tracks` | Topic name for multi-object tracking results |
| `KAFKA_TOPIC_METRICS` | `metrics` | Topic name for span telemetry metrics |
| `FRAME_EXTRACT_FPS` | `10` | Rate at which frames are decoded and sent to Kafka |
| `FRAME_RESIZE_WIDTH` | `640` | Extracted frame width in pixels |
| `FRAME_RESIZE_HEIGHT` | `480` | Extracted frame height in pixels |
| `DETECTION_MODEL_PATH` | `models/rfdetr-nano-int8.engine` | Filepath to TensorRT compiled engine |
| `DETECTION_CONFIDENCE_THRESHOLD` | `0.5` | Minimum confidence score for valid detection |
| `TRACKING_MAX_AGE` | `30` | Number of missed frames before deleting a track |
| `TRACKING_MIN_HITS` | `3` | Minimum consecutive detections before activating track |
| `TRACKING_IOU_THRESHOLD` | `0.3` | IoU threshold for matching detections to existing tracks |
| `DASHBOARD_STREAMS` | `uav-1:uav1,uav-2:uav2` | UAV ID to MediaMTX stream path mapping |
| `METRICS_WINDOW_SECONDS` | `60` | Rolling window size for monitoring aggregation |

---

## 🛠 Local Development & Testing

### Installing Dependencies

We recommend using [`uv`](https://docs.astral.sh/uv/) for fast, deterministic Python environment management:

```bash
# Install project dependencies
uv sync

# Or using standard pip
pip install -r requirements.txt
```

### Running Test Suite

```bash
# Run all unit tests
uv run pytest

# Run with verbose output and coverage
uv run pytest -v tests/

# Run individual test files
uv run pytest tests/test_schemas.py
uv run pytest tests/test_detector.py
uv run pytest tests/test_tracker.py
uv run pytest tests/test_tracing.py
uv run pytest tests/test_monitoring_aggregator.py
```

### Running Services Locally

You can run individual services on your host machine while keeping Kafka and MediaMTX running in Docker:

```bash
# 1. Start core infrastructure
docker compose up -d kafka mediamtx

# 2. Run target service locally with PYTHONPATH set to workspace root
PYTHONPATH=. python services/frame_extractor/main.py
PYTHONPATH=. python services/detection/main.py
PYTHONPATH=. python services/tracking/main.py
PYTHONPATH=. python services/dashboard/main.py
PYTHONPATH=. python services/monitoring/main.py
```

---

## 📐 Design Principles

1. **Strict Kafka Boundary**: Services never invoke each other directly via HTTP/gRPC. All data flows exclusively through Kafka topics, eliminating tight coupling and cascading service failures.
2. **Pluggable AI & Tracking**: Interfaces (`BaseDetector`, `BaseTracker`) define contracts so deep learning models and tracking algorithms can be upgraded or replaced with zero upstream/downstream changes.
3. **Immutable Schema Contract**: All inter-service messages are `@dataclass(frozen=True)`. Mutations are forbidden, ensuring predictable distributed state.
4. **Resilient Failure Handling**: A corrupted frame or network drop skips cleanly without crashing the stream loop. Tracing failures log warnings and never interrupt inference pipelines.
5. **Built-in Observability**: Every frame threads an unchanged `trace_id` through the pipeline, enabling microsecond-precision latency auditing across processing stages and network transit.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
