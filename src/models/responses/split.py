from typing import Any, Dict, List, Union

from pydantic import BaseModel


class SplitPartFile(BaseModel):
    """Metadata for an exported STEP / DXF pair."""

    name: str
    hierarchy: List[str] = []
    step_path: str
    dxf_path: str


class SplitJobResult(BaseModel):
    """Represents the outcome of processing a CAD split job."""

    user_id: str
    order_id: str
    original: str
    parts: List[SplitPartFile]
    layout: Union[Dict[str, Any], List[str]]


class SplitJobResponse(BaseModel):
    """Response envelope returned by the `/split` API endpoint."""

    data: SplitJobResult
