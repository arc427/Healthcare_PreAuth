import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "preauth.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS authorization_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    encrypted_data TEXT NOT NULL,
    iv TEXT NOT NULL,
    document_hash TEXT NOT NULL,
    blockchain_request_id INTEGER NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.execute(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def insert_record(
    patient_id: str,
    encrypted_data: str,
    iv: str,
    document_hash: str,
    blockchain_request_id: int,
) -> int:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO authorization_records (
                patient_id, encrypted_data, iv, document_hash, blockchain_request_id
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (patient_id, encrypted_data, iv, document_hash, blockchain_request_id),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def get_by_blockchain_id(blockchain_request_id: int) -> sqlite3.Row | None:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM authorization_records WHERE blockchain_request_id = ?",
            (blockchain_request_id,),
        ).fetchone()
    finally:
        conn.close()


def get_all_records() -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM authorization_records ORDER BY id DESC"
        ).fetchall()
    finally:
        conn.close()
