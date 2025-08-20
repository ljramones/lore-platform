# lore\_api — REST API for Lore-a-pedia

`lore_api` is a **FastAPI service** that exposes documents, sections, and named entity mentions stored in the shared Lore DB. It provides a lightweight HTTP interface for UIs, agents, or other services to browse and filter the evolving lore graph.

---

## What it does

* Boots a **FastAPI** app with a startup hook that initializes the database connection (`init_db`).
* Provides endpoints for:

  * **Service health** (`/healthz`)
  * **Document listing + retrieval** (`/documents`, `/documents/{id}`)
  * **Document sections** (`/documents/{id}/sections`)
  * **Mentions**:

    * By document (`/documents/{id}/mentions`)
    * Across all docs (`/mentions`) with joined metadata (doc title, section idx)

---

## Endpoints

### `GET /healthz`

Returns a simple `{ "ok": true }` if the API is up.

---

### `GET /documents`

Returns all `Document` records, ordered by `created_at DESC`.
**Response:** list of `Document` objects.

---

### `GET /documents/{doc_id}`

Returns the document with that ID or `404 Not found`.

---

### `GET /documents/{doc_id}/sections`

Returns all `Section`s belonging to the document, ordered by section index.

---

### `GET /documents/{doc_id}/mentions`

Returns mentions within a given document.

Query params:

* `label` *(optional)* — filter by entity label (e.g., `PERSON`, `LOC`)
* `q` *(optional)* — substring match on `surface` text (case-insensitive, `ilike`)
* `limit` *(default: 200)* — max rows returned

**Response:** list of `Mention` rows.

---

### `GET /mentions`

Returns mentions across all documents, joined with **Document title** and **Section index**.

Query params:

* `label` *(optional)* — filter by entity type
* `q` *(optional)* — filter by substring of mention surface
* `limit` *(default: 200)* — max rows

**Response:** list of dicts:

```json
{
  "mention": { ... Mention fields ... },
  "doc_title": "Epic of the Twin Moons",
  "section_idx": 7
}
```

---

## Environment

* Uses the same DB config as other Lore modules (`DATABASE_URL` or fallback SQLite at `/app/data/lore.db` via `lore_common.db`).
* No additional env vars required beyond DB connectivity.

---

## Run locally

```bash
uvicorn __main__:app --host 0.0.0.0 --port 8002 --reload
```

Now test:

```bash
curl http://localhost:8002/healthz
curl http://localhost:8002/documents
curl "http://localhost:8002/mentions?q=Tomoe&label=PERSON"
```

---

## Docker

A `Dockerfile` is included. Typical run:

```bash
docker build -t lore-api .
docker run --rm -p 8002:8002 \
  -e DATABASE_URL=sqlite:////app/data/lore.db \
  -v $(pwd)/data:/app/data \
  lore-api uvicorn __main__:app --host 0.0.0.0 --port 8002
```

---

## How it fits in

```
[lore_worker] -> DB: Documents + Sections + Mentions
     ^                                   |
     |                                   v
[lore_watcher]                     [lore_api HTTP]  <--- UI, agents, external tools
```

* **Producers**: ingest + NER pipelines populate `Document`, `Section`, `Mention`
* **Consumer**: `lore_api` provides a read-only interface to browse that data

---

## Extending

* Add filters by `created_at`, `author`, or custom metadata.
* Add POST endpoints for annotations or corrections.
* Wrap with authentication if exposed beyond local dev.

---

Do you want me to also generate an **OpenAPI summary** (endpoint list + schemas) in the README so you have a self-documenting spec for clients?
