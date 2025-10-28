import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from .tts_openai import synthesize as unified_synthesize
from ..config import settings


class TTSQueue:
    def __init__(self, base_dir: str = "./data/tts_queue"):
        self.base = Path(base_dir)
        self.jobs = self.base / "jobs"
        self.results = self.base / "results"
        self.running = False
        self._thread: Optional[threading.Thread] = None
        os.makedirs(self.jobs, exist_ok=True)
        os.makedirs(self.results, exist_ok=True)

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)

    def enqueue(self, text: str, voice: str | None = None) -> str:
        jid = uuid.uuid4().hex
        job = {
            "id": jid,
            "text": text,
            "voice": voice,
            "created_at": time.time(),
            "status": "queued",
        }
        jpath = self.jobs / f"{jid}.json"
        with open(jpath, "w", encoding="utf-8") as f:
            json.dump(job, f)
        # ensure a status file exists
        self._write_status(jid, job)
        return jid

    def status_path(self, jid: str) -> Path:
        return self.results / f"{jid}.status.json"

    def result_path(self, jid: str) -> Path:
        return self.results / f"{jid}.mp3"

    def _write_status(self, jid: str, data: dict):
        with open(self.status_path(jid), "w", encoding="utf-8") as f:
            json.dump(data, f)

    def _loop(self):
        # Simple loop that scans jobs folder and processes one job at a time
        while self.running:
            try:
                jobs = sorted(self.jobs.glob("*.json"))
                if not jobs:
                    time.sleep(0.5)
                    continue
                for jp in jobs:
                    try:
                        with open(jp, "r", encoding="utf-8") as f:
                            job = json.load(f)
                    except Exception:
                        jp.unlink(missing_ok=True)
                        continue
                    jid = job.get("id")
                    if not jid:
                        jp.unlink(missing_ok=True)
                        continue
                    # mark processing
                    job["status"] = "processing"
                    job["started_at"] = time.time()
                    self._write_status(jid, job)
                    out = self.result_path(jid)
                    try:
                        # attempt to synthesize; reuse unified synth which handles OpenAI/Azure fallback
                        unified_synthesize(job.get("text", ""), outfile=str(out), voice=job.get("voice"))
                        job["status"] = "done"
                        job["result"] = str(out)
                        job["finished_at"] = time.time()
                    except Exception as e:
                        job["status"] = "error"
                        job["error"] = str(e)
                        job["finished_at"] = time.time()
                    # write status and remove job file
                    self._write_status(jid, job)
                    try:
                        jp.unlink(missing_ok=True)
                    except Exception:
                        pass
                    # continue to next job
                # small sleep to avoid tight loop
                time.sleep(0.2)
            except Exception:
                time.sleep(1)


queue_manager = TTSQueue()
