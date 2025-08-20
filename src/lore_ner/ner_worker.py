from datetime import timedelta
from temporalio import workflow, activity
from temporalio.client import Client
from temporalio.worker import Worker
from lore_common.db import init_db, list_sections, add_mentions, Section
import os

# Load spaCy once in the activity process
_nlp = None
def _load_nlp():
    global _nlp
    if _nlp is None:
        import spacy
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            # As a fallback, allow runtime download (not ideal in prod)
            from spacy.cli import download
            download("en_core_web_sm")
            _nlp = spacy.load("en_core_web_sm")
    return _nlp

ALLOWED = {"PERSON","GPE","LOC","ORG","NORP","WORK_OF_ART","EVENT"}

@activity.defn
async def extract_mentions_for_doc(doc_id: int) -> int:
    init_db()
    nlp = _load_nlp()
    sections: list[Section] = list_sections(doc_id)
    out = []
    for sec in sections:
        doc = nlp(sec.text)
        for ent in doc.ents:
            if ent.label_ not in ALLOWED:
                continue
            start_s = int(ent.start_char)
            end_s = int(ent.end_char)
            start_doc = sec.start_char + start_s
            end_doc = sec.start_char + end_s
            out.append({
                "section_id": sec.id,
                "start_s": start_s, "end_s": end_s,
                "start_doc": start_doc, "end_doc": end_doc,
                "surface": ent.text, "label": ent.label_,
            })
    return add_mentions(doc_id, out)

@workflow.defn
class MentionsWorkflow:
    @workflow.run
    async def run(self, doc_id: int) -> int:
        count = await workflow.execute_activity(
            extract_mentions_for_doc, doc_id,
            schedule_to_close_timeout=timedelta(minutes=5),
            start_to_close_timeout=timedelta(minutes=5),
        )
        return count

async def run_worker():
    target = os.environ.get("TEMPORAL_TARGET", "temporal:7233")
    task_queue = os.environ.get("TEMPORAL_TASK_QUEUE", "lore-ner")
    client = await Client.connect(target)
    worker = Worker(client, task_queue=task_queue,
                    workflows=[MentionsWorkflow],
                    activities=[extract_mentions_for_doc])
    await worker.run()
