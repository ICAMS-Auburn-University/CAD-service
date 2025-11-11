import logging
import shutil
import tempfile
from pathlib import Path
from typing import BinaryIO

from models import SplitJobResult
from cad.workflow import process_order

logger = logging.getLogger(__name__)


def process_uploaded_cad(
    user_id: str,
    order_id: str,
    filename: str,
    file_stream: BinaryIO,
) -> SplitJobResult:
    temp_handle = tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix)
    temp_handle.close()
    temp_path = Path(temp_handle.name)

    try:
        with temp_path.open("wb") as destination:
            shutil.copyfileobj(file_stream, destination)
        logger.info("Saved upload for user %s order %s to %s", user_id, order_id, temp_path)
        return process_order(user_id, order_id, temp_path)
    finally:
        temp_path.unlink(missing_ok=True)
