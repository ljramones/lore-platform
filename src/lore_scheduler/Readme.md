# lore\_scheduler — Temporal kickoff loop for Lore-a-pedia

A tiny **orchestration shim** that watches your Lore DB for documents **missing NER mentions** and kicks off a Temporal workflow (`MentionsWorkflow`) to extract them. It connects to Temporal once, polls on an interval, and starts up to 20 workflows per cycle.&#x20;

---

## What it does

* Initializes the shared Lore DB and locates **documents without mentions** using `docs_without_mentions(limit=20)`.&#x20;
* Connects to Temporal (`temporalio.client.Client.connect`) at `TEMPORAL_TARGET`.&#x20;
* For each candidate doc, **starts** `MentionsWorkflow` on the configured **task queue** (default: `lore-ner`).&#x20;
* Repeats every `SCHED_INTERVAL` seconds.&#x20;

Workflow IDs are generated as:
`mentions-{doc_id}-{unix_timestamp}` — keeps runs unique while still human-readable.&#x20;

---

## Environment

| Variable              | Default         | Purpose                                                                    |
| --------------------- | --------------- | -------------------------------------------------------------------------- |
| `SCHED_INTERVAL`      | `5`             | Seconds between polling cycles.                                            |
| `TEMPORAL_TARGET`     | `temporal:7233` | Temporal host\:port to connect the client.                                 |
| `TEMPORAL_TASK_QUEUE` | `lore-ner`      | Task queue where `MentionsWorkflow` is registered (by `lore-ner` worker).  |

---

## Runtime topology

```
[Lore DB] --(docs_without_mentions)--> [lore_scheduler]
                                    \-> start_workflow("MentionsWorkflow", doc_id) --> [Temporal Server] --> [lore-ner Worker]
```

* **lore\_scheduler**: lightweight poller/launcher
* **lore-ner**: the worker that actually extracts and persists mentions
* **Temporal**: visibility, retries, and orchestration

All three can be run locally (Docker) or in your cluster.

---

## How to run

### Local (Python)

```bash
# Inside the lore_scheduler module directory
export SCHED_INTERVAL=5
export TEMPORAL_TARGET=temporal:7233
export TEMPORAL_TASK_QUEUE=lore-ner

python -m lore_scheduler
```

This executes `asyncio.run(loop())`, wires the DB, connects to Temporal, and begins polling/starting workflows. You’ll see logs like:
`Started MentionsWorkflow for doc 42`.&#x20;

### Docker

A `Dockerfile` is included. Example:

```bash
docker build -t lore-scheduler .
docker run --rm \
  -e SCHED_INTERVAL=5 \
  -e TEMPORAL_TARGET=temporal:7233 \
  -e TEMPORAL_TASK_QUEUE=lore-ner \
  --network=lore-net \
  lore-scheduler
```

Make sure the container can reach:

* your **Temporal server** at `TEMPORAL_TARGET`
* the **Lore DB** used by `lore_common.db` (same volume/connection as other services)&#x20;

---

## Operational notes

* **Throughput**: processes up to **20 docs per cycle** (tune by changing the `docs_without_mentions(limit=20)` call).&#x20;
* **Idempotency**: uniqueness of workflow IDs prevents duplicate-run collisions within the same second for a given doc. If you need strict one-run-at-a-time per document, adopt a deterministic ID scheme (e.g., `mentions-{doc_id}`) plus Temporal’s start options, or add DB-side leasing.
* **Resilience**: Exceptions during a cycle are caught and logged; the loop continues after sleeping `SCHED_INTERVAL`.&#x20;
* **Task queue**: Must match the queue used by your **lore-ner worker** registration so that `MentionsWorkflow` is picked up.&#x20;

---

## Typical deployment (with other services)

* **lore\_watcher**: ingests and sections new manuscripts
* **lore\_scheduler** *(this)*: finds docs lacking mentions and starts workflows
* **lore-ner**: Temporal worker/activity that extracts mentions and writes to DB
* **lore\_indexer**: indexes sections to Chroma for retrieval/search

This keeps the ingestion-to-NER-to-indexing lane flowing with clear separation of concerns.

---

## Troubleshooting

* **Can’t connect to Temporal**: verify `TEMPORAL_TARGET` and network policies/firewalls.&#x20;
* **Workflows not picked up**: ensure `TEMPORAL_TASK_QUEUE` matches the lore-ner worker’s queue and that the worker is running.&#x20;
* **No documents scheduled**: confirm your DB has docs/sections and that they truly lack mentions per `docs_without_mentions`.&#x20;

---

## File map

* `__main__.py` — the async polling loop and Temporal client kickoff. Run via `python -m lore_scheduler`.&#x20;
* `Dockerfile` — container image for the scheduler (ensure runtime env vars are provided).&#x20;

