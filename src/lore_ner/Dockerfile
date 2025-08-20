# src/lore_ner/Dockerfile
FROM python:3.11-slim

# Fast, clean Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install project (src/ layout) + runtime deps
COPY pyproject.toml /app/
COPY src/ /app/src/
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install -e . \
 && pip install --no-cache-dir -r /app/src/requirements.txt

# Download spaCy model at build time (no heredoc)
ENV SPACY_MODEL=en_core_web_sm
RUN python -c "import os; import spacy.cli as c; c.download(os.environ.get('SPACY_MODEL','en_core_web_sm'))"

# Run as non-root
RUN adduser --disabled-password --gecos '' appuser \
 && chown -R appuser:appuser /app
USER appuser

# Healthcheck without heredoc
HEALTHCHECK --interval=30s --timeout=5s --retries=5 \
  CMD ["python","-c","import os,spacy,sys; spacy.load(os.getenv('SPACY_MODEL','en_core_web_sm')); sys.exit(0)"]

CMD ["python","-m","lore_ner"]
