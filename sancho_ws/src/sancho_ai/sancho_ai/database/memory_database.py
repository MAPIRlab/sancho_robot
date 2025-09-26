import sqlite3
from datetime import datetime


class MemoryDatabase:
    def __init__(self, db_path='memory.db'):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                faceprint_id TEXT NOT NULL,
                version      INTEGER NOT NULL,
                memory_text  TEXT NOT NULL,
                created_at   REAL NOT NULL,           -- timestamp (float)
                PRIMARY KEY (faceprint_id, version)
            )
        ''')

        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_memories_faceprint_version ON memories (faceprint_id, version)')

        self.conn.commit()

    def _read_latest(self, faceprint_id):
        self.cursor.execute('''
            SELECT faceprint_id, version, memory_text, created_at FROM memories WHERE faceprint_id = ? ORDER BY version DESC LIMIT 1
        ''', (faceprint_id,))
        row = self.cursor.fetchone()

        return dict(row) if row else None

    # ----------------- MEMORIES -----------------
    def update_memory(self, faceprint_id, memory_text):
        now_ts = datetime.now().timestamp()

        self.cursor.execute('''
            INSERT INTO memories (faceprint_id, version, memory_text, created_at) SELECT ?, COALESCE(MAX(version), 0) + 1, ?, ?
            FROM memories WHERE faceprint_id = ?
        ''', (faceprint_id, memory_text, now_ts, faceprint_id))
        self.conn.commit()
        
        return self._read_latest(faceprint_id)
    
    def get_memory(self, faceprint_id):
        return self._read_latest(faceprint_id)
