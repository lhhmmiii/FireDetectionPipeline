# Stage 1: Build the React frontend
FROM node:22-alpine AS frontend-builder

WORKDIR /frontend

COPY services/dashboard/frontend/package.json ./
RUN npm install

COPY services/dashboard/frontend/ .
RUN npm run build
# Built assets land at /static (vite outDir: '../static' relative to /frontend)

# Stage 2: Python dashboard service
FROM python:3.11-slim

WORKDIR /app

COPY services/dashboard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ /app/shared/
COPY services/dashboard/main.py .
COPY --from=frontend-builder /static/ /app/static/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8080

CMD ["python", "main.py"]
