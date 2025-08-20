FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml /app/
COPY src/ /app/src/

RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install -e .

COPY src/requirements.txt /app/src/requirements.txt
RUN pip install --no-cache-dir -r /app/src/requirements.txt

ENV INBOX_DIR=/app/inbox
RUN mkdir -p "$INBOX_DIR"

CMD ["python", "-m", "lore_watcher"]
