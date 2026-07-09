FROM nvcr.io/nvidia/tensorrt:25.05-py3

WORKDIR /app

# Install Python dependencies not already in the base image
# numpy is pinned to the 1.x line: this base image ships pycuda compiled
# against numpy 1.23.5's C API, and numpy 2.x breaks that ABI.
RUN pip install --no-cache-dir \
    confluent-kafka>=2.3.0 \
    opencv-python-headless>=4.8.0 \
    "numpy>=1.24.0,<2"

# Copy shared libraries
COPY shared/ /app/shared/

# Copy service code
COPY services/detection/main.py \
     services/detection/detector.py \
     services/detection/trt_detector.py \
     ./

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["python", "main.py"]
