import asyncio
import os
from temporalio.client import Client
from temporalio.worker import Worker
from .ingest_workflow import IngestWorkflow


def _resolve(addr_vars, default):
    for v in addr_vars:
        val = os.getenv(v)
        if val:
            return val
    return default


async def run_worker() -> None:
    target = _resolve(
        ["TEMPORAL_ADDRESS", "TEMPORAL_TARGET", "TARGET"],
        "host.docker.internal:7233",
    )
    task_queue = _resolve(["TEMPORAL_TASK_QUEUE", "TASK_QUEUE"], "lore-ingest")

    if "://" in target:
        raise ValueError(f"TEMPORAL address must be 'host:port' (no scheme). Got: {target!r}")

    print(f"[lore-worker] Connecting to Temporal at {target} on task queue '{task_queue}'", flush=True)

    client = await Client.connect(target)

    # Import activities here (host process), NOT at module top-level
    from . import activities

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[IngestWorkflow],
        activities=[activities.parse_and_store],
    ):
        # keep the worker running
        await asyncio.Event().wait()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
