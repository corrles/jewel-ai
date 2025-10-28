from typing import Dict
from ..memory.sqlite_store import SqliteStore
from ..config import settings
import os, datetime

_STORE = SqliteStore(settings.db_path)

NOTES_FILE = "./data/notes.txt"
os.makedirs("./data", exist_ok=True)

def _note(arg: str) -> str:
    if not arg.strip():
        return "Usage: /note <text>"
    with open(NOTES_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {arg}\n")
    return "Saved to notes."

def _remember(arg: str) -> str:
    # store a memory key-value like: birthday=June 1
    if "=" not in arg:
        return "Usage: /remember key=value"
    k, v = [x.strip() for x in arg.split("=", 1)]
    _STORE.set(k, v)
    return f"Remembered {k}."

def _recall(arg: str) -> str:
    v = _STORE.get(arg.strip())
    return v or "(no memory)"

TOOLS: Dict[str, callable] = {
    "note": _note,
    "remember": _remember,
    "recall": _recall,
}