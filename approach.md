heck yes — “Lore-a-pedia” is the perfect framing 🎉
Here’s a tight, high-level package you can build from right away.

# Quick architecture diagram (Mermaid)

```mermaid
flowchart LR
  subgraph Agents/Orchestrator
    A1[Strands Agents] -->|Workflows| TMP[Temporal]
    MEM[Mem0 (short-term memory)]
    A1 --- MEM
  end

  subgraph MCP Tools (stateless)
    W1[Doc Watcher] --> P1[Parser]
    H1[Web Harvester] --> CLEAN[Cleaner/Chunker]
    X1[NER + Coref]
    X2[Relation & Timeline Extractor]
    V1[Verifier (GPT-5/Claude/Gemini)]
    T1[Trope Miner]
  end

  subgraph Services (stateful APIs)
    RQ[Review Queue API]
    LQ[Lore Query API]
    RAG[RAG API]
    UI[Lore Console (UI)]
  end

  subgraph Persistence
    DB1[(Canon DB)]
    DB2[(Research DB)]
    DB3[(Idea/Trope DB)]
    VEC[(Vector Store)]
    BLOB[(Blob Store)]
  end

  TMP --> W1 & H1 & X1 & X2 & V1 & T1
  P1 --> DB2 & DB1
  CLEAN --> DB2 & VEC
  X1 --> RQ
  X2 --> RQ
  V1 --> RQ
  RQ --> DB1
  T1 --> DB3
  RAG <---> DB2 & VEC
  LQ --> DB1
  UI <---> RQ & LQ & RAG
  H1 --> BLOB
```

# Minimal service registry

| Component          | Kind         | Responsibility                                 | Depends on                    |
| ------------------ | ------------ | ---------------------------------------------- | ----------------------------- |
| Doc Watcher        | MCP          | Watch folder → parse (PDF/DOCX/MD) → sections  | Temporal, Canon/Research DB   |
| Web Harvester      | MCP          | Curated search/fetch → clean → chunk           | Temporal, Research DB, Vector |
| NER+Coref          | MCP          | Mentions & clusters → proposals                | Canon/Research DB             |
| Relation Extractor | MCP          | Edges/events/timeexpr → proposals              | Canon DB                      |
| Verifier           | MCP          | Evidence-required JSON via GPT-5/Claude/Gemini | Providers, Canon DB           |
| Trope Miner        | MCP          | Detect tropes; link candidates                 | Idea/Trope DB                 |
| Review Queue API   | Service      | Accept/reject/merge; policy checks             | Canon DB                      |
| Lore Query API     | Service      | Cards, timelines, graphs                       | Canon DB                      |
| RAG API            | Service      | Hybrid retrieval (keyword+vector)              | Research DB, Vector           |
| Lore Console       | UI           | Human-in-the-loop review & browse              | All services                  |
| Temporal           | Orchestrator | Durable workflows, retries, signals            | —                             |
| Persistence set    | Infra        | DBs, vectors, blobs                            | —                             |

# Storage choices (start simple, level up later)

* **Canon / Research / Idea DB:** start **SQLite (FTS5)** → upgrade to **Postgres** (+ **pgvector**) when multi-user or bigger corpora.
* **Vector store:** start **Chroma** → upgrade to **Qdrant** *or* **pgvector** for one-DB simplicity.
* **Blob store:** start local filesystem → **MinIO** (S3-compatible) when you want portability/backups.

# Start-here checklist (keeps it high-level)

1. **Repos & layout**

```
/lore-platform
  /services {lore-query-api, review-queue-api, rag-api}
  /mcp      {doc-watcher, web-harvester, ner-coref, relation-extractor, verifier, trope-miner}
  /infra    {docker-compose.yml, .env}
  /db       {canon.sqlite, research.sqlite, idea.sqlite}
  /ui       {lore-console}
```

2. **Compose up infra (local-first)**

* SQLite files (bind mounts), **Chroma**, optional **MinIO**, **Temporal** (single worker).

3. **Wire the happy path**

* `Doc Watcher → Parser → Canon/Research DB`
* `NER+Coref → Review Queue (proposals)`
* `Review accept → Canon`
* `Lore Query: /entity/:id, /timeline/:id`

4. **Add RAG lane**

* `Web Harvester → Research DB + Vector → RAG API`

5. **Add verification gates**

* Verifier MCP with strict JSON schema & evidence spans; dual-verify only for high-impact facts.

# A few operating principles

* **Three lanes, always labeled:** `canon`, `research`, `idea`. Only canon fuels timelines/graphs by default.
* **Evidence or it didn’t happen:** every relation/event stores source + char-offset spans.
* **Local-first, escalate selectively:** rules/NER handle the bulk; cloud models only for low-confidence or conflicts.
* **Human is editor-in-chief:** nothing becomes canon without an explicit accept.

If you want me to, I can drop a compact **compose file + stubbed endpoints and schemas** next—just say the word “scaffold.”

