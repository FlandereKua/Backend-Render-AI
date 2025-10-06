import sqlite3
import os
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent.parent.parent / "sessions"
DB_PATH = DB_DIR / "chat_history.db"
DB_DIR.mkdir(exist_ok=True)

def init_db():
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.commit()
        con.close()
    except sqlite3.Error as e:
        print(f"Lỗi khi khởi tạo database: {e}")

def add_message(session_id: str, role: str, content: str):
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        cur.execute(
            "INSERT INTO chat_history (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content)
        )
        con.commit()
        con.close()
    except sqlite3.Error as e:
        print(f"Lỗi khi thêm tin nhắn: {e}")

def get_history(session_id: str, limit: int = 10) -> list:
    history = []
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        res = cur.execute(
            "SELECT role, content FROM chat_history WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
            (session_id, limit)
        )
        rows = reversed(res.fetchall())
        for row in rows:
            history.append({"role": row[0], "parts": [row[1]]})
        con.close()
    except sqlite3.Error as e:
        print(f"Lỗi khi lấy lịch sử: {e}")
    return history