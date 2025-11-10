from pathlib import Path
from typing import Tuple

from pydantic import BaseModel, ConfigDict


class SplitPart(BaseModel):
    """Represents a single exported assembly node."""

    model_config = ConfigDict(frozen=True)

    name: str
    hierarchy: Tuple[str, ...] = ()
    has_children: bool = False
    step_path: Path
