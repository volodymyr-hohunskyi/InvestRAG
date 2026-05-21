import sqlite3
import os
import numpy as np
from pathlib import Path

DB_PATH = os.environ.get("DB_PATH", str(Path(__file__).parent / "data" / "investrag.db"))


def get_db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            embedding BLOB NOT NULL,
            source_type TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS instruments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            provider TEXT NOT NULL,
            type TEXT NOT NULL,
            min_amount REAL,
            currency TEXT DEFAULT 'UAH',
            expected_yield_min REAL,
            expected_yield_max REAL,
            risk_level INTEGER CHECK (risk_level BETWEEN 1 AND 5),
            horizon_months INTEGER,
            liquidity TEXT,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS risk_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            risk_tolerance INTEGER CHECK (risk_tolerance BETWEEN 1 AND 5),
            investment_horizon_months INTEGER,
            available_amount REAL,
            currency TEXT DEFAULT 'UAH',
            goals TEXT DEFAULT '[]',
            experience_level TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_type, source_name);
        CREATE INDEX IF NOT EXISTS idx_instruments_active ON instruments(is_active);
        CREATE INDEX IF NOT EXISTS idx_profiles_user ON risk_profiles(user_id);
    """)
    conn.commit()
    conn.close()


def embed_to_blob(embedding: list | np.ndarray) -> bytes:
    return np.array(embedding, dtype=np.float32).tobytes()


def blob_to_embed(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def match_chunks(query_embedding: list | np.ndarray, match_count: int = 5, match_threshold: float = 0.7) -> list[dict]:
    query_vec = np.array(query_embedding, dtype=np.float32)
    query_norm = query_vec / np.linalg.norm(query_vec)

    conn = get_db()
    rows = conn.execute("SELECT id, content, embedding, source_type, source_name FROM chunks").fetchall()
    conn.close()

    if not rows:
        return []

    results = []
    for row in rows:
        chunk_vec = blob_to_embed(row["embedding"])
        chunk_norm = chunk_vec / np.linalg.norm(chunk_vec)
        similarity = float(np.dot(query_norm, chunk_norm))
        if similarity >= match_threshold:
            results.append({
                "id": row["id"],
                "content": row["content"],
                "source_type": row["source_type"],
                "source_name": row["source_name"],
                "similarity": similarity
            })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:match_count]


def insert_chunk(content: str, embedding: list | np.ndarray, source_type: str, source_name: str, source_url: str = None):
    conn = get_db()
    conn.execute(
        "INSERT INTO chunks (content, embedding, source_type, source_name, source_url) VALUES (?, ?, ?, ?, ?)",
        (content, embed_to_blob(embedding), source_type, source_name, source_url)
    )
    conn.commit()
    conn.close()


def get_existing_source_urls(source_type: str) -> set:
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT source_url FROM chunks WHERE source_type = ?", (source_type,)
    ).fetchall()
    conn.close()
    return {r["source_url"] for r in rows if r["source_url"]}


def get_existing_source_names(source_type: str) -> set:
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT source_name FROM chunks WHERE source_type = ?", (source_type,)
    ).fetchall()
    conn.close()
    return {r["source_name"] for r in rows}


def get_instruments(active_only=True, max_risk=None, max_amount=None) -> list[dict]:
    conn = get_db()
    query = "SELECT * FROM instruments WHERE 1=1"
    params = []
    if active_only:
        query += " AND is_active = 1"
    if max_risk is not None:
        query += " AND risk_level <= ?"
        params.append(max_risk)
    if max_amount is not None:
        query += " AND min_amount <= ?"
        params.append(max_amount)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_profile(user_id: str) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM risk_profiles WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def save_profile(user_id: str, profile_data: dict):
    import json
    conn = get_db()
    existing = conn.execute("SELECT id FROM risk_profiles WHERE user_id = ?", (user_id,)).fetchone()

    goals_json = json.dumps(profile_data.get("goals", []), ensure_ascii=False)

    if existing:
        conn.execute("""
            UPDATE risk_profiles SET
                risk_tolerance = ?, investment_horizon_months = ?,
                available_amount = ?, currency = ?, goals = ?,
                experience_level = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (
            profile_data.get("risk_tolerance"),
            profile_data.get("investment_horizon_months"),
            profile_data.get("available_amount"),
            profile_data.get("currency", "UAH"),
            goals_json,
            profile_data.get("experience_level"),
            user_id
        ))
    else:
        conn.execute("""
            INSERT INTO risk_profiles (user_id, risk_tolerance, investment_horizon_months,
                available_amount, currency, goals, experience_level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            profile_data.get("risk_tolerance"),
            profile_data.get("investment_horizon_months"),
            profile_data.get("available_amount"),
            profile_data.get("currency", "UAH"),
            goals_json,
            profile_data.get("experience_level"),
        ))
    conn.commit()
    conn.close()


# Initialize on import
init_db()
