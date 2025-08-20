from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from temporalio.client import Client
from pathlib import Path
import asyncio, time, os


INBOX = os.environ.get("INBOX_DIR", "/app/inbox")
TASK_QUEUE = os.environ.get("TEMPORAL_TASK_QUEUE", "lore-ingest")
TARGET = os.environ.get("TEMPORAL_TARGET", "temporal:7233")

class Handler(FileSystemEventHandler):
    def __init__(self, client):
        self.client = client

    def on_created(self, event):
        if event.is_directory: return
        p = Path(event.src_path)
        if p.suffix.lower() not in {".pdf",".docx",".md",".txt"}: return
        asyncio.run(self.start_ingest(str(p)))

    async def start_ingest(self, path: str):
        wf = await self.client.start_workflow(
            "IngestWorkflow", path, id=f"ingest-{Path(path).name}-{int(time.time())}",
            task_queue=TASK_QUEUE
        )
        print(f"Started workflow {wf.id} for {path}")

async def main():
    client = await Client.connect(TARGET)
    obs = Observer()
    h = Handler(client)
    obs.schedule(h, INBOX, recursive=False)
    obs.start()
    print(f"Watching {INBOX} for new files...")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()

if __name__ == "__main__":
    asyncio.run(main())
