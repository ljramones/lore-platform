# src/lore_common/db.py
import os
from pathlib import Path
from typing import Iterable, Optional

from sqlalchemy import event
from sqlmodel import SQLModel, Field, Relationship, Session, create_engine, select

# ---------- DB URL / engine ----------
DATABASE_URL = os.getenv("DATABASE_URL")
DB_PATH: Optional[str] = None
if not DATABASE_URL:
    # default to sqlite file; override with LORE_DB_PATH
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
    # Use Field(unique=True, index=True). Do NOT pass sa_column here.
    path: str = Field(unique=True, index=True)
    title: str
    sections: list["Section"] = Relationship(
        back_populates="document",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

class Section(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="document.id")
    index: int
    text: str
    document: Optional[Document] = Relationship(back_populates="sections")

# ---------- Helpers ----------
def init_db() -> None:
    # ensure dir for sqlite exists
    if DB_PATH:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)

def get_session() -> Session:
    return Session(engine)

def add_document_with_sections(path: str, title: str, sections: Iterable[str]) -> int:
    """
    Idempotent insert: upsert Document by path, replacing all Sections.
    Returns the (new) document ID.
    """
    with get_session() as session:
        existing = session.exec(select(Document).where(Document.path == path)).first()
        if existing:
            session.delete(existing)
            session.flush()

        doc = Document(path=path, title=title)
        session.add(doc)
        session.flush()  # assigns doc.id

        for idx, text in enumerate(sections):
            session.add(Section(document_id=doc.id, index=idx, text=text))

        session.commit()
        return int(doc.id)  # type: ignore[arg-type]
