# src/lore_worker/cli.py
import os, sys, asyncio, uuid
from temporalio.client import Client
from temporalio.common import RetryPolicy

async def main(path: str):
    client = await Client.connect(os.getenv("TEMPORAL_ADDRESS", "localhost:7233"))
    wf_id = f"ingest-{uuid.uuid4()}"
    res = await client.execute_workflow(
        "IngestWorkflow",
        path,
        id=wf_id,
        task_queue="lore-ingest",
        retry_policy=RetryPolicy(maximum_attempts=3),
    )
    print(res)

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
