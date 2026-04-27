from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.domain import ProviderCreateReviewRequest, ProviderName, ProviderResultPayload, ProviderStatus, ProviderTaskHandle, TaskRecord


class BaseProvider(ABC):
    name: ProviderName

    async def close(self) -> None:
        return None

    @abstractmethod
    async def create_review(self, request: ProviderCreateReviewRequest) -> ProviderTaskHandle:
        raise NotImplementedError

    @abstractmethod
    async def get_status(self, task: TaskRecord) -> ProviderStatus:
        raise NotImplementedError

    @abstractmethod
    async def get_result(self, task: TaskRecord) -> ProviderResultPayload:
        raise NotImplementedError
