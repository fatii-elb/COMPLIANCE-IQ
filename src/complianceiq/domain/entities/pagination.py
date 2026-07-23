"""Generic pagination envelope for list responses.

A single ``Page[T]`` shape across every collection endpoint gives clients a
consistent way to iterate results without each endpoint inventing its own
paging contract. In Pydantic v2 a generic model is declared simply by
subclassing ``BaseModel`` and ``Generic[T]``.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """A single page of items plus the metadata to fetch the next.

    Attributes:
        items: The items on this page.
        total: Total number of items across all pages.
        limit: Maximum items requested per page.
        offset: Zero-based offset of the first item on this page.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[T] = Field(default_factory=list)
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=500)
    offset: int = Field(ge=0)

    @property
    def has_more(self) -> bool:
        """Whether more items exist beyond this page."""
        return self.offset + len(self.items) < self.total
