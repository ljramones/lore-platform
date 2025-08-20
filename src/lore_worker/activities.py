from pathlib import Path
from temporalio import activity

from lore_common.db import init_db, add_document_with_sections
from lore_common.parse import read_file, chunk_text

def _normalize_sections(sections_iter):
    """Accepts list[str] or list[dict], returns list[str]."""
    norm = []
    for s in sections_iter:
        if isinstance(s, dict):           # {'start':..., 'end':..., 'text':...}
            s = s.get("text", "")
        elif not isinstance(s, str):      # fallback: stringify anything else
            s = str(s)
        norm.append(s)
    return norm

@activity.defn
async def parse_and_store(path: str) -> int:
    init_db()
    text = read_file(path)
    sections_raw = chunk_text(text)
    sections = _normalize_sections(sections_raw)

    title = Path(path).name
    return add_document_with_sections(path, title, sections)
