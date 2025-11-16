from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import re
import unicodedata
from pathlib import Path
from typing import BinaryIO, List
from uuid import uuid4

from loguru import logger

from models import SplitJobResult, SplitPartFile
from database import ensure_order_exists, record_split_part, upload_file_to_supabase

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SPLITTER_SCRIPT = PROJECT_ROOT / "scripts" / "split_stp.py"
SYSTEM_PYTHON = os.getenv("SYSTEM_PYTHON_PATH", "/usr/bin/python3")
SPLITTER_TIMEOUT = int(os.getenv("SPLITTER_TIMEOUT_SECONDS", "900"))


_SEGMENT_INVALID_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _clean_segment(value: str, fallback: str) -> str:
    """Normalize user-supplied identifiers for storage paths."""

    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    stripped = ascii_only.strip().strip("/\\")
    sanitized = _SEGMENT_INVALID_CHARS.sub("_", stripped)
    collapsed = re.sub(r"_+", "_", sanitized).strip("_")
    return collapsed or fallback


def _persist_upload(file_stream: BinaryIO, original_name: str, temp_dir: Path) -> Path:
    safe_name = Path(original_name or "upload.step").name
    destination = temp_dir / f"{uuid4()}_{safe_name}"
    with destination.open("wb") as target:
        shutil.copyfileobj(file_stream, target)
    logger.info("Saved upload to {}", destination)
    return destination


def _run_splitter(input_file: Path, output_dir: Path) -> None:
    if not input_file.exists():
        raise FileNotFoundError(f"Input STEP file not found: {input_file}")
    if not SPLITTER_SCRIPT.exists():
        raise FileNotFoundError(f"Splitter script not found at {SPLITTER_SCRIPT}")

    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        SYSTEM_PYTHON,
        str(SPLITTER_SCRIPT),
        "--input",
        str(input_file),
        "--outdir",
        str(output_dir),
    ]

    logger.info("Running splitter: {}", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SPLITTER_TIMEOUT,
            check=False,
        )
    except FileNotFoundError as exc:
        logger.error("System python executable not found: {}", SYSTEM_PYTHON)
        raise RuntimeError("System python executable not found.") from exc
    except subprocess.TimeoutExpired as exc:
        logger.error("Splitter timed out after {} seconds", exc.timeout)
        raise RuntimeError("STEP splitter timed out.") from exc
    except subprocess.SubprocessError as exc:
        logger.error("Splitter subprocess raised an error: {}", exc)
        raise RuntimeError("STEP splitter failed to execute.") from exc

    if result.stdout:
        logger.debug("Splitter stdout:\n{}", result.stdout)
    if result.stderr:
        logger.debug("Splitter stderr:\n{}", result.stderr)

    if result.returncode != 0:
        logger.error(
            "Splitter exited with {}. See stderr above for details.", result.returncode
        )
        raise RuntimeError("STEP splitter failed.")

    logger.info("Splitter completed successfully.")


def _collect_step_files(parts_dir: Path) -> List[Path]:
    if not parts_dir.exists():
        return []
    return sorted(parts_dir.rglob("*.stp"))


def _hierarchy_for(part_path: Path, base_dir: Path) -> List[str]:
    try:
        relative = part_path.parent.relative_to(base_dir)
    except ValueError:
        return []
    if str(relative) in (".", ""):
        return []
    return [segment for segment in relative.parts if segment not in (".", "")]


def _build_remote_key(user_id: str, order_id: str, *segments: str) -> str:
    cleaned_segments = [
        _clean_segment(user_id, "user"),
        _clean_segment(order_id, "order"),
    ]
    for index, segment in enumerate(segment for segment in segments if segment):
        fallback = f"segment_{index + 1}"
        cleaned_segments.append(_clean_segment(segment, fallback))
    return "/".join(segment for segment in cleaned_segments if segment)


def process_uploaded_cad(
    user_id: str,
    order_id: str,
    filename: str,
    file_stream: BinaryIO,
) -> SplitJobResult:
    user_id = user_id.strip()
    order_id = order_id.strip()
    if not user_id or not order_id:
        raise ValueError("user_id and order_id must be provided.")

    try:
        ensure_order_exists(order_id=order_id, user_id=user_id)
    except Exception as exc:
        logger.error(
            "Failed to ensure order {} exists for user {}: {}",
            order_id,
            user_id,
            exc,
        )
        raise

    temp_dir = Path(tempfile.mkdtemp(prefix="cad-service-"))
    try:
        input_path = _persist_upload(file_stream, filename, temp_dir)
        parts_dir = temp_dir / "parts"

        _run_splitter(input_path, parts_dir)
        part_files = _collect_step_files(parts_dir)
        if not part_files:
            raise RuntimeError("No STEP parts were produced by the splitter.")

        original_remote_key = _build_remote_key(
            user_id, order_id, "original", input_path.name
        )
        original_storage_path = upload_file_to_supabase(input_path, original_remote_key)

        part_payloads: List[SplitPartFile] = []
        for part_path in part_files:
            hierarchy = _hierarchy_for(part_path, parts_dir)
            remote_key = _build_remote_key(
                user_id,
                order_id,
                "parts",
                *hierarchy,
                part_path.name,
            )
            storage_path = upload_file_to_supabase(part_path, remote_key)
            safe_name = _clean_segment(
                part_path.name, f"{part_path.stem or 'part'}.stp"
            )

            try:
                record_split_part(
                    order_id=order_id,
                    name=safe_name,
                    storage_path=storage_path,
                    hierarchy=hierarchy,
                    metadata=None,
                )
            except Exception as exc:
                logger.error(
                    "Failed to record split part metadata for {} / {}: {}",
                    order_id,
                    part_path.name,
                    exc,
                )
                raise

            part_payloads.append(
                SplitPartFile(
                    name=part_path.stem,
                    hierarchy=hierarchy,
                    storage_path=storage_path,
                )
            )
            logger.info("Uploaded part {} -> {}", part_path.name, storage_path)

        logger.info(
            "Split completed for user {} order {} ({} parts)",
            user_id,
            order_id,
            len(part_payloads),
        )
        return SplitJobResult(
            user_id=user_id,
            order_id=order_id,
            original=original_storage_path,
            parts=part_payloads,
        )
    finally:
        try:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as exc:  # pragma: no cover - best effort cleanup
            logger.warning("Failed to clean temp dir {}: {}", temp_dir, exc)
