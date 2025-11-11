import mimetypes
import tempfile
from pathlib import Path
from typing import List

import os
from models import SplitJobResult, SplitPartFile
from cad.dxf import convert_step_to_dxf
from cad.layouts import build_part_layout
from cad.splitter import split_step_assembly
from database import get_supabase


def build_remote_path(*segments: str) -> str:
    prefix = os.getenv("SUPABASE_STORAGE_BUCKET").strip("/")
    clean = [segment.strip("/") for segment in segments if segment]
    return "/".join([prefix, *clean])


def upload_file(local_path: Path, remote_path: str) -> str:
    if not local_path.exists():
        raise FileNotFoundError(f"Cannot upload missing file: {local_path}")

    content_type = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
    client = get_supabase()
    with local_path.open("rb") as file_handle:
        response = client.storage.from_(os.getenv("SUPABASE_STORAGE_BUCKET")).upload(
            remote_path,
            file_handle,
            {"content-type": content_type, "upsert": True},
        )

    if isinstance(response, dict) and response.get("error"):
        raise RuntimeError(f"Supabase upload failed: {response['error']['message']}")
    return remote_path


def process_order(user_id: str, order_id: str, input_path: Path) -> SplitJobResult:
    with tempfile.TemporaryDirectory(prefix="cad-service-") as tmp_dir:
        export_dir = Path(tmp_dir) / "parts"
        parts = split_step_assembly(input_path, export_dir)
        layout = build_part_layout(parts)

        original_remote_name = f"original{input_path.suffix}"
        original_remote_path = build_remote_path(
            user_id,
            order_id,
            original_remote_name,
        )

        upload_file(input_path, original_remote_path)

        part_payloads: List[SplitPartFile] = []
        for part in parts:
            dxf_path = convert_step_to_dxf(part.step_path, part.step_path.with_suffix(".dxf"))

            step_remote = build_remote_path(
                user_id,
                order_id,
                "parts",
                *part.hierarchy,
                part.step_path.name,
            )
            upload_file(part.step_path, step_remote)

            dxf_remote = build_remote_path(
                user_id,
                order_id,
                "parts",
                *part.hierarchy,
                dxf_path.name,
            )
            upload_file(dxf_path, dxf_remote)

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

    return result
