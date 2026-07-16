import sqlite3
import os
import datetime

class MemoryDB:
    def __init__(self, db_path=None):
        if db_path is None:
            # Save db in the memory folder
            db_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(db_dir, "companion.db")
        
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            # Create chat history table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            
            # Create preferences table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.commit()
            print(f"Memory: SQLite database initialized at {self.db_path}")

    def save_message(self, role: str, content: str):
        timestamp = datetime.datetime.now().isoformat()
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO chat_history (role, content, timestamp) VALUES (?, ?, ?)",
                (role, content, timestamp)
            )
            conn.commit()

    def get_recent_history(self, limit=10):
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT role, content FROM chat_history ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            # Since we fetched in descending order, reverse it to get chronological order
            history = [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]
            return history

    def clear_history(self):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM chat_history")
            conn.commit()

    def set_preference(self, key: str, value: str):
        with self.get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO preferences (key, value) VALUES (?, ?)",
                (key, value)
            )
            conn.commit()

    def get_preference(self, key: str, default=None):
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT value FROM preferences WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default
