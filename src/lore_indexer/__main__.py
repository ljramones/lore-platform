# Indexes DB sections into Chroma using REST + sentence-transformers
import os, time,logging, requests
from typing import List, Dict
from sentence_transformers import SentenceTransformer
from sqlmodel import select
from lore_common.db import get_session, Document, Section

LOG = logging.getLogger("lore_indexer")
logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))

CHROMA_HOST = os.getenv("CHROMA_HOST", "chroma")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
COLLECTION   = os.getenv("CHROMA_COLLECTION", "lore-sections")
EMBED_MODEL  = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
BATCH_SIZE   = int(os.getenv("BATCH_SIZE", "64"))
INTERVAL_SEC = int(os.getenv("INDEX_INTERVAL", "30"))

def _api_base() -> str:
    base = f"http://{CHROMA_HOST}:{CHROMA_PORT}"
    # prefer v2 if available
    try:
        r = requests.get(f"{base}/api/v2/healthcheck", timeout=3)
        if r.ok:
            return f"{base}/api/v2"
    except Exception:
        pass
    return f"{base}/api/v1"

def _get_or_create_collection_id(base: str, name: str) -> str:
    # try get-by-name
    r = requests.get(f"{base}/collections", params={"name": name}, timeout=5)
    if r.ok and r.json().get("name") == name and "id" in r.json():
        return r.json()["id"]
    # create
    payload = {"name": name, "metadata": {"hnsw:space": "cosine"}}
    r = requests.post(f"{base}/collections", json=payload, timeout=10)
    r.raise_for_status()
    return r.json()["id"]

def _already_present_ids(base: str, col_id: str, ids: List[str]) -> set:
    # ask Chroma for the subset of ids that exist
    # v2 supports POST /collections/{id}/get with {"ids":[...]}
    r = requests.post(f"{base}/collections/{col_id}/get", json={"ids": ids}, timeout=30)
    if not r.ok:
        return set()
    data = r.json()
    return set(data.get("ids", []) or [])

def _add_or_update(base: str, col_id: str, docs: List[str], ids: List[str], metas: List[Dict], embeds: List[List[float]]) -> None:
    # Try add first
    payload = {"documents": docs, "ids": ids, "metadatas": metas, "embeddings": embeds}
    resp = requests.post(f"{base}/collections/{col_id}/add", json=payload, timeout=120)
    if resp.ok:
        return
    # Fallback to update (in case of dup IDs)
    requests.post(f"{base}/collections/{col_id}/update", json=payload, timeout=120).raise_for_status()

def _chunks(n: int, seq):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

def index_once():
    base = _api_base()
    col_id = _get_or_create_collection_id(base, COLLECTION)
    LOG.info("Using Chroma %s collection id=%s", COLLECTION, col_id)

    # load sections + doc metadata
    with get_session() as s:
        rows = s.exec(
            select(Section, Document.title)
            .join(Document, Section.document_id == Document.id)
            .order_by(Section.id)
        ).all()

    if not rows:
        LOG.info("No sections found in DB")
        return

    # build job lists
    ids, texts, metas = [], [], []
    for sec, title in rows:
        sid = f"sec:{sec.id}"
        ids.append(sid)
        texts.append(sec.text)
        metas.append({
            "document_id": sec.document_id,
            "document_title": title,
            "section_id": sec.id,
            "section_idx": sec.idx,
        })

    # skip already-present
    present = _already_present_ids(base, col_id, ids)
    todo = [(i,t,m) for i,t,m in zip(ids, texts, metas) if i not in present]
    LOG.info("Sections total=%d present=%d to_index=%d", len(ids), len(present), len(todo))
    if not todo:
        return

    # embed + upsert in batches
    model = SentenceTransformer(EMBED_MODEL)
    for batch in _chunks(BATCH_SIZE, todo):
        b_ids  = [b[0] for b in batch]
        b_text = [b[1] for b in batch]
        b_meta = [b[2] for b in batch]
        embeds = model.encode(b_text, normalize_embeddings=True).tolist()
        _add_or_update(base, col_id, b_text, b_ids, b_meta, embeds)
        LOG.info("Indexed %d/%d", len(b_ids), len(todo))

def main():
    LOG.info("Indexer using %s on collection=%s every %ss", EMBED_MODEL, COLLECTION, INTERVAL_SEC)
    while True:
        try:
            index_once()
        except Exception as e:
            LOG.exception("Indexing error: %s", e)
        time.sleep(INTERVAL_SEC)

if __name__ == "__main__":
    main()
