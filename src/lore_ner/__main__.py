# src/lore_ner/__main__.py
import os, time
import spacy
from lore_common.db import init_db, docs_without_mentions, list_sections, add_mentions

POLL_SECS = float(os.getenv("NER_POLL_INTERVAL", "10"))
MODEL = os.getenv("SPACY_MODEL", "en_core_web_sm")

def run():
    init_db()
    nlp = spacy.load(MODEL)
    print(f"[lore-ner] ready (model={MODEL}) – polling every {POLL_SECS}s", flush=True)

    while True:
        try:
            doc_ids = docs_without_mentions(limit=5)
            if not doc_ids:
                time.sleep(POLL_SECS)
                continue

            for doc_id in doc_ids:
                mentions = []
                for sec in list_sections(doc_id):
                    doc = nlp(sec.text)
                    for ent in doc.ents:
                        mentions.append({
                            "section_id": sec.id,
                            "start_s": ent.start_char,
                            "end_s": ent.end_char,
                            "start_doc": sec.start_char + ent.start_char,
                            "end_doc": sec.start_char + ent.end_char,
                            "surface": ent.text,
                            "label": ent.label_,
                        })
                added = add_mentions(doc_id, mentions)
                print(f"[lore-ner] doc {doc_id}: added {added} mentions", flush=True)

        except Exception as e:
            print("[lore-ner] error:", e, flush=True)

        time.sleep(POLL_SECS)

if __name__ == "__main__":
    run()
