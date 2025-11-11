from __future__ import annotations

import mimetypes
import os
from pathlib import Path

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
