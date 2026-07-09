FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY services/tracking/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared libraries
COPY shared/ /app/shared/

# Copy service code
COPY services/tracking/main.py services/tracking/tracker.py ./

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["python", "main.py"]
