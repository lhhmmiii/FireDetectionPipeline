# Stage 1: Build the React frontend
FROM node:22-alpine AS frontend-builder

WORKDIR /frontend

COPY services/monitoring/frontend/package.json ./
RUN npm install

COPY services/monitoring/frontend/ .
RUN npm run build
# Built assets land at /static (vite outDir: '../static' relative to /frontend)

# Stage 2: Python monitoring service
FROM python:3.11-slim

WORKDIR /app

COPY services/monitoring/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ /app/shared/
COPY services/monitoring/main.py services/monitoring/aggregator.py ./
COPY --from=frontend-builder /static/ /app/static/

RUN mkdir -p /app/data/baselines

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8090

CMD ["python", "main.py"]
