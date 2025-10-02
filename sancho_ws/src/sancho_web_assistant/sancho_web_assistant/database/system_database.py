import sqlite3

from datetime import datetime
from enum import Enum


class CONSTANTS:
    class LEVEL(str, Enum):
        INFO = "INFO"
        WARNING = "WARNING"
        ERROR = "ERROR"
        DEBUG = "DEBUG"

    class ORIGIN(str, Enum):
        ROS = "ROS"
        WEB = "WEB"

    class ACTION(str, Enum):
        ADD_CLASS = "add_class"
        RENAME_CLASS = "rename_class"
        DELETE_CLASS = "delete_class"
        DELETE_ALL = "delete_all"
        ADD_FEATURES = "add_features"
        UPDATE_FACE = "update_face"

        LOAD_LLM_MODEL = "load_llm_model"
        UNLOAD_LLM_MODEL = "unload_llm_model"
        ACTIVE_LLM_MODEL = "active_llm_model"

        LOAD_TTS_MODEL = "load_tts_model"
        UNLOAD_TTS_MODEL = "unload_tts_model"
        ACTIVE_TTS_MODEL = "active_tts_model"

        LOAD_STT_MODEL = "load_stt_model"
        UNLOAD_STT_MODEL = "unload_stt_model"
        ACTIVE_STT_MODEL = "active_stt_model"


