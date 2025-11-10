from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import BinaryIO

from models import SplitJobResult
from cad.workflow import process_order


def process_uploaded_cad(
    user_id: str,
    order_id: str,
    filename: str,
    file_stream: BinaryIO,
) -> SplitJobResult:
    """Persist an uploaded CAD file and run the workflow."""

    suffix = Path(filename).suffix or ".step"
    temp_handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_handle.close()
    temp_path = Path(temp_handle.name)

    try:
        with temp_path.open("wb") as destination:
            shutil.copyfileobj(file_stream, destination)

        return process_order(user_id, order_id, str(temp_path))
    finally:
        temp_path.unlink(missing_ok=True)
