# lore-search — FastAPI semantic search over Lore sections

A lightweight HTTP service that queries your **Chroma** collection of section embeddings and returns the most relevant lore passages for a given prompt. It pairs with the **lore-indexer** (which writes embeddings) and exposes a simple REST API for your UI, agents, or tools.&#x20;

---

## What it does

* Hosts a **FastAPI** app with:

  * `GET /healthz` – sanity check + current Chroma API base and collection.&#x20;
  * `GET /search?q=...&k=5` – embeds the query, runs a Chroma `query`, and returns `[id, distance, text, metadata]` tuples.&#x20;
* Auto-detects **Chroma REST v2** (falls back to v1) via `/api/v2/healthcheck`.&#x20;
* Lazily loads a **SentenceTransformer** once per process; uses `normalize_embeddings=True` for cosine similarity.&#x20;
* Ensures the configured **collection** exists before querying.&#x20;

---

## Environment variables

| Variable            | Default                                  | Purpose                                          |
| ------------------- | ---------------------------------------- | ------------------------------------------------ |
| `CHROMA_HOST`       | `chroma`                                 | Hostname of the Chroma service.                  |
| `CHROMA_PORT`       | `8000`                                   | Chroma REST port.                                |
| `CHROMA_COLLECTION` | `lore-sections`                          | Name of the collection created by lore-indexer.  |
| `EMBED_MODEL`       | `sentence-transformers/all-MiniLM-L6-v2` | Query embedding model.                           |

> Tip: keep `EMBED_MODEL` consistent with the one used by **lore-indexer** for best retrieval quality.

---

## API

### `GET /healthz`

Returns basic service/Chroma info.

**Response**

```json
{
  "ok": true,
  "chroma": "http://chroma:8000/api/v2",
  "collection": "lore-sections"
}
```



### `GET /search`

Query parameters:

* `q` *(required, string)* – the natural-language search prompt.
* `k` *(optional, int, default 5)* – number of nearest sections to return.

**Example request**

```bash
curl "http://localhost:8001/search?q=Tomoe%20Gozen%20battle&k=5"
```

**Example response (truncated)**

```json
{
  "query": "Tomoe Gozen battle",
  "k": 5,
  "results": [
    {
      "id": "sec:123",
      "distance": 0.08,
      "text": "Tomoe lowered her spear as thunder split the sky...",
      "metadata": {
        "document_id": 42,
        "document_title": "Chronicles of the Parallel Court",
        "section_id": 123,
        "section_idx": 7
      }
    }
  ]
}
```

Results are unwrapped from Chroma’s single-query response and include the stored `documents` (your section text) and `metadatas`.&#x20;

**Error cases**

* `500 Collection '...' not found in Chroma` – the named collection doesn’t exist. Ensure **lore-indexer** has created it (or create manually).&#x20;
* `500 Chroma query failed: ...` – upstream REST call failed. Check network/host/port and Chroma logs.&#x20;

---

## Run locally

```bash
# Inside the lore-search module
pip install -r requirements.txt
uvicorn __main__:app --host 0.0.0.0 --port 8001 --reload
```

> You can also run `python -m uvicorn __main__:app --host 0.0.0.0 --port 8001` depending on your layout.

Ensure your **Chroma** instance is reachable at `CHROMA_HOST:CHROMA_PORT`, and that the `CHROMA_COLLECTION` already exists (usually created by **lore-indexer**).&#x20;

---

## Docker

A `Dockerfile` is included. Typical usage:

```bash
docker build -t lore-search .
docker run --rm -p 8001:8001 \
  -e CHROMA_HOST=host.docker.internal \
  -e CHROMA_PORT=8000 \
  -e CHROMA_COLLECTION=lore-sections \
  -e EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2 \
  lore-search uvicorn __main__:app --host 0.0.0.0 --port 8001
```

---

## How it fits in

```
[lore_watcher] --> (DB: Document/Section)
         \
          -> [lore_indexer] -> (Chroma: lore-sections)
                                 ^
                                 |
                          [lore-search API]  <--- UI / agents / tools
```

* **lore\_watcher**: ingest & split into sections
* **lore\_indexer**: embed & upsert to Chroma
* **lore-search**: query-time retrieval API for your applications

---

## Implementation notes

* **Chroma v1/v2 auto-detect** – prefers `/api/v2` if `healthcheck` passes, else uses `/api/v1`.&#x20;
* **Collection guard** – verifies collection by name via `GET /collections?name=...` before querying.&#x20;
* **Embedding cache** – the `SentenceTransformer` model is constructed once (module-level singleton).&#x20;
* **Includes** – requests `documents`, `metadatas`, `distances`, and `ids` from Chroma so clients don’t need a second fetch.&#x20;

---

## Next steps

* Add **hybrid search** (BM25 + dense) by augmenting with a keyword index.
* Add **filters** (e.g., by document, era, locale) using Chroma metadata conditions.
* Stream results or support **MMR**/**diversity** re-ranking for less redundancy.

---
