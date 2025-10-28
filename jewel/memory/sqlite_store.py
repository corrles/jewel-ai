import sqlite3
from pathlib import Path
from typing import Optional, List, Tuple

class SqliteStore:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._init()

    def _init(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS kv (
                k TEXT PRIMARY KEY,
                v TEXT
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT,
                content TEXT,
                ts DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS private_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT,
                content TEXT,
                ts DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self.conn.commit()

    def set(self, key: str, value: str) -> None:
        self.conn.execute("REPLACE INTO kv (k, v) VALUES (?, ?)", (key, value))
        self.conn.commit()

    def get(self, key: str) -> Optional[str]:
        cur = self.conn.execute("SELECT v FROM kv WHERE k=?", (key,))
        row = cur.fetchone()
        return row[0] if row else None

    def add_message(self, role: str, content: str) -> None:
        self.conn.execute("INSERT INTO messages (role, content) VALUES (?, ?)", (role, content))
        self.conn.commit()

    def add_private_message(self, role: str, content: str) -> None:
        """Store a private message/reflection that is not part of public messages."""
        self.conn.execute("INSERT INTO private_messages (role, content) VALUES (?, ?)", (role, content))
        self.conn.commit()

    def recent_private_messages(self, limit: int = 50) -> List[Tuple[str, str]]:
        cur = self.conn.execute(
            "SELECT role, content FROM private_messages ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        rows.reverse()
        return rows

    def clear_private_messages(self) -> None:
        self.conn.execute("DELETE FROM private_messages")
        self.conn.commit()

    def recent_messages(self, limit: int = 20) -> List[Tuple[str, str]]:
        cur = self.conn.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        rows.reverse()
        return rows