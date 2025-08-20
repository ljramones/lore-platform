# High-level workflow set

## 1) `DocumentPipelineWorkflow` (top-level, one per *document version*)

**Purpose:** orchestrates the full path for a single file: ingest → mentions → relations/time → verify → review → publish.

**Phases (state machine):**

1. **INGEST** → parse & chunk → write `document`/`section`.
2. **MENTIONS** → NER over sections → write `mention`.
3. **RELATIONS** → rules pass → propose `proposed_relation`, `proposed_event`, `time_expression`.
4. **VERIFY (gated)** → only low-confidence/contradictory items escalated to GPT-5/Claude/Gemini.
5. **REVIEW** → block until human decisions (signals) accept/reject/merge.
6. **PUBLISH** → write to canon tables; add provenance.
7. **INDEX (optional)** → push sections to Chroma v2 (research lane stays separate).
8. **DONE**.

**Identity & idempotency:**

* `workflow_id = doc::<path_hash>::v::<content_hash>`.
* If a file changes, the watcher starts a **new version**; the old one auto-cancels (see signals below).

**Task queue:** `lore-pipeline`.

---

## 2) Child workflows (called by the pipeline)

* `MentionsWorkflow(doc_id)` → runs NER, writes `mention`. (You already have this.)
* `RelationsWorkflow(doc_id)` → finds `appears_in / located_in / teacher_of / …` proposals.
* `VerifyWorkflow(proposal_batch)` → calls cloud models under budget.
* `ReviewWorkflow(doc_id)` → waits on reviewer signals, returns accepted IDs.

**Task queues:** `lore-ner`, `lore-rel`, `lore-verify`, `lore-review`.

---

## 3) On-demand workflows

* `RagHarvestWorkflow(query|url)` → fetch + clean + chunk + embed to Chroma v2 (`/api/v2/...`), write `document(source_type='web')`.
* `TropeAuditWorkflow(scene_id|text)` → detect trope candidates; write to idea/trope lane.

---

# Signals & queries (controls you’ll use)

**Signals (to `DocumentPipelineWorkflow`):**

* `Pause()` / `Resume()` — temporarily halt/resume phases.
* `Supersede(new_content_hash)` — cancel this run if a newer version is in flight.
* `ReviewerDecision(proposal_id, decision, merge_with_id?)` — accept/reject/merge.
* `BudgetUpdate(provider, daily_tokens)` — raise/lower the verify gate.
* `Abort(reason)` — cancel gracefully.

**Queries (instant status):**

* `Status()` → phase, % complete per phase, counts (sections/mentions/proposals/accepted).
* `DocInfo()` → `doc_id`, `path`, `content_hash`, created\_at.
* `Pending()` → list of proposal IDs awaiting review.

**Search attributes** (Temporal):
`DocumentPath`, `ContentHash`, `Lane=canon`, `LastPhase`, `DocId` — lets you find/rerun from UI/CLI.

---

# “Happy path” (sequence)

1. **Watcher** detects a file → starts `DocumentPipelineWorkflow(path, mtime, size)`.
2. Pipeline **INGEST** activity parses + chunks, writes DB, returns `doc_id`.
3. Pipeline starts child **MentionsWorkflow(doc\_id)** and awaits result.
4. Pipeline starts **RelationsWorkflow(doc\_id)**; when done, it tallies proposal confidences.
5. If needed, **VerifyWorkflow** runs on the low-confidence/contradictory batch (budget-gated).
6. Pipeline enters **REVIEW** and waits on **`ReviewerDecision` signals** (from your UI/API).
7. Accepted items are **published** to canon; provenance is written.
8. Optionally **INDEX** sections to Chroma v2 (or just defer to RAG flows).
9. Mark **DONE**; expose status via `Status()` query.

If the file changes mid-process, your watcher sends `Supersede(new_hash)`; the pipeline cancels/compacts, and the new version runs.

---

# Retry/timeout policy (defaults that work well)

* **Activities:** `start_to_close=5–10m`, retry backoff `1s → 30s`, max attempts `8`.
* **Workflows:** long-lived, rely on **signals**; use **continue-as-new** if the history grows (e.g., after N phases or N signals).
* **Verification**: rate-limited by a tokens “budget” in workflow state; if exhausted, park in REVIEW.

---

# Suggested task queues

| Queue           | Who listens              | What runs                  |
| --------------- | ------------------------ | -------------------------- |
| `lore-pipeline` | Orchestrator worker      | `DocumentPipelineWorkflow` |
| `lore-ingest`   | Ingest worker            | parse & chunk              |
| `lore-ner`      | NER worker               | mentions                   |
| `lore-rel`      | Relation worker          | rules extraction           |
| `lore-verify`   | Verify worker            | cloud model calls          |
| `lore-review`   | (optional) Review worker | simple gates & bookkeeping |
| `lore-rag`      | RAG harvester            | web fetch/clean/embed      |

