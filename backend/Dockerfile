# Retail Intelligence backend: Python 3.12 + Java 17 + PySpark 3.5.4.
# Deterministic production image for Render / Cloud Run (any container host).
#
# Build:  docker build -t retail-intel-backend ./backend
# Run:    docker run -p 8000:8000 --env-file .env.prod retail-intel-backend
# Health: GET /api/v1/health
FROM python:3.12-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# --- Java 17 (Temurin, pinned) + runtime deps -----------------------------
# gcc/make are needed to build Prophet's Stan backend on install.
ARG TEMURIN_URL=https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.11%2B9/OpenJDK17U-jdk_x64_linux_hotspot_17.0.11_9.tar.gz
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates gcc g++ make \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/java /opt/jdbc \
    && curl -fsSL "$TEMURIN_URL" -o /tmp/jdk.tar.gz \
    && tar -xzf /tmp/jdk.tar.gz -C /opt/java --strip-components=1 \
    && rm /tmp/jdk.tar.gz \
    && curl -fsSL https://jdbc.postgresql.org/download/postgresql-42.7.4.jar \
        -o /opt/jdbc/postgresql.jar \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/opt/java \
    PATH=/opt/java/bin:$PATH \
    POSTGRES_JDBC_JAR=/opt/jdbc/postgresql.jar

RUN java -version 2>&1 | grep -q "17\." && echo "java 17 ok"

# --- Python deps (pinned PySpark) ------------------------------------------
WORKDIR /srv/app
COPY pyproject.toml ./
RUN pip install --upgrade pip \
    && pip install . \
    && python -c "import pyspark; assert pyspark.__version__ == '3.5.4', pyspark.__version__"

# --- Application ------------------------------------------------------------
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts

# Ephemeral processing workspace (PostgreSQL is the source of truth).
ENV DATA_DIR=/tmp/retail-intel/data \
    UPLOAD_DIR=/tmp/retail-intel/uploads
RUN mkdir -p /tmp/retail-intel/data /tmp/retail-intel/uploads

# Non-root execution.
RUN useradd -m -u 10001 appuser && chown -R appuser /srv/app /tmp/retail-intel
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT','8000')}/api/v1/health\", timeout=8)"

# PORT is injected by the host; default 8000 for local `docker run`.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
