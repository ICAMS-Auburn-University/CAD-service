from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional

logger = logging.getLogger(__name__)

try:
    import FreeCAD  # type: ignore
    import FreeCAD as App  # type: ignore
    import Import  # type: ignore

    FREECAD_AVAILABLE = True
except Exception:  # pragma: no cover - FreeCAD is not available in unit tests
    FREECAD_AVAILABLE = False
    FreeCAD = None  # type: ignore
    App = None  # type: ignore
    Import = None  # type: ignore


@dataclass
class ModelObject:
    """Representation of the imported CAD document."""

    source_path: Path
    document: Optional[Any] = None
    precomputed_parts: Optional[Iterable[Any]] = None


@dataclass
class PartMetadata:
    """Metadata for a single part extracted from the model."""

    index: int
    name: str
    raw_object: Any


@dataclass
class ExportResult:
    """Information about an exported part file."""

    part: PartMetadata
    file_path: Path
    size_bytes: int


def import_file(input_path: str) -> ModelObject:
    """Import a STEP/IGES file into FreeCAD."""
    source = Path(input_path)
    if not source.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    logger.info("Importing CAD file: %s", source)

    if not FREECAD_AVAILABLE:
        logger.warning(
            "FreeCAD Python modules are unavailable in this environment. "
            "Only mock-based workflows will function."
        )
        return ModelObject(source_path=source, document=None)

    # START FREECAD IMPORT PLACEHOLDER
    document = App.newDocument()
    Import.open(str(source))
    document.recompute()
    # END FREECAD IMPORT PLACEHOLDER

    return ModelObject(source_path=source, document=document)


def split_into_parts(model: ModelObject) -> List[PartMetadata]:
    """Split the model into individual parts and return metadata."""
    logger.info("Splitting model into parts: %s", model.source_path)

    if model.precomputed_parts is not None:
        parts = [
            PartMetadata(index=index, name=f"part_{index+1}", raw_object=raw)
            for index, raw in enumerate(model.precomputed_parts)
        ]
        logger.debug("Using precomputed parts: %s", [part.name for part in parts])
        return parts

    if not FREECAD_AVAILABLE or model.document is None:
        raise RuntimeError(
            "FreeCAD is not available, and no precomputed parts were provided."
        )

    # START FREECAD SPLIT PLACEHOLDER
    parts_container = []
    objects = model.document.Objects  # type: ignore[attr-defined]
    for index, obj in enumerate(objects):
        if getattr(obj, "isDerivedFrom", lambda _: False)("Part::Feature"):
            parts_container.append(PartMetadata(index=index, name=obj.Label, raw_object=obj))
    # END FREECAD SPLIT PLACEHOLDER

    if not parts_container:
        raise RuntimeError("No parts were detected in the CAD model.")

    logger.info("Split produced %d part(s).", len(parts_container))
    return parts_container


def export_parts(parts: List[PartMetadata], output_folder: str) -> List[ExportResult]:
    """Export each part to an individual STEP file."""
    target_dir = Path(output_folder)
    target_dir.mkdir(parents=True, exist_ok=True)

    results: List[ExportResult] = []

    for part in parts:
        filename = f"{part.name or f'part_{part.index+1}'}.step"
        sanitized = filename.replace(" ", "_")
        destination = target_dir / sanitized

        if FREECAD_AVAILABLE:
            # START FREECAD EXPORT PLACEHOLDER
            Import.export([part.raw_object], str(destination))
            # END FREECAD EXPORT PLACEHOLDER
        else:
            # Create an empty placeholder so the workflow can proceed in tests.
            destination.write_text(
                f"Placeholder export for {part.name or part.index}", encoding="utf-8"
            )

        size_bytes = destination.stat().st_size if destination.exists() else 0
        logger.debug("Exported part %s to %s (%d bytes).", part.name, destination, size_bytes)
        results.append(ExportResult(part=part, file_path=destination, size_bytes=size_bytes))

    logger.info("Exported %d part(s) to %s.", len(results), target_dir)
    return results
