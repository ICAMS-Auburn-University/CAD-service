"""Models describing split job inputs and outputs."""

from __future__ import annotations

from typing import Any, Dict, List, Union

from pydantic import BaseModel, Field


class SplitPartFile(BaseModel):
    """Metadata for an exported STEP / DXF pair."""

    name: str = Field(..., description="Part identifier derived from the CAD hierarchy.")
    hierarchy: List[str] = Field(
        default_factory=list, description="Ordered list of parent assemblies for this part."
    )
    step_path: str = Field(..., description="Supabase storage path for the STEP export.")
    dxf_path: str = Field(..., description="Supabase storage path for the DXF export.")


class SplitJobResult(BaseModel):
    """Represents the outcome of processing a CAD split job."""

    user_id: str = Field(..., description="User identifier tied to the storage namespace.")
    order_id: str = Field(..., description="Order identifier tied to the storage namespace.")
    original: str = Field(..., description="Remote storage path for the original uploaded file.")
    parts: List[SplitPartFile] = Field(..., description="Per-part STEP/DXF artifacts.")
    layout: Union[Dict[str, Any], List[str]] = Field(
        ...,
        description=(
            "Nested dictionary describing the assembly. "
            "Dictionary values are subassemblies; list values contain final part names."
        ),
    )


class SplitJobResponse(BaseModel):
    """Response envelope returned by the `/split` API endpoint."""

    data: SplitJobResult
