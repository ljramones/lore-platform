# Lore Indexer (Temporal Workflow Module)

This module is part of the **Lore-a-pedia** platform, a Temporal-based workflow system for processing incoming fictional documents. Its primary role is to **index document sections into a Chroma vector store** for semantic search and retrieval.

---

## 📖 Overview

The **Lore Indexer** runs as a Temporal activity/worker that:

1. Reads sections of ingested documents from the **SQLite/Postgres DB** (via `sqlmodel` and `lore_common.db`).
2. Encodes each section into embeddings using a configurable **SentenceTransformer model**.
3. Pushes new embeddings into a **Chroma collection** for semantic retrieval.
4. Runs continuously, polling for new content at configurable intervals.

This allows **cross-document exploration of characters, events, legends, and histories** across fictional works, enabling narrative research and AI-assisted analysis.

---

## ⚙️ Architecture

**Key Components:**

* **Temporal Workflow** – Orchestrates ingestion, processing, and indexing steps.
* **Lore Indexer (`__main__.py`)** – This module; handles embeddings + Chroma sync.
* **Database Layer (`lore_common.db`)** – Provides access to `Document` and `Section` entities.
* **Chroma Vector Store** – Stores embeddings with metadata for fast semantic queries.

**Processing Loop:**

1. Fetch document sections + metadata from DB.
2. Skip sections already indexed in Chroma.
3. Embed missing sections in batches.
4. Add or update Chroma collection with embeddings.
5. Repeat at configured intervals.

---

## 🚀 Running the Service

### Prerequisites

* **Python 3.9+**
* **Temporal Server** (local or remote)
* **Chroma** (running with REST API enabled)
* **Database** (default: SQLite at `/app/data/lore.db`)

### Environment Variables

| Variable            | Default Value                            | Description                            |
| ------------------- | ---------------------------------------- | -------------------------------------- |
| `DATABASE_URL`      | sqlite:///app/data/lore.db               | SQLModel DB connection                 |
| `CHROMA_HOST`       | `chroma`                                 | Chroma service host                    |
| `CHROMA_PORT`       | `8000`                                   | Chroma service port                    |
| `CHROMA_COLLECTION` | `lore-sections`                          | Collection name for section embeddings |
| `EMBED_MODEL`       | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model                        |
| `BATCH_SIZE`        | `64`                                     | Sections per embedding batch           |
| `INDEX_INTERVAL`    | `30`                                     | Seconds between indexing runs          |

### Running Locally

```bash
pip install -r requirements.txt
python -m lore_indexer
```

### Running with Docker

A `Dockerfile` is included for containerized deployment:

```bash
docker build -t lore-indexer .
docker run --rm \
  -e DATABASE_URL="sqlite:///app/data/lore.db" \
  -e CHROMA_HOST="localhost" \
  -e CHROMA_PORT="8000" \
  lore-indexer
```

---

## 🔄 Integration with Temporal

This service is designed to run alongside **Temporal workflows**. Typical flow:

1. **Watcher Service** ingests documents (PDFs, text, etc.) → stores sections in DB.
2. **Temporal Workflow** triggers downstream activities.
3. **Lore Indexer** picks up new sections, embeds them, and pushes into Chroma.
4. **Lore Search Service** uses Chroma to power retrieval and exploration.

---

## 📊 Example Metadata Stored

Each indexed section is stored with metadata:

```json
{
  "document_id": 42,
  "document_title": "Epic of the Twin Moons",
  "section_id": 17,
  "section_idx": 3
}
```

---

## 🛠 Development Notes

* Logging is configured via `LOG_LEVEL` (default: INFO).
* Embeddings are normalized for cosine similarity.
* Indexer retries failed batches with fallback to `update` if IDs already exist.
* Can be extended with other vector DBs or embedding models.

---

## 📚 Related Components

* `lore_watcher`: Ingests manuscripts & splits into sections.
* `lore_common`: Shared DB models and helpers.
* `lore_search`: Query layer for semantic retrieval.
* `lore_scheduler`: Orchestrates Temporal workflows.

