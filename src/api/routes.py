from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from models import SplitJobResponse, MessageResponse
from cad.service import process_uploaded_cad


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
    user_id: str,
    order_id: str,
    cad_file: UploadFile,
) -> SplitJobResponse:
    try:
        result = process_uploaded_cad(user_id, order_id, cad_file.filename, cad_file.file)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process CAD file.",
        ) from exc
    finally:
        await cad_file.close()

    return SplitJobResponse(data=result)
