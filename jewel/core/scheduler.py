import threading
import time
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

class Scheduler:
    """A tiny DB-backed scheduler that stores tasks in the provided sqlite connection.
    It expects the store to have a `conn` attribute (sqlite3.Connection) and `add_message` method.
    """
    def __init__(self, store, poll_interval: float = 5.0):
        self.store = store
        self.conn = getattr(store, 'conn')
        self.poll_interval = poll_interval
        self._ensure_table()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _ensure_table(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at TEXT,
                payload TEXT,
                done INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self.conn.commit()

    def schedule(self, run_at: datetime, payload: Dict[str, Any]) -> int:
        js = json.dumps(payload)
        cur = self.conn.cursor()
        cur.execute("INSERT INTO tasks (run_at, payload) VALUES (?, ?)", (run_at.isoformat(), js))
        self.conn.commit()
        return cur.lastrowid

    def list_tasks(self, include_done: bool = False) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        if include_done:
            cur.execute("SELECT id, run_at, payload, done, created_at FROM tasks ORDER BY id DESC")
        else:
            cur.execute("SELECT id, run_at, payload, done, created_at FROM tasks WHERE done=0 ORDER BY id DESC")
        rows = cur.fetchall()
        out = []
        for r in rows:
            try:
                payload = json.loads(r[2])
            except Exception:
                payload = {}
            out.append({"id": r[0], "run_at": r[1], "payload": payload, "done": bool(r[3]), "created_at": r[4]})
        return out

    def cancel(self, task_id: int) -> bool:
        cur = self.conn.cursor()
        cur.execute("UPDATE tasks SET done=1 WHERE id=? AND done=0", (task_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def _due_tasks(self) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        cur.execute("SELECT id, run_at, payload FROM tasks WHERE done=0 AND run_at<=? ORDER BY run_at ASC", (now,))
        rows = cur.fetchall()
        out = []
        for r in rows:
            try:
                payload = json.loads(r[2])
            except Exception:
                payload = {}
            out.append({"id": r[0], "run_at": r[1], "payload": payload})
        return out

    def _mark_done(self, task_id: int):
        cur = self.conn.cursor()
        cur.execute("UPDATE tasks SET done=1 WHERE id=?", (task_id,))
        self.conn.commit()

    def _execute_task(self, task: Dict[str, Any]):
        # Minimal safe execution: post a message into the store so UI/users see the reminder.
        payload = task.get('payload') or {}
        text = payload.get('text') or payload.get('message') or str(payload)
        try:
            self.store.add_message('system', f"Reminder: {text}")
        except Exception:
            # best-effort
            try:
                cur = self.conn.cursor()
                cur.execute("INSERT INTO messages (role, content) VALUES (?, ?)", ('system', f"Reminder: {text}"))
                self.conn.commit()
            except Exception:
                pass

    def _run_loop(self):
        while not self._stop.is_set():
            try:
                due = self._due_tasks()
                for t in due:
                    try:
                        self._execute_task(t)
                    except Exception:
                        pass
                    try:
                        self._mark_done(t['id'])
                    except Exception:
                        pass
            except Exception:
                pass
            self._stop.wait(self.poll_interval)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
