# src/kick_off.py
import os, asyncio, uuid
from temporalio.client import Client
from temporalio.common import RetryPolicy

async def main():
    client = await Client.connect(os.getenv("TEMPORAL_ADDRESS", "localhost:7233"))
    wf_id = f"ingest-{uuid.uuid4()}"
    result = await client.execute_workflow(
        "IngestWorkflow",
        "/app/inbox/test.txt",       # must exist inside the worker container
        id=wf_id,
        task_queue="lore-ingest",
        retry_policy=RetryPolicy(maximum_attempts=3),
    )
    print("Doc ID:", result)

if __name__ == "__main__":
    asyncio.run(main())
