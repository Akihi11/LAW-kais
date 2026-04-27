from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.exceptions import TaskNotFoundError
from app.schemas.domain import TaskRecord


class TaskRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._lock = asyncio.Lock()

    def ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_tasks (
                    task_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    async def save(self, task: TaskRecord) -> TaskRecord:
        async with self._lock:
            task.updated_at = datetime.now(UTC)
            payload = task.model_dump(mode='json')
            await asyncio.to_thread(self._upsert, task.task_id, payload, payload['created_at'], payload['updated_at'])
            return task.model_copy(deep=True)

    async def get(self, task_id: str) -> TaskRecord:
        async with self._lock:
            payload = await asyncio.to_thread(self._fetch, task_id)
        if payload is None:
            raise TaskNotFoundError(task_id)
        return TaskRecord.model_validate(payload)

    def _upsert(self, task_id: str, payload: dict, created_at: str, updated_at: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO review_tasks (task_id, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (task_id, json.dumps(payload, ensure_ascii=False), created_at, updated_at),
            )
            conn.commit()

    def _fetch(self, task_id: str) -> dict | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                'SELECT payload_json FROM review_tasks WHERE task_id = ?',
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])
