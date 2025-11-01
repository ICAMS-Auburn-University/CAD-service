from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, List

from config import Settings
from splitter import export_parts, import_file, split_into_parts
from storage import SupabaseStorageClient

logger = logging.getLogger(__name__)


def process_order(user_id: str, order_id: str, input_file: str, settings: Settings) -> Dict[str, object]:
    """Run the full split -> upload workflow."""
    user_id = user_id.strip()
    order_id = order_id.strip()
    if not user_id or not order_id:
        raise ValueError("User ID and Order ID must be provided.")

    input_path = Path(input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    logger.info("Processing order %s for user %s", order_id, user_id)

    storage_client = SupabaseStorageClient(
        settings.supabase_url,
        settings.supabase_key,
        bucket=settings.storage_bucket,
        storage_prefix=settings.storage_prefix,
        service_role_key=settings.supabase_service_role_key,
    )

    model = import_file(str(input_path))
    parts = split_into_parts(model)

    with tempfile.TemporaryDirectory(prefix="cad-service-") as tmp_dir:
        exports = export_parts(parts, tmp_dir)

        original_remote_name = f"original{input_path.suffix or '.step'}"
        original_remote_path = storage_client.build_remote_path(
            user_id,
            order_id,
            original_remote_name,
        )

        logger.info("Uploading original file as %s", original_remote_path)
        storage_client.upload_file(input_path, original_remote_path)

        parts_remote_paths: List[str] = []
        for export in exports:
            remote_path = storage_client.build_remote_path(
                user_id,
                order_id,
                "parts",
                export.file_path.name,
            )
            storage_client.upload_file(export.file_path, remote_path)
            parts_remote_paths.append(remote_path)

    result = {
        "user_id": user_id,
        "order_id": order_id,
        "original": original_remote_path,
        "parts": parts_remote_paths,
    }

    logger.info("Workflow completed for order %s", order_id)
    return result


def run_and_dump_json(user_id: str, order_id: str, input_file: str, settings: Settings) -> str:
    """Execute the workflow and return a JSON string."""
    result = process_order(user_id, order_id, input_file, settings)
    json_payload = json.dumps(result, indent=2)
    logger.debug("Workflow JSON result: %s", json_payload)
    return json_payload
