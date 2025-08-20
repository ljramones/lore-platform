from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Any, Dict, Optional
import os, requests
from sentence_transformers import SentenceTransformer

CHROMA_HOST = os.getenv("CHROMA_HOST", "chroma")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
COLLECTION  = os.getenv("CHROMA_COLLECTION", "lore-sections")
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

app = FastAPI(title="Lore Search")

def _api_base() -> str:
    base = f"http://{CHROMA_HOST}:{CHROMA_PORT}"
    try:
        r = requests.get(f"{base}/api/v2/healthcheck", timeout=3)
        if r.ok:
            return f"{base}/api/v2"
    except Exception:
        pass
    return f"{base}/api/v1"

def _ensure_collection_id(base: str, name: str) -> str:
    r = requests.get(f"{base}/collections", params={"name": name}, timeout=5)
    if r.ok and r.json().get("id"):
        return r.json()["id"]
    raise HTTPException(500, f"Collection {name!r} not found in Chroma")

_model = None
def _model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL)
    return _model

@app.get("/healthz")
def healthz():
    base = _api_base()
    return {"ok": True, "chroma": base, "collection": COLLECTION}

@app.get("/search")
def search(q: str = Query(..., min_length=1), k: int = 5):
    base = _api_base()
    col_id = _ensure_collection_id(base, COLLECTION)
    emb = _model().encode([q], normalize_embeddings=True).tolist()

    payload = {"query_embeddings": emb, "n_results": k, "include": ["documents","metadatas","distances","ids"]}
    r = requests.post(f"{base}/collections/{col_id}/query", json=payload, timeout=60)
    if not r.ok:
        raise HTTPException(500, f"Chroma query failed: {r.text}")

    data = r.json()
    # unwrap single query
    out = []
    for i in range(len(data.get("ids",[[]])[0])):
        out.append({
            "id":        data["ids"][0][i],
            "distance":  data["distances"][0][i] if "distances" in data else None,
            "text":      data["documents"][0][i],
            "metadata":  data["metadatas"][0][i],
        })
    return {"query": q, "k": k, "results": out}
