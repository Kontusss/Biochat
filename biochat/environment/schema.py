"""Schema for the environment catalog (data-lake / library descriptors)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CatalogEntry(BaseModel):
    """One described resource in the environment catalog.

    Attributes:
        name: Canonical resource name (e.g. dataset filename or tool name).
        description: Human-readable description injected into the system prompt.
        commercial_allowed: Whether the entry may be used in commercial mode.
        license_note: Known license information (when recorded upstream).
        source: Provenance of the entry (e.g. upstream dataset provider).
    """

    name: str
    description: str
    commercial_allowed: bool = True
    license_note: Optional[str] = None
    source: Optional[str] = None


class EnvironmentCatalogSchema(BaseModel):
    """Top-level catalog document."""

    meta: dict = Field(default_factory=dict)
    data_lake: list[CatalogEntry] = Field(default_factory=list)
    libraries: list[CatalogEntry] = Field(default_factory=list)
