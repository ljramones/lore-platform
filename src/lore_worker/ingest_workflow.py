# ingest_workflow.py
from temporalio import workflow

from temporalio.common import RetryPolicy

from datetime import timedelta   # <-- add this at top

@workflow.defn
class IngestWorkflow:
    @workflow.run
    async def run(self, path: str) -> int:
        return await workflow.execute_activity(
            "parse_and_store",
            path,
            schedule_to_close_timeout=timedelta(minutes=5),
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
