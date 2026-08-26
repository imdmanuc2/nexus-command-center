FROM python:3.14-slim

ARG NEXUS_VERSION=development
ARG NEXUS_REVISION=unknown

LABEL org.opencontainers.image.title="Nexus Command Center"
LABEL org.opencontainers.image.description="Seymour Nexus Command Center"
LABEL org.opencontainers.image.source="https://github.com/imdmanuc2/nexus-command-center"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/opt/nexus \
    NEXUS_VERSION=${NEXUS_VERSION} \
    NEXUS_REVISION=${NEXUS_REVISION}

WORKDIR /opt/nexus

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        openssh-client \
        ca-certificates \
        iproute2 \
        procps \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-container.txt /tmp/requirements-container.txt

RUN python -m pip install \
        --no-cache-dir \
        -r /tmp/requirements-container.txt \
    && rm -f /tmp/requirements-container.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY scripts/ ./scripts/

# Private credentials and host-specific runtime state are excluded
# by .dockerignore and must be supplied at runtime.
RUN mkdir -p \
      backend/data/private \
      backend/data/events \
      backend/data/telemetry \
      backend/data/snapshots \
      backend/data/graph \
    && chmod -R a+rX /opt/nexus

EXPOSE 8080

HEALTHCHECK \
    --interval=30s \
    --timeout=10s \
    --start-period=20s \
    --retries=3 \
    CMD curl --fail --silent --show-error \
        http://127.0.0.1:8080/api/health >/dev/null || exit 1

CMD ["python", "-m", "backend.api.server"]
