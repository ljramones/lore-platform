from pathlib import Path
import re

def _read_txt(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

def _read_md(p: Path) -> str:
    # Keep it simple for MVP; treat as plain text.
    return _read_txt(p)

def _read_docx(p: Path) -> str:
    from docx import Document
    doc = Document(str(p))
    return "\n".join(p.text for p in doc.paragraphs)

def _read_pdf(p: Path) -> str:
    import fitz  # PyMuPDF
    text = []
    with fitz.open(str(p)) as doc:
        for page in doc:
            text.append(page.get_text())
    return "\n".join(text)

def read_file(path: str) -> str:
    p = Path(path)
    ext = p.suffix.lower()
    if ext in [".txt"]: return _read_txt(p)
    if ext in [".md", ".markdown"]: return _read_md(p)
    if ext == ".docx": return _read_docx(p)
    if ext == ".pdf": return _read_pdf(p)
    raise ValueError(f"Unsupported extension: {ext}")

def chunk_text(text: str, max_chars: int = 3000) -> list[dict]:
    # MVP: split on H2-ish headings or blank lines, then size-cap
    chunks = []
    cur = []
    size = 0
    pos = 0
    for para in re.split(r"\n\s*\n", text):
        if size + len(para) > max_chars and cur:
            chunk = "\n\n".join(cur)
            chunks.append({"start": pos - len(chunk), "end": pos, "text": chunk})
            cur, size = [], 0
        cur.append(para)
        size += len(para) + 2
        pos += len(para) + 2
    if cur:
        chunk = "\n\n".join(cur)
        chunks.append({"start": pos - len(chunk), "end": pos, "text": chunk})
    return chunks
