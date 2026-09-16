"""Shared response envelopes."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str
    fields: dict | None = None


class ErrorOut(BaseModel):
    error: ErrorDetail


class Paginated(BaseModel, Generic[T]):
    items: list[T]
    total: int
