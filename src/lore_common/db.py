# src/lore_common/db.py

import os
from pathlib import Path
from typing import Iterable, Optional, List, Union, Dict
from datetime import datetime

from sqlalchemy import UniqueConstraint, event
from sqlmodel import SQLModel, Field, Relationship, Session, create_engine, select

# ---------- DB URL / engine ----------
DATABASE_URL = os.getenv("DATABASE_URL")
DB_PATH: Optional[str] = None
if not DATABASE_URL:
    DB_PATH = os.getenv("LORE_DB_PATH", "/app/data/lore.db")
    DATABASE_URL = f"sqlite:///{DB_PATH}"

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)

# SQLite QoL: enable FK + WAL
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON;")
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.close()

# ---------- Models ----------
class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    path: str = Field(index=True, unique=True)
    title: str
    source_type: str = Field(default="local", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Plain SQLModel relationship typing (no Mapped[])
    sections: List["Section"] = Relationship(
        back_populates="document",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "Section.idx"},
    )


class Section(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("document_id", "idx", name="uix_section_doc_idx"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="document.id", index=True)
    idx: int = Field(index=True)               # 0..N within a document
    start_char: int = Field(default=0)         # absolute char offset in doc
    end_char: int = Field(default=0)
    heading: str = Field(default="")
    text: str

    document: Optional[Document] = Relationship(back_populates="sections")


class Mention(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(index=True)
    section_id: int = Field(index=True)
    start_char_doc: int
    end_char_doc: int
    start_char_section: int
    end_char_section: int
    surface: str
    label: str  # PERSON, GPE, ORG, etc.

# ---------- Helpers ----------
def init_db() -> None:
    if DB_PATH:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)

def get_session() -> Session:
    return Session(engine)

def _normalize_sections(
    sections: Iterable[Union[str, Dict[str, Union[str, int]]]]
) -> List[Dict[str, Union[str, int]]]:
    out: List[Dict[str, Union[str, int]]] = []
    for item in sections:
        if isinstance(item, str):
            out.append({"text": item, "heading": "", "start": -1, "end": -1})
        else:
            d = dict(item)
            if "text" not in d or not isinstance(d["text"], str):
                raise ValueError("Each section must have a 'text' string")
            d.setdefault("heading", "")
            d.setdefault("start", -1)
            d.setdefault("end", -1)
            out.append(d)

    pos = 0
    for d in out:
        start = int(d.get("start", -1))  # type: ignore[arg-type]
        end = int(d.get("end", -1))      # type: ignore[arg-type]
        txt = d["text"]                  # type: ignore[assignment]
        if start < 0 or end < 0:
            start = pos
            end = pos + len(txt)         # type: ignore[arg-type]
        d["start"] = start
        d["end"] = end
        pos = end
    return out

def add_document_with_sections(
    path: str, title: str, sections: Iterable[Union[str, Dict[str, Union[str, int]]]]
) -> int:
    normalized = _normalize_sections(sections)
    with get_session() as session:
        existing = session.exec(select(Document).where(Document.path == path)).first()
        if existing:
            session.delete(existing)
            session.flush()

        doc = Document(path=path, title=title, source_type="local")
        session.add(doc)
        session.flush()  # assigns doc.id

        for idx, sec in enumerate(normalized):
            session.add(Section(
                document_id=doc.id,          # type: ignore[arg-type]
                idx=idx,
                start_char=int(sec["start"]),  # type: ignore[index]
                end_char=int(sec["end"]),      # type: ignore[index]
                heading=str(sec.get("heading", "")),
                text=str(sec["text"]),         # type: ignore[index]
            ))
        session.commit()
        return int(doc.id)  # type: ignore[arg-type]

def list_sections(doc_id: int) -> List[Section]:
    with get_session() as s:
        return list(
            s.exec(
                select(Section)
                .where(Section.document_id == doc_id)
                .order_by(Section.idx)
            )
        )

def add_mentions(doc_id: int, mentions: List[Dict[str, Union[int, str]]]) -> int:
    with get_session() as s:
        for m in mentions:
            s.add(Mention(
                document_id=doc_id,
                section_id=int(m["section_id"]),
                start_char_doc=int(m["start_doc"]),
                end_char_doc=int(m["end_doc"]),
                start_char_section=int(m["start_s"]),
                end_char_section=int(m["end_s"]),
                surface=str(m["surface"]),
                label=str(m["label"]),
            ))
        s.commit()
        return len(mentions)

def docs_without_mentions(limit: int = 50) -> list[int]:
    """Return document IDs that have zero mention rows."""
    with get_session() as s:
        subq = select(Mention.id).where(Mention.document_id == Document.id).exists()
        stmt = (
            select(Document.id)
            .where(~subq)
            .order_by(Document.created_at.desc())
            .limit(limit)
        )
        # In your versions, exec returns ScalarResult (iterable of ints) already
        return list(s.exec(stmt))
