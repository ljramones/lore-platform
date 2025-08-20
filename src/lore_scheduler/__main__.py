import asyncio, time, os
from temporalio.client import Client
from lore_common.db import init_db, docs_without_mentions

INTERVAL = int(os.environ.get("SCHED_INTERVAL", "5"))
TARGET = os.environ.get("TEMPORAL_TARGET", "temporal:7233")
QUEUE = os.environ.get("TEMPORAL_TASK_QUEUE", "lore-ner")

async def loop():
    init_db()
    client = await Client.connect(TARGET)
    print(f"Scheduler watching for docs without mentions every {INTERVAL}s…")
    while True:
        try:
            for doc_id in docs_without_mentions(limit=20):
                wf_id = f"mentions-{doc_id}-{int(time.time())}"
                await client.start_workflow("MentionsWorkflow", doc_id, id=wf_id, task_queue=QUEUE)
                print(f"Started MentionsWorkflow for doc {doc_id}")
        except Exception as e:
            print("Scheduler error:", e)
        time.sleep(INTERVAL)

if __name__ == "__main__":
    asyncio.run(loop())
