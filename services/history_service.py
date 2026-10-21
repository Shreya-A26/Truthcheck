import sqlite3
import json
import uuid
from datetime import datetime, timezone
import os

class HistoryService:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_history (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    title TEXT NOT NULL,
                    input_type TEXT NOT NULL,
                    prediction TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    verification_status TEXT NOT NULL,
                    result_json TEXT NOT NULL
                )
            """)
            conn.commit()

    def save_analysis(self, title: str, input_type: str, prediction: str, confidence: float, verification_status: str, result_data: dict) -> str:
        record_id = result_data.get("id") or str(uuid.uuid4())
        # Strip large raw files, keep only structured result
        clean_result = dict(result_data)
        clean_result["id"] = record_id

        # Ensure title is reasonable length
        safe_title = (title[:120] + "...") if len(title) > 120 else (title or "Untitled Analysis")

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO analysis_history (id, created_at, title, input_type, prediction, confidence, verification_status, result_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record_id,
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                safe_title,
                input_type,
                prediction,
                confidence,
                verification_status,
                json.dumps(clean_result)
            ))
            conn.commit()
            
        return record_id

    def get_all(self, limit: int = 50) -> list[dict]:
        with self._get_connection() as conn:
            cur = conn.execute("""
                SELECT id, created_at, title, input_type, prediction, confidence, verification_status
                FROM analysis_history
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def get_by_id(self, record_id: str) -> dict | None:
        with self._get_connection() as conn:
            cur = conn.execute("""
                SELECT id, created_at, title, input_type, prediction, confidence, verification_status, result_json
                FROM analysis_history
                WHERE id = ?
            """, (record_id,))
            row = cur.fetchone()
            if not row:
                return None
            data = dict(row)
            data["result"] = json.loads(data["result_json"])
            return data

    def delete_by_id(self, record_id: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM analysis_history WHERE id = ?", (record_id,))
            conn.commit()
            return cur.rowcount > 0

    def clear_all(self) -> int:
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM analysis_history")
            conn.commit()
            return cur.rowcount
