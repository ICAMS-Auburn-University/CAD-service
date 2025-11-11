from typing import List

from pydantic import BaseModel, Field


class SplitPartFile(BaseModel):
    """Metadata for a STEP part stored in Supabase."""

    name: str
    hierarchy: List[str] = Field(default_factory=list)
    storage_path: str


class SplitJobResult(BaseModel):
    """Represents the outcome of processing a CAD split job."""

    user_id: str
    order_id: str
    original: str
    parts: List[SplitPartFile] = Field(default_factory=list)


class SplitJobResponse(BaseModel):
    """Response envelope returned by the `/split` API endpoint."""

    data: SplitJobResult
