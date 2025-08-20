#!/usr/bin/env bash
set -euo pipefail

echo "Stopping and removing containers..."
docker compose down --volumes --remove-orphans

echo "Deleting bind-mounted data..."
rm -rf ./data/chroma \
       ./data/temporal/postgres \
       ./data/minio \
       ./data/db \
       ./inbox/*

echo "Pruning docker volumes and networks..."
docker volume prune -f || true
docker network prune -f || true

echo "Recreating fresh DBs & inbox..."
mkdir -p data/db inbox
touch data/db/{canon.sqlite,research.sqlite,idea.sqlite}

echo "Bringing stack back up..."
docker compose up -d
docker compose up -d --build lore-worker lore-watcher lore-ner lore-scheduler

echo "Done. Temporal UI: http://localhost:8088  |  Chroma: http://localhost:8000/docs"
