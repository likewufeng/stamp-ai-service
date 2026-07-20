# Stamp AI Service - production image
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PIP_NO_CACHE_DIR=1 \
  PIP_DISABLE_PIP_VERSION_CHECK=1 \
  U2NET_HOME=/app/models/u2net \
  APP_PORT=8000 \
  APP_RELOAD=false \
  DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Build args (compose defaults to China mirrors)
#   APT_MIRROR=mirrors.aliyun.com
#   PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG APT_MIRROR=mirrors.aliyun.com
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# Force rewrite Debian apt sources to mirror (avoids deb.debian.org 502)
RUN set -eux; \
  MIRROR="${APT_MIRROR:-mirrors.aliyun.com}"; \
  rm -f /etc/apt/sources.list.d/debian.sources; \
  printf '%s\n' \
  "deb http://${MIRROR}/debian bookworm main contrib non-free non-free-firmware" \
  "deb http://${MIRROR}/debian bookworm-updates main contrib non-free non-free-firmware" \
  "deb http://${MIRROR}/debian-security bookworm-security main contrib non-free non-free-firmware" \
  > /etc/apt/sources.list; \
  for i in 1 2 3 4 5; do \
  if apt-get update; then break; fi; \
  echo "apt-get update failed (try $i), retry..."; \
  sleep 2; \
  if [ "$i" -eq 3 ]; then \
  echo "drop bookworm-updates and retry"; \
  printf '%s\n' \
  "deb http://${MIRROR}/debian bookworm main contrib non-free non-free-firmware" \
  "deb http://${MIRROR}/debian-security bookworm-security main contrib non-free non-free-firmware" \
  > /etc/apt/sources.list; \
  fi; \
  if [ "$i" -eq 5 ]; then exit 1; fi; \
  done; \
  apt-get install -y --no-install-recommends \
  libgl1 \
  libglib2.0-0 \
  libgomp1 \
  curl \
  ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN set -eux; \
  pip install --upgrade pip -i "${PIP_INDEX_URL}" --trusted-host mirrors.aliyun.com --trusted-host pypi.tuna.tsinghua.edu.cn; \
  pip install -r requirements.txt -i "${PIP_INDEX_URL}" --trusted-host mirrors.aliyun.com --trusted-host pypi.tuna.tsinghua.edu.cn; \
  pip uninstall -y opencv-python || true; \
  pip install "opencv-python-headless==4.10.0.84" -i "${PIP_INDEX_URL}" --trusted-host mirrors.aliyun.com --trusted-host pypi.tuna.tsinghua.edu.cn

COPY . .

RUN mkdir -p /app/uploads /app/outputs /app/logs /app/temp /app/models/u2net \
  && useradd --create-home --shell /bin/bash appuser \
  && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${APP_PORT}/api/health" || exit 1

CMD ["sh", "-c", "python -m uvicorn app:app --host 0.0.0.0 --port ${APP_PORT} --workers ${UVICORN_WORKERS:-2} --proxy-headers --forwarded-allow-ips='*'"]
