"""FastAPI dependency wiring for the CAD service."""

from __future__ import annotations

from functools import lru_cache

from core.config import Settings


@lru_cache
def _load_settings() -> Settings:
    return Settings.from_env()


def get_settings() -> Settings:
    """Provide cached Settings instance for request handlers."""

    return _load_settings()


__all__ = ["get_settings"]
