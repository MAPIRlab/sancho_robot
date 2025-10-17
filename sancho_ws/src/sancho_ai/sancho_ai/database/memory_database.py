import sqlite3
import threading
from datetime import datetime

class MemoryDatabase:
    def __init__(self, db_path='memory.db'):
        self.conn = sqlite3.connect(db_path, check_same_thread=False, timeout=5)
        self.conn.row_factory = sqlite3.Row

        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA busy_timeout=5000;")

        self._lock = threading.Lock()

        self._create_tables()

    def _create_tables(self):
        with self._lock:
            cur = self.conn.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS memories (
                    faceprint_id TEXT NOT NULL,
                    version      INTEGER NOT NULL,
                    memory_text  TEXT NOT NULL,
                    created_at   REAL NOT NULL,           -- timestamp (float)
                    PRIMARY KEY (faceprint_id, version)
                )
            ''')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_memories_faceprint_version ON memories (faceprint_id, version)')
            self.conn.commit()

    def _read_latest(self, faceprint_id):
        with self._lock:
            cur = self.conn.cursor()
            cur.execute('''
                SELECT faceprint_id, version, memory_text, created_at
                FROM memories
                WHERE faceprint_id = ?
                ORDER BY version DESC
                LIMIT 1
            ''', (faceprint_id,))
            row = cur.fetchone()
            return dict(row) if row else {}

    # ----------------- MEMORIES -----------------
    def direct_update_memory(self, faceprint_id: str, memory_text: str):
        latest = self._read_latest(faceprint_id)

        with self._lock:
            cur = self.conn.cursor()
            if not latest:
                now_ts = datetime.now().timestamp()
                cur.execute('''
                    INSERT INTO memories (faceprint_id, version, memory_text, created_at)
                    VALUES (?, 0, ?, ?)
                    ''', (faceprint_id, memory_text, now_ts))
            else:
                cur.execute('''
                    UPDATE memories
                    SET memory_text = ?
                    WHERE faceprint_id = ? AND version = ?
                    ''', (memory_text, faceprint_id, latest["version"]))
            self.conn.commit()

        return self._read_latest(faceprint_id)

    def update_memory(self, faceprint_id: str, memory_text: str):
        now_ts = datetime.now().timestamp()

        with self._lock:
            cur = self.conn.cursor()
            cur.execute('''
                INSERT INTO memories (faceprint_id, version, memory_text, created_at) SELECT ?, COALESCE(MAX(version), 0) + 1, ?, ?
                FROM memories WHERE faceprint_id = ?
            ''', (faceprint_id, memory_text, now_ts, faceprint_id))
            self.conn.commit()
        
        return self._read_latest(faceprint_id)

    def get_all_latest_memories(self) -> list:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute('''
                SELECT m.faceprint_id, m.version, m.memory_text, m.created_at
                FROM memories AS m
                JOIN (
                    SELECT faceprint_id, MAX(version) AS max_version
                    FROM memories
                    GROUP BY faceprint_id
                ) AS t
                ON t.faceprint_id = m.faceprint_id
                AND t.max_version  = m.version
                ORDER BY m.faceprint_id
            ''')
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def get_all_versions(self, faceprint_id: str) -> list:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute('''
                SELECT faceprint_id, version, memory_text, created_at
                FROM memories
                WHERE faceprint_id = ?
                ORDER BY version DESC
            ''', (faceprint_id))
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def get_memory(self, faceprint_id: str) -> dict:
        return self._read_latest(faceprint_id)

    def get_memory_text(self, faceprint_id: str) -> str:
        return self.get_memory(faceprint_id).get("memory_text", "")