from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional


@dataclass
class Settings:
    """Runtime configuration loaded from environment variables."""

    supabase_url: str
    supabase_key: str
    storage_bucket: str
    storage_prefix: str = "cad-files"
    supabase_service_role_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings from environment variables."""
        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_KEY", "")
        storage_bucket = os.environ.get("STORAGE_BUCKET", "")
        storage_prefix = os.environ.get("STORAGE_PREFIX", "cad-files")
        supabase_service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

        missing = [
            name
            for name, value in [
                ("SUPABASE_URL", supabase_url),
                ("SUPABASE_KEY", supabase_key),
                ("STORAGE_BUCKET", storage_bucket),
            ]
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise EnvironmentError(
                f"Missing required environment variables: {joined}. "
                "Ensure the container receives these values."
            )

        return cls(
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            storage_bucket=storage_bucket,
            storage_prefix=storage_prefix,
            supabase_service_role_key=supabase_service_role_key,
        )
