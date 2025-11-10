from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterator


@contextmanager
def temporary_file(*, suffix: str = "") -> Iterator[Path]:
    """Yield a temporary file path and remove it when the context exits."""

    handle = NamedTemporaryFile(delete=False, suffix=suffix)
    handle.close()
    path = Path(handle.name)
    try:
        yield path
    finally:  # pragma: no cover - best-effort cleanup
        try:
            path.unlink(missing_ok=True)
        except Exception:
            # retain silent failure so API can still return useful information
            pass


__all__ = ["temporary_file"]
