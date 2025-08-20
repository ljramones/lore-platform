# src/lore_common/db.py
import json
import re
import os
from pathlib import Path
from typing import Iterable, Optional, List, Union, Dict
from datetime import datetime

from sqlalchemy import UniqueConstraint, event
from sqlmodel import SQLModel, Field, Relationship, Session, create_engine, select

# ---------- New: core canon entities/aliases ----------
class Entity(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    type: str = Field(index=True)  # 'character'|'place'|'artifact'|'faction'|'legend'|'motif'
    display_name: str = Field(index=True)
    attrs_json: str = Field(default="{}")     # JSON text
    notes: str = Field(default="")
    lane: str = Field(default="canon", index=True)  # keep 'canon' for now


class Alias(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("entity_id", "name", name="uix_alias_entity_name"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    entity_id: int = Field(foreign_key="entity.id", index=True)
    name: str = Field(index=True)

# ---------- New: proposals for relations ----------
# For MVP, object can be either another entity OR a section (for appears_in).
class ProposedRelation(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "subj_entity_id", "predicate", "obj_entity_id", "obj_kind", "obj_ref_id",
            "document_id", "section_id", name="uix_proposed_rel_dedupe"
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # subject
    subj_entity_id: Optional[int] = Field(default=None, index=True)

    # predicate (controlled vocab, stored as string)
    predicate: str = Field(index=True)  # e.g., 'appears_in', 'located_in'

    # object (one of: entity | section)
    obj_kind: str = Field(index=True)   # 'entity' | 'section' | 'place'
    obj_entity_id: Optional[int] = Field(default=None, index=True)
    obj_ref_id: Optional[int] = Field(default=None, index=True)  # section_id when obj_kind='section'

    # evidence / provenance
    document_id: int = Field(index=True)
    section_id: int = Field(index=True)
    evidence_json: str = Field(default="[]")  # JSON text: list of [start,end] offsets
    confidence: float = Field(default=0.75)
    lane: str = Field(default="canon", index=True)
    status: str = Field(default="pending", index=True)  # 'pending'|'accepted'|'rejected'
    reasons: str = Field(default="")  # freeform note for why proposed / rule name

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


# --- util: coarse label→entity.type mapping for MVP
def _entity_type_from_label(label: str) -> str:
    lab = (label or "").upper()
    if lab in ("GPE", "LOC"):
        return "place"
    if lab in ("PERSON",):
        return "character"
    if lab in ("ORG",):
        return "faction"
    # fallback:
    return "legend"  # neutral-ish bucket for unknowns

# --- util: normalize surface form (very basic; can swap later for fuzzy)
def _canon_name(surface: str) -> str:
    s = surface.strip()
    s = re.sub(r"\s+", " ", s)
    return s

def resolve_or_create_entity(session: Session, surface: str, label: str) -> Entity:
    name = _canon_name(surface)
    etype = _entity_type_from_label(label)
    # try Alias hit first
    alias = session.exec(select(Alias).where(Alias.name == name)).first()
    if alias:
        ent = session.get(Entity, alias.entity_id)
        if ent:
            return ent

    # else try the exact entity display_name
    ent = session.exec(
        select(Entity).where(Entity.display_name == name).where(Entity.type == etype)
    ).first()
    if ent:
        # ensure alias exists
        if not session.exec(
            select(Alias).where(Alias.entity_id == ent.id, Alias.name == name)
        ).first():
            session.add(Alias(entity_id=ent.id, name=name))
            session.flush()
        return ent

    # create new
    ent = Entity(type=etype, display_name=name)
    session.add(ent)
    session.flush()
    session.add(Alias(entity_id=ent.id, name=name))
    session.flush()
    return ent

# --- propose 'appears_in' for every mention (entity -> section)
def propose_appears_in_for_doc(doc_id: int, min_conf: float = 0.80, rule_name: str = "rule:appears_in") -> int:
    count = 0
    with get_session() as s:
        mentions = list(s.exec(select(Mention).where(Mention.document_id == doc_id)))
        if not mentions:
            return 0

        # cache sections to ensure they exist
        secs = {sec.id: sec for sec in s.exec(select(Section).where(Section.document_id == doc_id))}

        for m in mentions:
            ent = resolve_or_create_entity(s, m.surface, m.label)
            evidence = [[m.start_char_section, m.end_char_section]]
            pr = ProposedRelation(
                subj_entity_id=ent.id,
                predicate="appears_in",
                obj_kind="section",
                obj_ref_id=m.section_id,
                document_id=doc_id,
                section_id=m.section_id,
                evidence_json=json.dumps(evidence),
                confidence=max(min_conf, 0.80),
                reasons=rule_name,
            )
            # dedupe via unique index; catch on commit
            s.add(pr)
            try:
                s.commit()
                count += 1
            except Exception:
                s.rollback()
                # unique collision → ignore
        return count

# --- propose 'located_in' (entity -> place) when a PERSON/ORG appears near a GPE/LOC in same section
def propose_located_in_for_doc(doc_id: int, window_chars: int = 200, base_conf: float = 0.70, rule_name: str = "rule:located_in_window") -> int:
    count = 0
    with get_session() as s:
        # group mentions per section
        sec_to_mentions: Dict[int, List[Mention]] = {}
        for m in s.exec(select(Mention).where(Mention.document_id == doc_id)):
            sec_to_mentions.setdefault(m.section_id, []).append(m)

        for section_id, mlist in sec_to_mentions.items():
            # split into candidates
            persons = [m for m in mlist if _entity_type_from_label(m.label) in ("character", "faction")]
            places  = [m for m in mlist if _entity_type_from_label(m.label) == "place"]
            if not persons or not places:
                continue

            for p in persons:
                for q in places:
                    # proximity check within the same section
                    if abs(p.start_char_section - q.start_char_section) <= window_chars:
                        subj = resolve_or_create_entity(s, p.surface, p.label)
                        obj  = resolve_or_create_entity(s, q.surface, q.label)
                        evidence = [
                            [min(p.start_char_section, q.start_char_section),
                             max(p.end_char_section, q.end_char_section)]
                        ]
                        pr = ProposedRelation(
                            subj_entity_id=subj.id,
                            predicate="located_in",
                            obj_kind="entity",
                            obj_entity_id=obj.id,
                            obj_ref_id=None,
                            document_id=doc_id,
                            section_id=section_id,
                            evidence_json=json.dumps(evidence),
                            confidence=base_conf,
                            reasons=rule_name,
                        )
                        s.add(pr)
                        try:
                            s.commit()
                            count += 1
                        except Exception:
                            s.rollback()
        return count

# --- convenience: batch proposal driver for a document
def propose_relations_for_doc(doc_id: int) -> Dict[str, int]:
    return {
        "appears_in": propose_appears_in_for_doc(doc_id),
        "located_in": propose_located_in_for_doc(doc_id),
    }

# --- fetch pending proposals (for worker / API / review)
def pending_relations(limit: int = 100, predicates: Optional[List[str]] = None) -> List[ProposedRelation]:
    with get_session() as s:
        stmt = select(ProposedRelation).where(ProposedRelation.status == "pending")
        if predicates:
            stmt = stmt.where(ProposedRelation.predicate.in_(predicates))  # type: ignore[attr-defined]
        stmt = stmt.order_by(ProposedRelation.id).limit(limit)
        return list(s.exec(stmt))
