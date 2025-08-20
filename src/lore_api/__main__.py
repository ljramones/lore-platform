from fastapi import FastAPI, HTTPException
from typing import Optional
from sqlmodel import select
from lore_common.db import init_db, get_session, Document, Section, Mention

app = FastAPI(title="Lore API")

@app.on_event("startup")
def _startup():
    init_db()

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/documents")
def list_documents():
    with get_session() as s:
        rows = s.exec(select(Document).order_by(Document.created_at.desc())).all()
        return rows

@app.get("/documents/{doc_id}")
def get_document(doc_id: int):
    with get_session() as s:
        d = s.get(Document, doc_id)
        if not d:
            raise HTTPException(404, "Not found")
        return d

@app.get("/documents/{doc_id}/sections")
def list_sections(doc_id: int):
    with get_session() as s:
        rows = s.exec(
            select(Section)
            .where(Section.document_id == doc_id)
            .order_by(Section.idx)
        ).all()
        return rows

@app.get("/documents/{doc_id}/mentions")
def list_doc_mentions(
    doc_id: int, label: Optional[str] = None, q: Optional[str] = None, limit: int = 200
):
    with get_session() as s:
        stmt = select(Mention).where(Mention.document_id == doc_id)
        if label:
            stmt = stmt.where(Mention.label == label)
        if q:
            stmt = stmt.where(Mention.surface.ilike(f"%{q}%"))
        rows = s.exec(stmt.limit(limit)).all()
        return rows

@app.get("/mentions")
def list_mentions(label: Optional[str] = None, q: Optional[str] = None, limit: int = 200):
    # Join to show doc title + section idx with each mention
    with get_session() as s:
        stmt = (
            select(Mention, Document.title, Section.idx)
            .join(Document, Mention.document_id == Document.id)
            .join(Section, Mention.section_id == Section.id)
        )
        if label:
            stmt = stmt.where(Mention.label == label)
        if q:
            stmt = stmt.where(Mention.surface.ilike(f"%{q}%"))
        result = s.exec(stmt.limit(limit)).all()
        return [
            {"mention": m, "doc_title": title, "section_idx": sec_idx}
            for (m, title, sec_idx) in result
        ]
