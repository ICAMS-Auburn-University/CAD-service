import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from api.dependencies import get_settings
from api.utils import temporary_file
from core.config import Settings
from models import SplitJobResponse, MessageResponse
from cad.workflow import process_order


router = APIRouter(tags=["split"])


@router.get("/", response_model=MessageResponse)
async def read_root():
    return {"message": "CAD service for ManuConnect!"}


@router.post(
    "/split",
    response_model=SplitJobResponse,
    status_code=status.HTTP_200_OK,
    summary="Split a CAD assembly into parts and upload results to Supabase.",
)
async def split_cad_model(
    user_id: str = Form(..., min_length=1, description="User identifier for storage scoping."),
    order_id: str = Form(..., min_length=1, description="Order identifier for storage scoping."),
    cad_file: UploadFile = File(..., description="STEP/IGES CAD file to be processed."),
    settings: Settings = Depends(get_settings),
) -> SplitJobResponse:
    """Process an uploaded CAD file and return Supabase storage locations."""

    if not cad_file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename required.")

    clean_user = user_id.strip()
    clean_order = order_id.strip()
    if not clean_user or not clean_order:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User and order identifiers are required.",
        )

    try:
        suffix = Path(cad_file.filename).suffix or ".step"
        with temporary_file(suffix=suffix) as temp_path:
            with temp_path.open("wb") as destination:
                shutil.copyfileobj(cad_file.file, destination)

            result = process_order(clean_user, clean_order, str(temp_path), settings)
    except RuntimeError as exc:
        message = str(exc)
        if "FreeCAD is not available" in message:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "FreeCAD runtime is not available. Ensure the service container includes FreeCAD "
                    "or provide precomputed parts for testing."
                ),
            ) from exc
        raise
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process CAD file.",
        ) from exc
    finally:
        await cad_file.close()

    return SplitJobResponse(data=result)


__all__ = ["router"]
