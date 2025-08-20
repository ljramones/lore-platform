# src/lore_scheduler/Dockerfile
FROM python:3.11-slim

# Fast, clean Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Project metadata + sources (src/ layout)
COPY pyproject.toml /app/
COPY src/ /app/src/

# Install the package + runtime deps
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install -e . \
 && pip install --no-cache-dir -r /app/src/requirements.txt

# Runtime defaults (override in compose)
ENV TEMPORAL_ADDRESS=temporal:7233 \
    TASK_QUEUE=lore-ingest \
    SCHED_INTERVAL=5

# Run as non-root
RUN adduser --disabled-password --gecos '' appuser \
 && chown -R appuser:appuser /app
USER appuser

# Lightweight healthcheck (no heredoc)
HEALTHCHECK --interval=20s --timeout=5s --retries=5 \
  CMD python -c "import os,socket; a=os.getenv('TEMPORAL_ADDRESS','temporal:7233'); h,p=(a.split(':')+['7233'])[:2]; socket.create_connection((h,int(p)),timeout=3).close()"

CMD ["python","-m","lore_scheduler"]


