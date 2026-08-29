"""Shared schemas (kernel k0): pagination envelope."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class MessageResponse(BaseModel):
    """Generic ``{message: str}`` envelope shared across ring routes."""

    message: str

