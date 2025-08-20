FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml /app/
COPY src/ /app/src/

RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install -e . \
 && pip install --no-cache-dir -r /app/src/requirements.txt \
 && pip install --no-cache-dir fastapi uvicorn requests sentence-transformers

ENV CHROMA_HOST=chroma CHROMA_PORT=8000 CHROMA_COLLECTION=lore-sections \
    EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2 \
    PORT=8080
EXPOSE 8080
CMD ["uvicorn","lore_search.__main__:app","--host","0.0.0.0","--port","8080"]
