# Stamp AI Service - production image
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PIP_NO_CACHE_DIR=1 \
  PIP_DISABLE_PIP_VERSION_CHECK=1 \
  # rembg model cache path (persist via volume)
  U2NET_HOME=/app/models/u2net \
  APP_PORT=8000 \
  APP_RELOAD=false

WORKDIR /app

# System deps for opencv / pillow / onnxruntime
RUN apt-get update && apt-get install -y --no-install-recommends \
  libgl1 \
  libglib2.0-0 \
  libgomp1 \
  curl \
  ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Use headless opencv in container (no GUI libs needed beyond runtime)
COPY requirements.txt .
RUN pip install --upgrade pip \
  && pip install -r requirements.txt \
  && pip uninstall -y opencv-python || true \
  && pip install "opencv-python-headless==4.10.0.84"

# App source
COPY . .

# Runtime dirs
RUN mkdir -p /app/uploads /app/outputs /app/logs /app/temp /app/models/u2net \
  && useradd --create-home --shell /bin/bash appuser \
  && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${APP_PORT}/api/health" || exit 1

# Production: multi-worker uvicorn (CPU-bound vision; 2 workers default)
CMD ["sh", "-c", "python -m uvicorn app:app --host 0.0.0.0 --port ${APP_PORT} --workers ${UVICORN_WORKERS:-2} --proxy-headers --forwarded-allow-ips='*'"]
