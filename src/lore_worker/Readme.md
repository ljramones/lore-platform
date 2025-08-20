# lore\_worker — Temporal ingest worker for Lore-a-pedia

`lore_worker` is the **Temporal worker + workflow** that turns newly arrived files (from `lore_watcher` or manual starts) into persisted **Documents** and **Sections** in the shared Lore DB. It exposes:

* A **Workflow**: `IngestWorkflow(path)` → returns the new `document_id`.&#x20;
* An **Activity**: `parse_and_store(path)` that reads the file, chunks it into sections, and saves it.&#x20;
* A **Worker bootstrap** (`__main__`) that registers the workflow + activity on a task queue.&#x20;
* A tiny **CLI** to start the workflow against a Temporal server.&#x20;

---

## How it fits in

```
lore_watcher (file created) ──▶ IngestWorkflow(path) ──▶ parse_and_store
                                                      └─▶ Lore DB: Document + Sections
```

Downstream modules (NER, indexer, search) build on the stored sections.

---

## Components

### Workflow: `IngestWorkflow`

* Runs a single activity `parse_and_store` with 5-minute timeouts and up to **3** retries.
* Returns the `document_id` created by the activity.&#x20;

### Activity: `parse_and_store(path: str) -> int`

1. `init_db()`
2. `read_file(path)` → raw text
3. `chunk_text(text)` → list of section strings (or dicts that are normalized)
4. `add_document_with_sections(path, title, sections)` → returns `document_id`
   Normalization accepts either `str` or `{..., "text": "..."}` items.&#x20;

### Worker bootstrap

* Resolves Temporal **address** from `TEMPORAL_ADDRESS` / `TEMPORAL_TARGET` / `TARGET` (default `host.docker.internal:7233`).
* Resolves **task queue** from `TEMPORAL_TASK_QUEUE` / `TASK_QUEUE` (default `lore-ingest`).
* Connects to Temporal and registers `IngestWorkflow` and `parse_and_store`.
* Stays alive waiting for tasks.&#x20;

### CLI launcher

* Connects to Temporal at `TEMPORAL_ADDRESS` (default `localhost:7233`).
* Starts `IngestWorkflow` with a random `ingest-<uuid>` workflow ID, on task queue `lore-ingest`, with a retry policy of 3 attempts.&#x20;

---

## Environment variables

| Name                                              | Default                                                       | Purpose                                                |
| ------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------ |
| `TEMPORAL_ADDRESS` / `TEMPORAL_TARGET` / `TARGET` | `host.docker.internal:7233` (worker) / `localhost:7233` (CLI) | Temporal server address (`host:port`, **no scheme**)   |
| `TEMPORAL_TASK_QUEUE` / `TASK_QUEUE`              | `lore-ingest`                                                 | Task queue worker listens on & CLI submits to          |

> Note: If you include a URL scheme in the address (e.g., `http://…`) the worker will raise an error—it expects only `host:port`.&#x20;

---

## Run the worker (local)

```bash
# Install your project deps (temporalio, sqlmodel, etc.)
export TEMPORAL_ADDRESS=localhost:7233
export TEMPORAL_TASK_QUEUE=lore-ingest

python -m lore_worker
# [lore-worker] Connecting to Temporal at localhost:7233 on task queue 'lore-ingest'
```



---

## Start a workflow (CLI)

```bash
python -m lore_worker.cli /absolute/path/to/file.md
# prints the new document_id
```

* Uses workflow name `"IngestWorkflow"` and a random `ingest-<uuid>` as the workflow ID.
* Submits to `lore-ingest` with a 3-attempt retry policy.&#x20;

---

## What gets written

The activity derives the **title** from the filename and stores:

* **Document**: path, title
* **Sections**: list of strings (after normalization)

Returns the created `document_id`.&#x20;

---

## Operational notes

* **Timeouts & retries** are set on both workflow→activity call and CLI submission (max 3 attempts). &#x20;
* **Chunking strategy** is delegated to `lore_common.parse.chunk_text`; you can swap that without changing the worker.&#x20;
* **Activity import location**: activities are imported **inside** the worker process after connecting to Temporal (keeps module import side effects minimal).&#x20;

---

## Docker

A `Dockerfile` is included for containerized deployment of the worker. Ensure the container can reach your Temporal server and your DB. (Run the CLI either from your host or an admin/debug container.) *(See your repo’s Dockerfile for image specifics.)*

---

## Extending

* Add more activities (OCR, format-specific parsing) and call them from the workflow.
* Emit metrics (processed files, sections) around `parse_and_store`.
* Add input validation (file existence, allowed extensions) before reading.

---

## File map

* `__main__.py` — worker bootstrap: connect, register, run forever.&#x20;
* `activities.py` — `parse_and_store` activity + section normalization.&#x20;
* `ingest_workflow.py` — `IngestWorkflow` definition.&#x20;
* `cli.py` — convenience launcher to start the workflow.&#x20;

---
