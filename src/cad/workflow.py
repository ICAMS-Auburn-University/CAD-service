from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import List

from core.config import Settings
from models import SplitJobResult, SplitPartFile
from cad.dxf import convert_step_to_dxf
from cad.layouts import build_part_layout
from cad.splitter import split_step_assembly
from cad.storage import SupabaseStorageClient

logger = logging.getLogger(__name__)


def process_order(
    user_id: str, order_id: str, input_file: str, settings: Settings
) -> SplitJobResult:
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

    with tempfile.TemporaryDirectory(prefix="cad-service-") as tmp_dir:
        export_dir = Path(tmp_dir) / "parts"
        parts = split_step_assembly(input_path, export_dir)
        layout = build_part_layout(parts)

        original_remote_name = f"original{input_path.suffix or '.step'}"
        original_remote_path = storage_client.build_remote_path(
            user_id,
            order_id,
            original_remote_name,
        )

        logger.info("Uploading original file as %s", original_remote_path)
        storage_client.upload_file(input_path, original_remote_path)

        part_payloads: List[SplitPartFile] = []
        for part in parts:
            dxf_path = convert_step_to_dxf(part.step_path, part.step_path.with_suffix(".dxf"))

            step_remote = storage_client.build_remote_path(
                user_id,
                order_id,
                "parts",
                *part.hierarchy,
                part.step_path.name,
            )
            storage_client.upload_file(part.step_path, step_remote)

            dxf_remote = storage_client.build_remote_path(
                user_id,
                order_id,
                "parts",
                *part.hierarchy,
                dxf_path.name,
            )
            storage_client.upload_file(dxf_path, dxf_remote)

            part_payloads.append(
                SplitPartFile(
                    name=part.name,
                    hierarchy=list(part.hierarchy),
                    step_path=step_remote,
                    dxf_path=dxf_remote,
                )
            )

    result = SplitJobResult(
        user_id=user_id,
        order_id=order_id,
        original=original_remote_path,
        parts=part_payloads,
        layout=layout,
    )

    logger.info("Workflow completed for order %s", order_id)
    return result


def run_and_dump_json(user_id: str, order_id: str, input_file: str, settings: Settings) -> str:
    """Execute the workflow and return a JSON string."""
    result = process_order(user_id, order_id, input_file, settings)
    json_payload = result.model_dump_json(indent=2)
    logger.debug("Workflow JSON result: %s", json_payload)
    return json_payload
