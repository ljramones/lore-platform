FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# project sources
COPY pyproject.toml /app/
COPY src/ /app/src/

# install your project (src layout) + minimal deps only for this service
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install -e . \
 && pip install --no-cache-dir -r /app/src/requirements.txt \
 && pip install --no-cache-dir sentence-transformers requests

ENV CHROMA_HOST=chroma CHROMA_PORT=8000 CHROMA_COLLECTION=lore-sections \
    EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2 \
    INDEX_INTERVAL=30 BATCH_SIZE=64
CMD ["python","-m","lore_indexer"]
