# src/terminate_existing.py
import asyncio
from temporalio.client import Client

async def main():
    client = await Client.connect("localhost:7233")
    h = client.get_workflow_handle("ingest-test-001")
    await h.terminate("wrong path argument")

if __name__ == "__main__":
    asyncio.run(main())

