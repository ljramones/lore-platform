FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml /app/
COPY src/ /app/src/

RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install -e . \
 && pip install --no-cache-dir -r /app/src/requirements.txt fastapi uvicorn

ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "lore_api.__main__:app", "--host", "0.0.0.0", "--port", "8080"]
