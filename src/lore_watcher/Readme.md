# lore\_watcher — File-system watcher → Temporal ingest launcher

`lore_watcher` watches a local “inbox” folder for new manuscript files and immediately starts a Temporal **IngestWorkflow** for each new file. It’s the first hop in the Lore-a-pedia pipeline (watch → ingest → section → NER → index → search).&#x20;

---

## What it does

* Watches a single directory (non-recursive) using `watchdog`. When a file is created with one of the allowed extensions, it triggers a Temporal workflow start.&#x20;
* Accepts **PDF, DOCX, Markdown, and TXT**: `[".pdf", ".docx", ".md", ".txt"]`.&#x20;
* Starts `IngestWorkflow` with arguments:

  * `arg0 = absolute file path`
  * `workflow_id = "ingest-{filename}-{unix_ts}"`
  * `task_queue = $TEMPORAL_TASK_QUEUE` (default `lore-ingest`)&#x20;
* Connects to Temporal at `$TEMPORAL_TARGET` (default `temporal:7233`).&#x20;
* Logs a friendly “Started workflow …” message for each file.&#x20;

---

## Environment variables

| Name                  | Default         | Purpose                                       |
| --------------------- | --------------- | --------------------------------------------- |
| `INBOX_DIR`           | `/app/inbox`    | Directory to watch for new files.             |
| `TEMPORAL_TASK_QUEUE` | `lore-ingest`   | Task queue where `IngestWorkflow` is polled.  |
| `TEMPORAL_TARGET`     | `temporal:7233` | Temporal server endpoint used by the client.  |

---

## Run locally

```bash
# 1) Ensure Temporal server is reachable (e.g., docker-compose up for your stack)
# 2) Prepare an inbox directory
mkdir -p /tmp/lore-inbox

# 3) Configure environment
export INBOX_DIR=/tmp/lore-inbox
export TEMPORAL_TARGET=temporal:7233
export TEMPORAL_TASK_QUEUE=lore-ingest

# 4) Start the watcher
python -m lore_watcher
# -> "Watching /tmp/lore-inbox for new files..."
```

Now drop a file into the inbox:

```bash
cp ~/Manuscripts/chapter01.md /tmp/lore-inbox/
# -> "Started workflow ingest-chapter01.md-1724180000 for /tmp/lore-inbox/chapter01.md"
```

(IDs include the filename and a UNIX timestamp to keep them unique.)&#x20;

---

## Docker

A `Dockerfile` is provided. Typical run:

```bash
docker build -t lore-watcher .
docker run --rm \
  -e INBOX_DIR=/inbox \
  -e TEMPORAL_TARGET=temporal:7233 \
  -e TEMPORAL_TASK_QUEUE=lore-ingest \
  -v $(pwd)/inbox:/inbox \
  --network=lore-net \
  lore-watcher
```

Make sure the container can reach your Temporal server at `TEMPORAL_TARGET`.&#x20;

---

## Workflow contract

* **Workflow name**: `"IngestWorkflow"` (string form passed to `start_workflow`).&#x20;
* **Input**: the **absolute path** to the new file.&#x20;
* **Queue**: `$TEMPORAL_TASK_QUEUE` (your ingest worker must register on this queue).&#x20;

> Downstream services (e.g., sectioning, NER, indexing) are not handled here—`lore_watcher` only **starts ingestion**. Orchestration continues within your ingest workflow definition.

---

## Operational notes

* **Non-recursive watching**: only the top level of `INBOX_DIR` is monitored (no subfolders).&#x20;
* **Allowed file types** are extension-checked, case-insensitive. Adjust in code if you need more.&#x20;
* **Backpressure**: Each file leads to one workflow start. Use Temporal’s workflow concurrency/queueing and your ingest worker’s rate limits to throttle.&#x20;
* **Shutdown**: Ctrl-C stops the `watchdog` observer cleanly.&#x20;

---

## Troubleshooting

* **Nothing happens when I drop a file**

  * Confirm the extension is one of `.pdf .docx .md .txt`.&#x20;
  * Ensure `INBOX_DIR` matches the directory you’re writing to.&#x20;
  * Verify connectivity to Temporal (`TEMPORAL_TARGET`).&#x20;
* **Workflows don’t pick up**

  * Check the ingest worker is running and **registered to the same task queue** as `TEMPORAL_TASK_QUEUE`.&#x20;
* **Multiple triggers for one file**

  * Some editors create temp files or write files in multiple passes; consider dropping final artifacts (e.g., copy rather than save-in-place), or extend the handler to de-bounce events.

---

## How it fits in

```
[Author / Import] --> [INBOX_DIR] --(file create)--> lore_watcher
                                       \--> start_workflow("IngestWorkflow", path) --> [Temporal] --> [Ingest worker]
```

From there your workflow handles parsing, sectioning, DB writes, and kicks off the rest of the pipeline.&#x20;

---

## File map

* `__main__.py` — Watchdog setup, Temporal client, and `on_created` handler that starts `IngestWorkflow`. Run with `python -m lore_watcher`.&#x20;
* `Dockerfile` — Container image for deployment (bind-mount an inbox volume).&#x20;
