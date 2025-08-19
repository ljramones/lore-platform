# Lore-a-pedia — Concept README

> A local-first **lore bank + exploration platform** for historical fantasy & sci-fi worldbuilding.
> Ingest your manuscripts, extract entities/relations/timelines, cross-link with curated web research, and explore narrative tropes—**with human-in-the-loop control**.

---

## Table of Contents

* [Vision & Non-Goals](#vision--non-goals)
* [Core Ideas](#core-ideas)
* [Architecture Overview](#architecture-overview)
* [Components](#components)
* [Persistence & Data Model](#persistence--data-model)
* [Extraction Pipeline](#extraction-pipeline)
* [RAG+ (Web Research Lane)](#rag-web-research-lane)
* [Trope Explorer](#trope-explorer)
* [Orchestration via Temporal](#orchestration-via-temporal)
* [MCP Tools & Public APIs](#mcp-tools--public-apis)
* [Review Workflow & Console](#review-workflow--console)
* [Governance: Confidence, Provenance, Lanes](#governance-confidence-provenance-lanes)
* [Security, Privacy, and Licenses](#security-privacy-and-licenses)
* [Observability & Cost Controls](#observability--cost-controls)
* [Environments & Deployment](#environments--deployment)
* [Testing Strategy](#testing-strategy)
* [Roadmap](#roadmap)
* [Glossary](#glossary)
* [Appendix A — Schemas (Concept)](#appendix-a--schemas-concept)
* [Appendix B — Prompts (Concept)](#appendix-b--prompts-concept)
* [Appendix C — Events & Policies](#appendix-c--events--policies)

---

## Vision & Non-Goals

**Vision.**
Build a durable, **canon-first** knowledge base for your fiction that:

* Ingests local drafts (PDF/DOCX/MD) continuously,
* Extracts **entities** (Characters, Places, Artifacts, Factions), **events**, **relations**, and **timelines**,
* Keeps **provenance** (document+char spans) for every accepted fact,
* Curates a separate, attributed **research lane** for real history/mythology,
* Provides an **idea/trope lane** for speculative brainstorms,
* Offers **RAG** search over curated web sources without polluting canon,
* Uses **human-in-the-loop** review to promote proposals into canon,
* Scales from single-machine to team use with minimal changes.

**Non-Goals (for v1).**

* No auto-canonization without human approval for high-impact facts (lineage, death, world rules).
* No general web scraping at scale; use whitelists and manual adds.
* No heavy knowledge graph platform required; start relational, project graph views as needed.

---

## Core Ideas

### Three Knowledge Lanes

* **Canon** — accepted facts in your universe; fuels timelines/graphs/queries.
* **Research** — cleaned, attributed external sources (history, myth, archaeology).
* **Idea/Trope** — speculative “what-ifs”, trope patterns, and subversions; inspire writing but don’t become canon automatically.

### Relationship Vocabulary (controlled)

`parent_of, descendant_of, ally_of, enemy_of, teacher_of, member_of, appears_in, located_in, holds, origin_of, inspired_by, embodies`

---

## Architecture Overview

```mermaid
flowchart LR
  subgraph Agents/Orchestrator
    A1[Strands Agents] --> TMP[Temporal Workflows]
    MEM[Mem0 (short-term memory)]
    A1 --- MEM
  end

  subgraph MCP Tools (stateless)
    W1[Doc Watcher]
    P1[Parser]
    H1[Web Harvester]
    CLN[Cleaner/Chunker]
    X1[NER + Coref]
    X2[Relation/Timeline Extractor]
    V1[Verifier (GPT-5/Claude/Gemini)]
    T1[Trope Miner]
  end

  subgraph Services (stateful APIs)
    RQ[Review Queue API]
    LQ[Lore Query API]
    RAG[RAG API]
    UI[Lore Console]
  end

  subgraph Persistence
    DB1[(Canon DB)]
    DB2[(Research DB)]
    DB3[(Idea/Trope DB)]
    VEC[(Vector Store)]
    BLOB[(Blob Store)]
  end

  TMP --> W1 & H1 & X1 & X2 & V1 & T1
  W1 --> P1 --> DB1
  H1 --> CLN --> DB2 & VEC & BLOB
  X1 --> RQ
  X2 --> RQ
  V1 --> RQ
  RQ --> DB1
  T1 --> DB3
  RAG <---> DB2 & VEC
  LQ --> DB1
  UI <---> RQ & LQ & RAG
```

---

## Components

### MCP Tools (stateless)

* **Doc Watcher** — watches a folder; emits file arrivals.
* **Parser** — PDF/DOCX/MD → plain text, sections, char offsets; FTS indexing.
* **Web Harvester** — curated search + URL fetch; stores cleaned text with metadata.
* **Cleaner/Chunker** — readability, boilerplate removal, chunking for RAG.
* **NER + Coref** — detects entities & coreference clusters; proposes mentions.
* **Relation/Timeline Extractor** — rules + dependency patterns; proposes relations/events/time expressions.
* **Verifier** — gated calls to GPT-5 / Claude 4 / Gemini for low-confidence or conflicting items; JSON-only, evidence-required.
* **Trope Miner** — detects trope candidates and links them to scenes/entities.

### Services (stateful)

* **Review Queue API** — CRUD for proposals; accept/reject/merge; domain rules.
* **Lore Query API** — entity cards, timelines, adjacency views, search.
* **RAG API** — hybrid (keyword + vector) retrieval, idea synthesis endpoints.
* **Lore Console (UI)** — human review, browsing canon/research/idea, conflict dashboards.

### Orchestrator

* **Temporal** — durable workflows, retries, human signals, rate limits.

### Persistence (pluggable)

* **Canon DB** — relational (SQLite → Postgres).
* **Research DB** — relational with FTS; hybrid retrieval hooks.
* **Idea/Trope DB** — relational; links to scenes/entities.
* **Vector Store** — Chroma (local) → Qdrant or pgvector.
* **Blob Store** — local FS → MinIO (S3-compatible).

---

## Persistence & Data Model

### Canon (relational core)

* `entity(id, type[character|place|artifact|faction|legend|motif], display_name, attrs_json, notes, lane='canon')`
* `alias(id, entity_id, name)`
* `event(id, title, time_start?, time_end?, place_id?, notes, lane='canon')`
* `relation(id, subj_id, predicate, obj_id, time_start?, time_end?, place_id?, confidence, lane, notes)`
* `participation(event_id, entity_id, role)`
* `provenance(kind['entity'|'event'|'relation'], ref_id, source_type['local'|'web'], document_id, section_id, evidence_json, model, decided_by['auto'|'human'])`

### Proposals (review queue)

* `proposed_entity`, `proposed_event`, `proposed_relation` (mirror canon tables + `status`, `created_at`, `reasons`, `conflicts[]`)

### Text & Structure

* `document(id, path_or_url, title, source_type['local'|'web'], publisher?, published_at?, retrieved_at?, era_hint?)`
* `section(id, document_id, idx, start_char, end_char, heading, text)`  *(FTS on text)*

### Research (web lane)

* Same `document/section` structure; each chunk linked to embeddings; all rows **lane='research'** by default.

### Idea/Trope Lane

* `trope(id, name, category, description, source_ref)`
* `idea_card(id, title, pitch, risks[], subversions[], seeds[], status['draft'|'kept'|'merged'], lane='idea')`
* Link tables: `trope_link(trope_id, entity_id|event_id|scene_id, tone, status)`

---

## Extraction Pipeline

**Local first pass (fast & deterministic)**

* NER (spaCy), Coref (fastcoref)
* Rules/dep patterns for easy edges (appears\_in, located\_in, teacher\_of from appositives, etc.)
* `dateparser` + regex for temporal phrases

**LLM-assisted verification (only when needed)**

* GPT-5 / Claude 4 to **verify/normalize** low-confidence or conflicting relations
* Gemini for **temporal normalization** (ISO + granularity) on fuzzy expressions
* Strict JSON schemas; **evidence spans required**; dual-verify for high-impact facts

**Human-in-the-loop**

* All proposals route to Review Queue
* Acceptance promotes items to canon & writes provenance

---

## RAG+ (Web Research Lane)

**Harvester**

* Whitelists (academic, museum, high-quality references) + manual URLs
* Clean & chunk into `section`; store publisher, published\_at, retrieved\_at
* Build vectors with local embeddings; attach to `section_id`

**Retriever**

* Hybrid: FTS keyword + vector similarity with filters (publisher, date, tags)
* Returns **attributed snippets** (never full content), each with URL and publisher

**Synthesis**

* Idea cards derived from snippets are stored in **Idea/Trope DB** (lane='idea')
* They **do not** alter canon until explicitly promoted via review

---

## Trope Explorer

**Model**

* Trope taxonomy (name, category, description, examples, pitfalls)
* Detected trope candidates (`trope.mine(scene_id)`) with confidence & evidence spans
* Suggestion API (`trope.suggest(context, goals[])`) to subvert/lean-in with risks

**Usage**

* Audit a scene to avoid cliché or intentionally embrace a pattern
* Link trope → entity/event via `embodies` relation (lane='idea' until accepted)

---

## Orchestration via Temporal

**Workflows (examples)**

* `IngestWorkflow(doc_path)` → parse → index → propose mentions
* `ExtractWorkflow(doc_id)` → NER/Coref → relation/time passes → proposals
* `VerifyWorkflow(proposal_ids)` → model calls → enrich confidence/evidence
* `ReviewWorkflow(batch)` → wait on human signals `Accept/Reject/Merge`
* `RagHarvestWorkflow(query|url)` → fetch → clean → index → embed

**Activities**

* Small, idempotent calls to MCP tools & APIs
* Token budgets and rate limits per provider
* Signals for human decisions and for budget exhaustion fallback

---

## MCP Tools & Public APIs

### MCP (tool surface, v1)

* `lore.ingest(path|folder)`
* `lore.extract(mode="hybrid", batch=8)`
* `lore.verify(kind, ids[])`
* `lore.review.next(kind, limit)` / `lore.review.accept(id)` / `lore.review.reject(id)` / `lore.review.merge(a,b)`
* `lore.query.entity(name|id)` / `lore.timeline(entity_id)` / `lore.graph(entity_id, depth)`
* `lore.search(text)` (FTS + optional semantic)
* `lore.import_web(query|url, whitelist_tag)`
* `trope.mine(scene_id)` / `trope.suggest(context, goals[])`
* `idea.create(seeds[])` / `idea.promote(id)`

### Public HTTP APIs (service layer)

* **Lore Query**: `/entity/:id`, `/timeline/:id`, `/graph/:id`, `/search?q=`
* **Review Queue**: `/proposals?kind=relation&status=pending`, `POST /accept`, `POST /merge`
* **RAG**: `/rag/search`, `/rag/snippets`, `/rag/synthesize`

All returns are JSON; pagination and filtering via query params.

---

## Review Workflow & Console

**Views**

* **By Entity**: proposed aliases/relations/events grouped with side-by-side evidence
* **By Predicate**: e.g., show all `parent_of` proposals for this batch
* **Conflicts**: contradictory facts with citations & char-spans

**Actions**

* Accept → promotes to canon (writes provenance, updates confidence)
* Reject → archived with reason
* Merge → unify entities/aliases; re-point references
* Annotate → add clarifications (adoption, reincarnation, mythic metaphor flags)

---

## Governance: Confidence, Provenance, Lanes

* **Confidence Gates (defaults)**

  * `≥ 0.80`: auto-publish for **low-impact** edges (e.g., appears\_in)
  * `0.60 – 0.79`: require verify or review
  * `< 0.60`: review only
  * **High-impact** edges (lineage/death/world rules): dual-verify *or* human approval
* **Provenance**

  * Every canon item links to **document + section + evidence spans** and the **model** (if any) that proposed/verified it
* **Lanes**

  * `canon` fuels timelines/graphs/exports
  * `research` is attributed background; never auto-bleeds into canon
  * `idea` is sandbox; promote via review when used

---

## Security, Privacy, and Licenses

* **Local-first.** Keep manuscripts and extracted data local by default.
* **Selective escalation.** Only send necessary excerpts to cloud models; consider redacting sensitive lines.
* **Attribution.** Store publisher, URL, published\_at, retrieved\_at for all web content; keep quotes short.
* **Licenses.** Respect site terms; store a `policy` field for each source domain; allow blocklist/allowlist.

---

## Observability & Cost Controls

* **Metrics**: ingest rate, extraction latency, acceptance rate, conflict count, token spend per provider
* **Tracing**: OpenTelemetry spans across MCP calls and Temporal activities
* **Budgets**: daily token caps per model; workflow pauses → pushes items to review
* **Caching**: hash(section\_text) → cache model outputs; invalidate on change

---

## Environments & Deployment

**Local (MVP)**

* SQLite (canon/research/idea), Chroma, optional MinIO, Temporal single worker, all services on localhost

**Team / Scale-out**

* Postgres (+ pgvector) or Qdrant, MinIO, Temporal server+workers, NATS/Redis for messaging, CI for migrations and tests

---

## Testing Strategy

* **Unit tests** for parsers, rules, policy gates, schema validation
* **Contract tests** for MCP tool JSON I/O and public APIs
* **Golden/snapshot tests** for extraction outputs on small fixture docs
* **Property tests** for merge/alias behavior and timeline math
* **Load tests** for RAG retrieval and vector queries

---

## Roadmap

**Milestone 1 — Canon Core**

* Folder watch → parse → NER/coref → propose `appears_in/located_in`
* Review console (basic) → accept → entity cards & timelines
* FTS search over sections & notes

**Milestone 2 — Relations & Time**

* Add parent/descendant/ally/enemy/teacher
* Temporal normalization + event participation
* Conflict detector; provenance everywhere

**Milestone 3 — RAG+ Research Lane**

* Web harvester + embeddings + hybrid retriever
* Idea cards from attributed snippets (kept in idea lane)
* Promote “inspired\_by/origin\_of” links via review

**Milestone 4 — Trope Explorer**

* Trope mining + suggestions + audit reports
* Subversion patterns; link to scenes/entities

**Milestone 5 — Visualization & Exports**

* Graph/adjacency views; timelines → ICS/CSV
* Graphviz export; report generators

---

## Glossary

* **Canon**: Accepted truth of your fictional universe.
* **Research**: External factual background with citation.
* **Idea/Trope**: Speculative brainstorms and narrative patterns.
* **Evidence spans**: Character offsets in source text supporting a fact.
* **Dual-verify**: Two independent model checks agree before auto-publish.

---

## Appendix A — Schemas (Concept)

**Proposed Relation (JSON)**

```json
{
  "subject": "Tomoe",
  "predicate": "parent_of | ally_of | enemy_of | teacher_of | member_of | appears_in | located_in | holds | origin_of | inspired_by | embodies",
  "object": "Yoli",
  "time": {"start_iso": null, "end_iso": null, "text": "late Heian", "granularity": "era"},
  "place": "Kyoto",
  "confidence": 0.73,
  "evidence_spans": [[1204, 1268]],
  "source": {"type": "local", "document_id": "doc-17", "section_id": "s-3"},
  "model": {"name": "llama3.1:14b", "mode": "verify"},
  "lane": "canon"
}
```

**Time Expression**

```json
{
  "text": "the winter after the coronation",
  "normalized": {"start_iso": "1450-12", "end_iso": "1451-02", "granularity": "month"},
  "assumptions": ["coronation=1450-11 (doc-37 s2)"],
  "evidence_spans": [[834, 867]],
  "confidence": 0.78
}
```

**Idea Card**

```json
{
  "title": "Storm-pact echoes Illapa rites",
  "pitch": "What if Inari’s storm aspect mirrors Andean Illapa ceremonies, binding winds to blood debt?",
  "seeds": ["research:doc-5:s-12", "research:doc-9:s-3"],
  "risks": ["Chosen One fatigue"],
  "subversions": ["mentor’s betrayal is pragmatic, not evil"],
  "links": [{"type": "inspired_by", "from": "Event:1450-Chimu-Rite", "to": "Legend:Illapa"}],
  "lane": "idea",
  "status": "draft"
}
```

---

## Appendix B — Prompts (Concept)

**Relation Verify (system)**

* *“You verify proposed lore relations from a fictional manuscript. Output **only** JSON matching the provided schema. Include at least one evidence span (start,end char offsets) for each accepted relation. If uncertain, omit.”*

**Temporal Normalize (system)**

* *“Normalize time expressions to ISO with granularity (day|month|year|era). Include original text, evidence spans, and any assumptions.”*

**Trope Mine (system)**

* *“Detect likely narrative tropes present in the scene. Return trope ids/names, confidence, and evidence spans. Do not invent plot facts.”*

---

## Appendix C — Events & Policies

**Events (examples)**

* `document.ingested`, `webdoc.ingested`
* `mentions.proposed`, `relations.proposed`, `events.proposed`
* `proposal.verified`, `proposal.accepted`, `proposal.rejected`, `entity.merged`

**Confidence Policy (defaults)**

* Low-impact edges (`appears_in`, `located_in`) with **≥0.80** may auto-publish
* High-impact edges (lineage/death/world rules) require **dual-verify ≥0.70** or human acceptance
* Any item **without evidence spans** cannot be published

---

### Final Notes

* Keep **lanes** explicit and always visible.
* **Evidence or it didn’t happen**—this keeps canon trustworthy.
* Start **local-first**; add cloud verification only when needed.
* Temporal gives you durable workflows and human gates without duct-tape cron jobs.

When you’re ready, we can turn this concept into a scaffold (folders, stub endpoints, and minimal DDL) you can drop into a repo.

