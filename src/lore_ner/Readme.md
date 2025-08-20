# lore-ner — Named-Entity Extraction Worker (Temporal-ready)

`lore-ner` finds entities (people, places, orgs, events, etc.) in your fictional documents and writes **mention** records back to the shared Lore DB. It can run either as a **simple polling worker** or as a **Temporal activity/workflow** for orchestration with the rest of your Lore-a-pedia pipeline.

---

## What it does

* Loads a spaCy model (configurable, default: `en_core_web_sm`).
* Scans documents that **don’t yet have mentions**.
* For each section, extracts NER spans and records:

  * surface text, entity label
  * offsets within the section and within the whole document
* Writes all mentions back to the DB in one shot per doc.&#x20;

When used with Temporal, it exposes:

* An **activity**: `extract_mentions_for_doc(doc_id)` that runs NER and persists mentions.
* A **workflow**: `MentionsWorkflow` that executes the activity.
* A **worker** bootstrap (`run_worker`) that registers the workflow + activity on a task queue.&#x20;

---

## Modes

### 1) Standalone Polling Worker

A lightweight loop that wakes up every `NER_POLL_INTERVAL` seconds, grabs up to 5 documents missing mentions, extracts entities, and saves them. Useful for local/dev or when you don’t need orchestration.&#x20;

### 2) Temporal Worker

Registers a workflow (`MentionsWorkflow`) and an activity (`extract_mentions_for_doc`). Point it at your Temporal server and enqueue work onto the configured task queue from upstream services (e.g., after ingestion or sectioning).&#x20;

---

## Entity types

By default, the Temporal activity **filters** to a curated subset of spaCy labels:
`{"PERSON","GPE","LOC","ORG","NORP","WORK_OF_ART","EVENT"}`.
This keeps the graph focused on narrative-relevant entities.&#x20;

---

## Data written to DB

Each mention includes:

* `section_id`
* `start_s`, `end_s` (span within the section)
* `start_doc`, `end_doc` (span within the full doc; computed from section’s base offset)
* `surface` (text)
* `label` (spaCy NER label)
  Both modes compute identical fields before calling the shared DB helper to persist. &#x20;

---

## Environment variables

| Variable              | Default          | Purpose                                              |
| --------------------- | ---------------- | ---------------------------------------------------- |
| `SPACY_MODEL`         | `en_core_web_sm` | Which spaCy model to load.                           |
| `NER_POLL_INTERVAL`   | `10`             | Seconds between polling cycles (standalone worker).  |
| `TEMPORAL_TARGET`     | `temporal:7233`  | Temporal host\:port for the worker.                  |
| `TEMPORAL_TASK_QUEUE` | `lore-ner`       | Task queue for registering workflow/activity.        |

> The module relies on `lore_common.db` helpers (e.g., `init_db`, `docs_without_mentions`, `list_sections`, `add_mentions`) and your existing `Document/Section` schema.

---

## Running

### A) Standalone polling worker

```bash
# Make sure your DB is reachable and contains documents + sections
export SPACY_MODEL=en_core_web_sm
export NER_POLL_INTERVAL=10

python -m lore_ner
```

This starts the infinite loop that periodically extracts and writes mentions.&#x20;

### B) Temporal worker

```python
# run_worker.py (example)
import asyncio
from lore_ner.ner_worker import run_worker

if __name__ == "__main__":
    asyncio.run(run_worker())
```

```bash
export TEMPORAL_TARGET=temporal:7233
export TEMPORAL_TASK_QUEUE=lore-ner
python run_worker.py
```

This registers:

* `MentionsWorkflow` (workflow)
* `extract_mentions_for_doc` (activity)
  on the `lore-ner` queue against your Temporal cluster.&#x20;

To kick off processing, schedule a workflow run from your orchestrator (e.g., after ingestion):

```python
from temporalio.client import Client
from lore_ner.ner_worker import MentionsWorkflow

async def start(doc_id: int):
    client = await Client.connect("temporal:7233")
    handle = await client.start_workflow(
        MentionsWorkflow.run,
        doc_id,
        id=f"mentions-{doc_id}",
        task_queue="lore-ner",
    )
    print("Started", handle.id)
```

---

## Notes & behavior

* **Model loading**: The Temporal activity lazily loads spaCy once per worker process; on missing model it can download as a fallback (handy for dev, pin in prod).&#x20;
* **Batching**: The polling worker processes up to **5 docs per cycle** by default (change in the DB helper if needed).&#x20;
* **Offsets**: Document-level offsets are derived by adding the section’s starting character to the entity span—ensures exact cross-referencing back to the source text. &#x20;
* **Resilience**: Both modes catch exceptions, continue the loop/worker, and log diagnostic messages.&#x20;

---

## Docker

A `Dockerfile` is included so you can run either mode in a container. For Temporal mode, make sure the container can reach your Temporal server and that the spaCy model is available (either baked into the image or downloaded at startup).&#x20;

---

## When to use which mode?

* **Use polling** when you want a simple “set-and-forget” background service that keeps your mentions table fresh.
* **Use Temporal** when you need robust orchestration, retries, visibility, and to chain NER with upstream/downstream steps (ingestion ➜ sectioning ➜ NER ➜ indexing/search).

---

## Next steps

* Add custom entity rules (e.g., `EntityRuler`) for world-specific names/title patterns.
* Upgrade to a larger spaCy model or a transformer-backed pipeline for better accuracy.
* Emit metrics for processed docs/spans and latency per section to your observability stack.
