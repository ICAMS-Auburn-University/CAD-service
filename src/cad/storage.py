import mimetypes
from pathlib import Path
from typing import Optional

from supabase import Client, create_client


class SupabaseStorageClient:
    """Thin wrapper around Supabase storage operations."""

    def __init__(
        self,
        url: str,
        key: str,
        bucket: str,
        storage_prefix: str = "cad-files",
        *,
        service_role_key: Optional[str] = None,
    ) -> None:
        self._client: Client = create_client(url, key)
        self._bucket = bucket
        self._prefix = storage_prefix.strip("/")

        if service_role_key:
            # Store for future enhancements (e.g., signed URLs or admin tasks)
            self._service_role_key = service_role_key
        else:
            self._service_role_key = None

    @property
    def client(self) -> Client:
        return self._client

    def build_remote_path(self, *segments: str) -> str:
        clean_segments = [segment.strip("/") for segment in segments if segment]
        return "/".join([self._prefix, *clean_segments])

    def upload_file(
        self, local_path: Path, remote_path: str, *, content_type: Optional[str] = None
    ) -> str:
        if not local_path.exists():
            raise FileNotFoundError(f"Cannot upload missing file: {local_path}")

        detected_type = (
            content_type or mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
        )

        with local_path.open("rb") as file_handle:
            response = self._client.storage.from_(self._bucket).upload(
                remote_path,
                file_handle,
                {"content-type": detected_type, "upsert": True},
            )

        if isinstance(response, dict) and response.get("error"):
            error_message = response["error"]["message"]
            raise RuntimeError(f"Supabase upload failed: {error_message}")
        return remote_path
