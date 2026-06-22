# chanlun/cache.py
# 诊断结果 SQLite 缓存与请求日志
import sqlite3
import json
import time
import os
import threading
from typing import List, Optional, Dict, Any

_LOCK = threading.Lock()
_DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "chanlun_cache.sqlite")
_DEFAULT_DB_PATH = os.path.abspath(_DEFAULT_DB_PATH)


class DiagnosisCache:
    """SQLite 缓存 / 持久化"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _DEFAULT_DB_PATH
        self._init_schema()

    # ---------- 基础 ----------
    def _conn(self):
        return sqlite3.connect(self.db_path, timeout=10)

    def _init_schema(self):
        with _LOCK:
            with self._conn() as conn:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS single_diagnosis (
                        code TEXT NOT NULL,
                        level TEXT NOT NULL,
                        date TEXT NOT NULL,
                        result_json TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        PRIMARY KEY (code, level, date)
                    );

                    CREATE TABLE IF NOT EXISTS multilevel_diagnosis (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        code TEXT NOT NULL,
                        date TEXT NOT NULL,
                        result_json TEXT NOT NULL,
                        created_at REAL NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_multilevel_code ON multilevel_diagnosis(code);

                    CREATE TABLE IF NOT EXISTS request_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL NOT NULL,
                        endpoint TEXT NOT NULL,
                        code TEXT,
                        response_time_ms REAL,
                        status_code INTEGER,
                        error TEXT
                    );

                    CREATE INDEX IF NOT EXISTS idx_req_time ON request_log(timestamp);
                    CREATE INDEX IF NOT EXISTS idx_req_endpoint ON request_log(endpoint);
                    """
                )

    # ---------- 工具 ----------
    @staticmethod
    def _today() -> str:
        return time.strftime("%Y-%m-%d")

    # ---------- 单级别 ----------
    def get_single(self, code: str, level: str, max_age_h: int = 24) -> Optional[dict]:
        threshold = time.time() - max_age_h * 3600
        with self._conn() as conn:
            row = conn.execute(
                "SELECT result_json, created_at FROM single_diagnosis "
                "WHERE code=? AND level=? AND date=?",
                (code, level, self._today()),
            ).fetchone()
            if row and row[1] >= threshold:
                return json.loads(row[0])
            return None

    def save_single(self, code: str, level: str, result_json: Dict[str, Any]) -> None:
        serialized = json.dumps(result_json, ensure_ascii=False)
        with _LOCK:
            with self._conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO single_diagnosis(code, level, date, result_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (code, level, self._today(), serialized, time.time()),
                )

    # ---------- 多级别 ----------
    def get_multilevel(self, code: str, max_age_h: int = 6) -> Optional[dict]:
        threshold = time.time() - max_age_h * 3600
        with self._conn() as conn:
            row = conn.execute(
                "SELECT result_json, created_at FROM multilevel_diagnosis "
                "WHERE code=? AND date=? ORDER BY created_at DESC LIMIT 1",
                (code, self._today()),
            ).fetchone()
            if row and row[1] >= threshold:
                return json.loads(row[0])
            return None

    def save_multilevel(self, code: str, result_json: Dict[str, Any]) -> None:
        serialized = json.dumps(result_json, ensure_ascii=False)
        with _LOCK:
            with self._conn() as conn:
                conn.execute(
                    "INSERT INTO multilevel_diagnosis(code, date, result_json, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (code, self._today(), serialized, time.time()),
                )

    # ---------- 历史 ----------
    def get_history(self, code: str, n: int = 30) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT date, result_json, created_at FROM multilevel_diagnosis "
                "WHERE code=? ORDER BY created_at DESC LIMIT ?",
                (code, n),
            ).fetchall()
            return [
                {"date": r[0], "result": json.loads(r[1]), "created_at": r[2]}
                for r in rows
            ]

    # ---------- 日志 ----------
    def log_request(self, endpoint: str, code: Optional[str], response_time_ms: float,
                     status_code: int, error: Optional[str] = None) -> None:
        with _LOCK:
            with self._conn() as conn:
                conn.execute(
                    "INSERT INTO request_log(timestamp, endpoint, code, response_time_ms, status_code, error) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (time.time(), endpoint, code, response_time_ms, status_code, error),
                )

    def get_recent_logs(self, n: int = 50) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT timestamp, endpoint, code, response_time_ms, status_code, error "
                "FROM request_log ORDER BY id DESC LIMIT ?",
                (n,),
            ).fetchall()
            return [
                {"timestamp": r[0], "endpoint": r[1], "code": r[2],
                 "response_time_ms": r[3], "status_code": r[4], "error": r[5]}
                for r in rows
            ]

    def clear_all(self) -> None:
        """仅用于测试清理"""
        with _LOCK:
            with self._conn() as conn:
                conn.execute("DELETE FROM single_diagnosis")
                conn.execute("DELETE FROM multilevel_diagnosis")
                conn.execute("DELETE FROM request_log")