---

# Minimal pipeline skeleton (Python, Temporal SDK)

```python
# src/lore_worker/pipeline_workflow.py
from __future__ import annotations
from datetime import timedelta
from temporalio import workflow, activity

# ---- Activities (signatures only here) ----
@activity.defn
async def parse_and_store(path: str) -> int: ...
@activity.defn
async def extract_relations(doc_id: int) -> dict: ...
@activity.defn
async def verify_proposals(batch_ids: list[int]) -> dict: ...
@activity.defn
async def publish_accepts(doc_id: int, accepted_ids: list[int]) -> int: ...

# ---- Child workflows (you already have MentionsWorkflow) ----
@workflow.defn
class MentionsWorkflow:
    @workflow.run
    async def run(self, doc_id: int) -> int: ...

@workflow.defn
class RelationsWorkflow:
    @workflow.run
    async def run(self, doc_id: int) -> dict: ...  # returns proposal stats

@workflow.defn
class VerifyWorkflow:
    @workflow.run
    async def run(self, ids: list[int]) -> dict: ...

# ---- Top-level pipeline ----
@workflow.defn
class DocumentPipelineWorkflow:
    def __init__(self):
        self.doc_id: int | None = None
        self.phase = "INIT"
        self.accepted: list[int] = []
        self.pending: set[int] = set()
        self.paused = False

    # Signals
    @workflow.signal
    def Pause(self): self.paused = True

    @workflow.signal
    def Resume(self): self.paused = False

    @workflow.signal
    def ReviewerDecision(self, proposal_id: int, decision: str, merge_with: int | None = None):
        # 'accept' | 'reject' | 'merge'
        if decision == "accept": self.accepted.append(proposal_id)
        if proposal_id in self.pending: self.pending.remove(proposal_id)

    # Queries
    @workflow.query
    def Status(self) -> dict:
        return {"phase": self.phase, "doc_id": self.doc_id, "pending": len(self.pending), "accepted": len(self.accepted)}

    @workflow.run
    async def run(self, path: str, content_hash: str):
        # PHASE: INGEST
        self.phase = "INGEST"
        self.doc_id = await workflow.execute_activity(
            parse_and_store, path,
            start_to_close_timeout=timedelta(minutes=5),
            schedule_to_close_timeout=timedelta(minutes=10),
        )

        # PHASE: MENTIONS (child)
        self.phase = "MENTIONS"
        await workflow.execute_child_workflow(MentionsWorkflow.run, self.doc_id, id=f"mentions-{self.doc_id}")

        # PHASE: RELATIONS (child)
        self.phase = "RELATIONS"
        rel_stats = await workflow.execute_child_workflow(RelationsWorkflow.run, self.doc_id, id=f"relations-{self.doc_id}")
        low_conflict_ids = rel_stats.get("needs_verify", [])
        self.pending = set(rel_stats.get("needs_review", []))

        # PHASE: VERIFY (child if needed)
        if low_conflict_ids:
            self.phase = "VERIFY"
            verify_out = await workflow.execute_child_workflow(VerifyWorkflow.run, low_conflict_ids, id=f"verify-{self.doc_id}")
            self.accepted.extend(verify_out.get("auto_accept", []))
            self.pending |= set(verify_out.get("needs_review", []))

        # PHASE: REVIEW (signals drive this)
        self.phase = "REVIEW"
        while self.pending or not self.accepted:
            # park for a bit; signals can mutate pending/accepted
            await workflow.sleep(2)

        # PHASE: PUBLISH
        self.phase = "PUBLISH"
        await workflow.execute_activity(
            publish_accepts, self.doc_id, self.accepted,
            start_to_close_timeout=timedelta(minutes=5),
        )

        self.phase = "DONE"
        return {"doc_id": self.doc_id, "accepted": self.accepted}
```

**Watcher change:** start `DocumentPipelineWorkflow` instead of `IngestWorkflow`, passing `content_hash` (e.g., sha256 of file).
**Scheduler:** can go away once the pipeline triggers `MentionsWorkflow` itself.

---

# How this maps to what you’ve built

* You already have **ingest** and **mentions** running.
* Next, add the **Relations** worker/child workflow (rules → proposals).
* Then the **Verify** child (model-gated).
* Finally, a minimal **Review API** that calls the **`ReviewerDecision` signal** so the pipeline can unblock and publish.

If you want, I can sketch the `RelationsWorkflow` MVP (tables + simple rules + activities) so your pipeline does a full run end-to-end.
