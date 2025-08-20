# test/test_db.py
import os
import sys
import importlib

def test_upsert_and_cascade(tmp_path, monkeypatch):
    # 1) Point the DB to a fresh temp SQLite file BEFORE importing the module
    db_path = tmp_path / "lore.db"
    monkeypatch.setenv("DATABASE_URL", "")                 # force sqlite fallback
    monkeypatch.setenv("LORE_DB_PATH", str(db_path))       # set sqlite file path

    # 2) Ensure a clean import (dispose old engine if present)
    if "lore_common.db" in sys.modules:
        try:
            mod = sys.modules["lore_common.db"]
            getattr(mod, "engine", None) and mod.engine.dispose()
        except Exception:
            pass
        del sys.modules["lore_common.db"]

    # 3) Import once (no reloads => no double-def tables)
    import lore_common.db as db
    importlib.invalidate_caches()

    # 4) Create schema
    db.init_db()

    # 5) First insert
    doc_id1 = db.add_document_with_sections("/app/inbox/test.txt", "test.txt", ["alpha", "beta"])
    with db.get_session() as s:
        docs = s.exec(db.select(db.Document)).all()
        secs = s.exec(db.select(db.Section).where(db.Section.document_id == doc_id1)).all()
    assert len(docs) == 1
    assert docs[0].path == "/app/inbox/test.txt"
    assert [sec.text for sec in secs] == ["alpha", "beta"]

    # 6) Re-ingest same path with different sections → replaces sections (idempotent)
    doc_id2 = db.add_document_with_sections("/app/inbox/test.txt", "test.txt", ["only-one"])
    with db.get_session() as s:
        docs = s.exec(db.select(db.Document)).all()
        secs = s.exec(db.select(db.Section).where(db.Section.document_id == doc_id2)).all()
    assert len(docs) == 1               # still a single document (same path)
    assert [sec.text for sec in secs] == ["only-one"]

    # 7) Cascade delete: removing Document removes its Sections
    with db.get_session() as s:
        d = s.get(db.Document, doc_id2)
        s.delete(d)
        s.commit()
        remaining = s.exec(db.select(db.Section)).all()
    assert remaining == []
