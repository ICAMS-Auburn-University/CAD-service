import logging
import shutil
import tempfile
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from models import SplitJobResult
from cad.workflow import process_order

logger = logging.getLogger(__name__)


def process_uploaded_cad(
    user_id: str,
    order_id: str,
    filename: str,
    file_stream: BinaryIO,
) -> SplitJobResult:
    safe_name = Path(filename).name or "upload.step"
    temp_path = Path(tempfile.gettempdir()) / f"{uuid4()}_{safe_name}"

    try:
        with temp_path.open("wb") as destination:
            shutil.copyfileobj(file_stream, destination)
        logger.info("Saved upload for user %s order %s to %s", user_id, order_id, temp_path)
        return process_order(user_id, order_id, temp_path)
    finally:
        temp_path.unlink(missing_ok=True)
