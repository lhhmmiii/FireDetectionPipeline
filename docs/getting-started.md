# Getting Started

## Prerequisites

- **Docker** & **Docker Compose** (v2+)
- **Python 3.11+** (for local development)
- A UAV or any RTSP video source (or use a test video)

## Quick Start

### 1. Clone and Setup

```bash
cd d:\Projects\FireDetectionPipeline

# Copy environment template
cp .env.example .env
```

### 2. Start the Pipeline

```bash
# Start all services
docker compose up -d

# Watch logs
docker compose logs -f
```

### 3. Provide a Video Source

Push an RTSP stream to the Media Gateway:

```bash
# Using FFmpeg with a test video
ffmpeg -re -i test_video.mp4 -c copy -f rtsp rtsp://localhost:8554/uav1

ffmpeg -re -i test_video.mp4 -c copy -f rtsp rtsp://localhost:8554/uav2

# Using FFmpeg with a webcam (Linux)
ffmpeg -f v4l2 -i /dev/video0 -c:v libx264 -f rtsp rtsp://localhost:8554/stream
```

### 4. Access the Dashboard

Open [http://localhost:8080](http://localhost:8080) in your browser.

## Service URLs

| Service | URL | Protocol |
|---------|-----|----------|
| Dashboard | http://localhost:8080 | HTTP |
| MediaMTX RTSP | rtsp://localhost:8554/uav1 | RTSP |
| MediaMTX RTSP | rtsp://localhost:8554/uav2 | RTSP |
| MediaMTX WebRTC | http://localhost:8889 | HTTP/WebRTC |
| MediaMTX API | http://localhost:9997 | HTTP |
| Kafka (internal) | kafka:9092 | TCP |
| Kafka (host) | localhost:29092 | TCP |

## Development

### Run Tests

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_schemas.py -v
```

### Run Services Locally (without Docker)

```bash
# Start Kafka first
docker compose up -d kafka mediamtx

# Then run services individually
PYTHONPATH=. python services/frame_extractor/main.py
PYTHONPATH=. python services/detection/main.py
PYTHONPATH=. python services/tracking/main.py
PYTHONPATH=. python services/dashboard/main.py
```

## Stopping

```bash
# Stop all services
docker compose down

# Stop and remove volumes (reset data)
docker compose down -v
```
