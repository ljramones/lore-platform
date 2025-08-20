# src/lore_watcher/Dockerfile
FROM python:3.11-slim

# Fast, clean Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Copy metadata + sources (src/ layout)
COPY pyproject.toml /app/
COPY src/ /app/src/

# Install project + runtime deps
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install -e . \
 && pip install --no-cache-dir -r /app/src/requirements.txt

# Runtime defaults
ENV INBOX_DIR=/app/inbox \
    TEMPORAL_ADDRESS=temporal:7233 \
    TASK_QUEUE=lore-ingest

# Prepare inbox and run as non-root
RUN adduser --disabled-password --gecos '' appuser \
 && mkdir -p "$INBOX_DIR" \
 && chown -R appuser:appuser /app
USER appuser

# Simple healthcheck (no heredoc)
HEALTHCHECK --interval=20s --timeout=5s --retries=5 \
  CMD ["python","-c","import os,socket,sys,os.path; addr=os.getenv('TEMPORAL_ADDRESS','temporal:7233'); h,p=(addr.split(':')+['7233'])[:2]; socket.create_connection((h,int(p)),timeout=3).close(); d=os.getenv('INBOX_DIR','/app/inbox'); sys.exit(0 if os.path.isdir(d) and os.access(d, os.W_OK) else 1)"]

CMD ["python","-m","lore_watcher"]