class SystemDatabase:
    def __init__(self, db_path='system.db'):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        # Enforce FK constraints
        self.conn.execute('PRAGMA foreign_keys = ON')
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        # ----------------- LOGS GENERALES -----------------
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                origin TEXT NOT NULL,
                actor TEXT,
                action TEXT NOT NULL,
                target TEXT,
                message TEXT,
                metadata TEXT
            )
        ''')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs (timestamp)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_action ON logs (action)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_origin ON logs (origin)')

        # ----------------- CONVERSATION LOGS -----------------
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at REAL NOT NULL
            )
        ''')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversations_started_at ON conversations (started_at)')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                timestamp REAL NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                CHECK (role IN ('user','assistant'))
            )
        ''')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_time ON messages (conversation_id, timestamp)')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS message_nlu (
                message_id INTEGER PRIMARY KEY,
                user_id TEXT,
                user_name TEXT,
                intent TEXT NOT NULL,
                arguments_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
            )
        ''')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_message_nlu_intent ON message_nlu (intent)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_message_nlu_user ON message_nlu (user_id)')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS message_llm (
                message_id INTEGER PRIMARY KEY,
                value_json TEXT,
                provider TEXT,
                model TEXT,
                FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
            )
        ''')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_message_llm_model ON message_llm (provider, model)')

        self.conn.commit()

    # ----------------- LOGS (GENERALES) -----------------
    def create_log(self, level, origin, action, actor=None, target=None, message=None, metadata_json=None):
        if level not in CONSTANTS.LEVEL._value2member_map_:
            raise ValueError(f"Invalid level: {level}")
        if origin not in CONSTANTS.ORIGIN._value2member_map_:
            raise ValueError(f"Invalid origin: {origin}")
        if action not in CONSTANTS.ACTION._value2member_map_:
            raise ValueError(f"Invalid action: {action}")

        timestamp = datetime.now().timestamp()
        self.cursor.execute('''
            INSERT INTO logs (timestamp, level, origin, actor, action, target, message, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, level, origin, actor, action, target, message, metadata_json))
        self.conn.commit()

    def get_all_logs(self):
        self.cursor.execute('SELECT * FROM logs')
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]

    def get_log_by_id(self, id):
        self.cursor.execute('SELECT * FROM logs WHERE id = ?', (id,))
        row = self.cursor.fetchone()
        return dict(row) if row else {}

    # ----------------- CONVERSATION LOGS -----------------
    def append_turn(self, conversation_id: str, user_timestamp: int, user_id: str, user_name: str, user_text: str, user_intent: str, user_arguments_json: str,
                    assistant_timestamp: int, assistant_text: str, assistant_value_json: str, assistant_provider: str, assistant_model: str) -> tuple[int, int]:
        
        with self.conn:
            user_message_id = self.create_message(conversation_id, "user", user_text, user_timestamp)
            self.annotate_message_nlu(user_message_id, user_intent, user_arguments_json, user_id, user_name)

            assistant_message_id = self.create_message(conversation_id, "assistant", assistant_text, assistant_timestamp)
            self.annotate_message_llm(assistant_message_id, assistant_value_json, assistant_provider, assistant_model)

        return user_message_id, assistant_message_id
    
    # ---- Conversations ----
    def create_conversation(self, started_at: float | None = None) -> int:
        ts = started_at if started_at is not None else datetime.now().timestamp()
        self.cursor.execute('INSERT INTO conversations (started_at) VALUES (?)', (ts,))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_conversation_by_id(self, conversation_id: int) -> dict:
        self.cursor.execute('SELECT * FROM conversations WHERE id = ?', (conversation_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else {}

    def get_all_conversations(self, start_time: float | None = None, end_time: float | None = None) -> list[dict]:
        query = 'SELECT * FROM conversations'
        params = []
        clauses = []
        if start_time is not None:
            clauses.append('started_at >= ?')
            params.append(start_time)
        if end_time is not None:
            clauses.append('started_at <= ?')
            params.append(end_time)
        if clauses:
            query += ' WHERE ' + ' AND '.join(clauses)
        query += ' ORDER BY started_at DESC'
        self.cursor.execute(query, params)
        rows = self.cursor.fetchall()
        return [dict(r) for r in rows]

    # ---- Messages ----
    def create_message(self, conversation_id: int, role: str, content: str, timestamp: float | None = None) -> int:
        if role not in ('user', 'assistant'):
            raise ValueError("role must be 'user' or 'assistant'")
        ts = timestamp if timestamp is not None else datetime.now().timestamp()
        self.cursor.execute('''
            INSERT INTO messages (conversation_id, timestamp, role, content)
            VALUES (?, ?, ?, ?)
        ''', (conversation_id, ts, role, content))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_message_by_id(self, message_id: int) -> dict:
        self.cursor.execute('SELECT * FROM messages WHERE id = ?', (message_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else {}

    def get_messages_by_conversation(self, conversation_id: int) -> list[dict]:
        self.cursor.execute('''
            SELECT * FROM messages
            WHERE conversation_id = ?
            ORDER BY timestamp ASC
        ''', (conversation_id,))
        rows = self.cursor.fetchall()
        return [dict(r) for r in rows]

    # ---- NLU annotations (for user messages) ----
    def annotate_message_nlu(self, message_id: int, intent: str, arguments_json: str = "{}", user_id: str | None = None, user_name: str | None = None) -> None:
        # Validar que el mensaje sea 'user'
        self.cursor.execute('SELECT role FROM messages WHERE id = ?', (message_id,))
        row = self.cursor.fetchone()
        if not row:
            raise ValueError(f"message_id {message_id} does not exist")
        if row['role'] != 'user':
            raise ValueError(f"message_id {message_id} is not a 'user' message")
        print("message_id", message_id, "user_id", user_id, "user_name", user_name, "intent", intent, "arguments_json", arguments_json)
        # da error aqui por la cara
        self.cursor.execute('''
            INSERT INTO message_nlu (message_id, user_id, user_name, intent, arguments_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(message_id) DO UPDATE SET
                user_id=excluded.user_id,
                user_name=excluded.user_name,
                intent=excluded.intent,
                arguments_json=excluded.arguments_json
        ''', (message_id, user_id, user_name, intent, arguments_json))
        self.conn.commit()

    def get_message_nlu(self, message_id: int) -> dict:
        self.cursor.execute('SELECT * FROM message_nlu WHERE message_id = ?', (message_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else {}

    # ---- LLM metadata (for assistant messages) ----
    def annotate_message_llm(self, message_id: int, value_json: str | None = None, provider: str | None = None, model: str | None = None) -> None:
        # Validar que el mensaje sea 'assistant'
        self.cursor.execute('SELECT role FROM messages WHERE id = ?', (message_id,))
        row = self.cursor.fetchone()
        if not row:
            raise ValueError(f"message_id {message_id} does not exist")
        if row['role'] != 'assistant':
            raise ValueError(f"message_id {message_id} is not an 'assistant' message")

        self.cursor.execute('''
            INSERT INTO message_llm (message_id, value_json, provider, model)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(message_id) DO UPDATE SET
                value_json=excluded.value_json,
                provider=excluded.provider,
                model=excluded.model
        ''', (message_id, value_json, provider, model))
        self.conn.commit()

    def get_message_llm(self, message_id: int) -> dict:
        self.cursor.execute('SELECT * FROM message_llm WHERE message_id = ?', (message_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else {}
