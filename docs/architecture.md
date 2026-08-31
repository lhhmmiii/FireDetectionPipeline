# Architecture

## Overview

The Fire Detection Pipeline is a microservice-based system that processes live video streams to detect and track fires in real-time.

## System Architecture

```
              Live Video Source
                      │
                  RTSP Stream
                      │
                 Media Gateway
                  (MediaMTX)
          ┌───────────┴────────────┐
          │                        │
          ▼                        ▼
 Frame Extractor              WebRTC Viewer
          │                   (Dashboard UI)
          ▼
 Kafka (frames topic)
          │
          ▼
 Detection Service
 (RFDETRTensorRTDetector)
          │
          ▼
 Kafka (detections topic)
          │
          ▼
 Tracking Service
 (SimpleIoUTracker / Custom)
          │
          ▼
 Kafka (tracks topic)
          │
          ▼
 Dashboard Backend (FastAPI)
          │
          ▼
 Dashboard UI (WebSocket)
```

## Service Responsibilities

| Service | Input | Output | Description |
|---------|-------|--------|-------------|
| **Media Gateway** | RTSP from Video Source | RTSP + WebRTC | Relays video, converts to WebRTC |
| **Frame Extractor** | RTSP from Gateway | Kafka `frames` | Decodes video, publishes frames |
| **Detection Service** | Kafka `frames` | Kafka `detections` | Runs fire detection model |
| **Tracking Service** | Kafka `detections` | Kafka `tracks` | Associates objects across frames |
| **Dashboard** | Kafka `tracks` + WebRTC | Browser UI | Visualization layer |

## Communication

All inter-service communication goes through **Apache Kafka**. Services never communicate directly.

### Kafka Topics

| Topic | Message Schema | Producer | Consumer |
|-------|---------------|----------|----------|
| `frames` | `FrameMessage` | Frame Extractor | Detection |
| `detections` | `DetectionMessage` | Detection | Tracking |
| `tracks` | `TrackMessage` | Tracking | Dashboard |

## Key Design Principles

1. **Media transport is decoupled from AI processing** — RTSP for inference, WebRTC for visualization
2. **Services communicate only through Kafka** — No direct coupling
3. **Pluggable AI models** — Swap detection/tracking algorithms without code changes
4. **Messages are immutable** — All schemas use frozen dataclasses
5. **Graceful degradation** — Corrupted frames are skipped, services auto-reconnect
