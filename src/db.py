import sqlite3
import os
import json
from typing import Optional, List, Dict, Any

def get_connection(db_path: str = "data/leads.db") -> sqlite3.Connection:
    dirname = os.path.dirname(db_path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str = "data/leads.db") -> None:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS keywords (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        keywords TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS seen_tweets (
        tweet_id TEXT PRIMARY KEY,
        author_handle TEXT,
        created_at TEXT,
        text TEXT,
        is_lead BOOLEAN,
        reason TEXT,
        suggested_comment TEXT,
        evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()

def save_keywords(user_id: int, keywords: List[str], db_path: str = "data/leads.db") -> None:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    keywords_json = json.dumps([k.strip().lower() for k in keywords if k.strip()])
    cursor.execute("DELETE FROM keywords WHERE user_id = ?", (user_id,))
    cursor.execute("INSERT INTO keywords (user_id, keywords) VALUES (?, ?)", (user_id, keywords_json))
    conn.commit()
    conn.close()

def get_active_keywords(db_path: str = "data/leads.db") -> List[str]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT keywords FROM keywords ORDER BY updated_at DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row and row["keywords"]:
        return json.loads(row["keywords"])
    return []

def is_tweet_seen(tweet_id: str, db_path: str = "data/leads.db") -> bool:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM seen_tweets WHERE tweet_id = ?", (tweet_id,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def save_tweet_lead(tweet_data: Dict[str, Any], db_path: str = "data/leads.db") -> None:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO seen_tweets 
    (tweet_id, author_handle, created_at, text, is_lead, reason, suggested_comment)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        tweet_data.get("tweet_id"),
        tweet_data.get("author_handle"),
        tweet_data.get("created_at"),
        tweet_data.get("text"),
        tweet_data.get("is_lead", False),
        tweet_data.get("reason", ""),
        tweet_data.get("suggested_comment", "")
    ))
    conn.commit()
    conn.close()

def get_lead_by_id(tweet_id: str, db_path: str = "data/leads.db") -> Optional[Dict[str, Any]]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM seen_tweets WHERE tweet_id = ?", (tweet_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None
