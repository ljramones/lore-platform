FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy project metadata and sources
COPY pyproject.toml /app/
COPY src/ /app/src/

# Install the project (src/ layout)
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install -e .

# Shared/runtime deps (if you keep them here)
COPY src/requirements.txt /app/src/requirements.txt
RUN pip install --no-cache-dir -r /app/src/requirements.txt

# Runtime env (adjust if you read these)
ENV TEMPORAL_ADDRESS=host.docker.internal:7233
ENV TASK_QUEUE=lore-ingest

# Start worker; __main__.py must import/register workflows
CMD ["python", "-m", "lore_worker"]
