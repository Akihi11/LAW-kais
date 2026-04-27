from __future__ import annotations

import secrets

from app.repositories.task_repository import TaskRepository
from app.schemas.domain import TaskRecord


class TaskService:
    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    def generate_task_id(self) -> str:
        return f"rev_{secrets.token_hex(6)}"

    async def save_task(self, task: TaskRecord) -> TaskRecord:
        return await self.repository.save(task)

    async def get_task(self, task_id: str) -> TaskRecord:
        return await self.repository.get(task_id)

    async def update_task(self, task: TaskRecord) -> TaskRecord:
        return await self.repository.save(task)
