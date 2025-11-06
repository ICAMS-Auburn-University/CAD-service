"""Models describing split job inputs and outputs."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class SplitJobResult(BaseModel):
    """Represents the outcome of processing a CAD split job."""

    user_id: str = Field(..., description="User identifier tied to the storage namespace.")
    order_id: str = Field(..., description="Order identifier tied to the storage namespace.")
    original: str = Field(..., description="Remote storage path for the original uploaded file.")
    parts: List[str] = Field(
        ..., description="Remote storage paths for each part exported from the assembly."
    )


class SplitJobResponse(BaseModel):
    """Response envelope returned by the `/split` API endpoint."""

    data: SplitJobResult
