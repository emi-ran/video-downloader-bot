import sqlite3
from datetime import datetime

DB_PATH = "downloads.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                platform TEXT,
                link TEXT,
                status TEXT,
                timestamp TEXT
            )
        ''')
        conn.commit()

def add_download(user_id: int, username: str, platform: str, link: str, status: str):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO downloads (user_id, username, platform, link, status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, username, platform, link, status, datetime.utcnow().isoformat()))
        conn.commit() 