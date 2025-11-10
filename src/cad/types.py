from __future__ import annotations

from pathlib import Path
from typing import Tuple

from pydantic import BaseModel, ConfigDict, Field


class SplitPart(BaseModel):
    """Represents a single exported assembly node."""

    model_config = ConfigDict(frozen=True)

    name: str
    hierarchy: Tuple[str, ...] = Field(default_factory=tuple)
    has_children: bool = False
    step_path: Path


__all__ = ["SplitPart"]
