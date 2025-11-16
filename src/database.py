from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

from loguru import logger
from supabase import Client, create_client

_supabase: Client | None = None


def init_supabase() -> Client:
    """Initialize the Supabase client using environment variables."""

    global _supabase
    project_url = os.getenv("SUPABASE_PROJECT_URL")
    api_key = os.getenv("SUPABASE_API_KEY")

    if not project_url or not api_key:
        raise ValueError(
            "SUPABASE_PROJECT_URL and SUPABASE_API_KEY environment variables must be set"
        )

    _supabase = create_client(project_url, api_key)
    return _supabase


def get_supabase() -> Client:
    """Return an initialized Supabase client, creating it on demand."""

    global _supabase
    if _supabase is None:
        _supabase = init_supabase()
    return _supabase


def _response_data(response: Any) -> list[Mapping[str, Any]]:
    """Extract the .data payload from a Supabase response object."""

    if response is None:
        return []
    data = getattr(response, "data", None)
    if data is None and isinstance(response, Mapping):
        data = response.get("data")
    if data is None:
        return []
    if isinstance(data, list):
        return data
    return [data]


def ensure_order_exists(order_id: str, user_id: str) -> Mapping[str, Any]:
    """Verify the order row already exists; raise if it does not."""

    order_id = (order_id or "").strip()
    user_id = (user_id or "").strip()
    if not order_id or not user_id:
        raise ValueError("order_id and user_id are required to verify an order.")

    client = get_supabase()

    try:
        response = (
            client.table("Orders").select("id").eq("id", order_id).limit(1).execute()
        )
    except Exception as exc:  # pragma: no cover - network issues
        logger.error("Order lookup failed for {}: {}", order_id, exc)
        raise

    existing = _response_data(response)
    if not existing:
        raise ValueError(
            f"Order {order_id} for user {user_id} does not exist in Supabase."
        )
    return existing[0]


def upload_file_to_supabase(
    local_path: Path,
    remote_path: str,
    *,
    content_type: str | None = None,
    upsert: bool = True,
) -> str:
    """Upload a file to the configured Supabase storage bucket.

    Args:
        local_path: Path to the local file that should be uploaded.
        remote_path: Object path inside the bucket (no leading slash).
        content_type: Optional explicit MIME type.
        upsert: Whether to overwrite existing files.

    Returns:
        The combined bucket/path string for the stored file.
    """

    bucket = (os.getenv("SUPABASE_STORAGE_BUCKET") or "").strip("/")
    if not bucket:
        raise RuntimeError("SUPABASE_STORAGE_BUCKET environment variable must be set.")
    if not local_path.exists():
        raise FileNotFoundError(f"Cannot upload missing file: {local_path}")

    normalized_remote = remote_path.strip("/")
    if not normalized_remote:
        raise ValueError("remote_path must not be empty.")

    client = get_supabase()
    mime = (
        content_type
        or mimetypes.guess_type(local_path.name)[0]
        or "application/octet-stream"
    )

    try:
        with local_path.open("rb") as file_handle:
            response = client.storage.from_(bucket).upload(
                normalized_remote,
                file_handle,
                {"content-type": mime, "x-upsert": "true" if upsert else "false"},
            )
    except Exception as exc:  # pragma: no cover - network issues
        logger.error("Supabase upload raised an exception: {}", exc)
        raise

    if isinstance(response, dict) and response.get("error"):
        message = response["error"].get("message", "Unknown Supabase upload error")
        logger.error("Supabase upload failed for {}: {}", normalized_remote, message)
        raise RuntimeError(f"Supabase upload failed: {message}")

    stored_path = f"{bucket}/{normalized_remote}"
    logger.info("Uploaded {} to {}", local_path.name, stored_path)
    return stored_path


def record_split_part(
    *,
    order_id: str,
    name: str,
    storage_path: str,
    hierarchy: Sequence[str] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Persist part metadata to the split_parts table, avoiding duplicates."""

    order_id = order_id.strip()
    storage_path = storage_path.strip()
    if not order_id or not storage_path:
        raise ValueError("order_id and storage_path must be provided for split parts.")

    client = get_supabase()
    hierarchy_list = list(hierarchy or [])
    payload: dict[str, Any] = {
        "id": str(uuid4()),
        "order_id": order_id,
        "name": name.strip() or Path(storage_path).name,
        "storage_path": storage_path,
        "hierarchy": hierarchy_list,
        "metadata": metadata,
    }

    try:
        existing_response = (
            client.table("split_parts")
            .select("id")
            .eq("order_id", order_id)
            .eq("storage_path", storage_path)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # pragma: no cover - network issues
        logger.error(
            "Failed checking existing split part for order {} and path {}: {}",
            order_id,
            storage_path,
            exc,
        )
        raise

    existing_data = _response_data(existing_response)
    if existing_data:
        return existing_data[0]

    try:
        insert_response = client.table("split_parts").insert(payload).execute()
    except Exception as exc:  # pragma: no cover - network issues
        logger.error(
            "Failed recording split part {} for order {}: {}",
            storage_path,
            order_id,
            exc,
        )
        raise

    inserted = _response_data(insert_response)
    return inserted[0] if inserted else payload
