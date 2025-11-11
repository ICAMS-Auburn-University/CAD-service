from __future__ import annotations

import logging
import mimetypes
import os
import shutil
import tempfile
from pathlib import Path
from typing import BinaryIO, Iterable, List, Sequence, Set
from uuid import uuid4

from models import SplitJobResult, SplitPartFile
from models.types.split_part import SplitPart
from cad.dxf import convert_step_to_dxf
from cad.layouts import build_part_layout
from database import get_supabase

logger = logging.getLogger(__name__)

try:  # pragma: no cover - FreeCAD unavailable in tests
    import FreeCAD  # type: ignore
    import Import as FreeCADImport  # type: ignore
except Exception:  # pragma: no cover
    FreeCAD = None  # type: ignore
    FreeCADImport = None  # type: ignore


def _require_freecad() -> None:
    if FreeCAD is None or FreeCADImport is None:  # pragma: no cover
        raise RuntimeError("FreeCAD is not available in this environment.")


def _has_solid_shape(obj) -> bool:
    shape = getattr(obj, "Shape", None)
    if shape is None:
        return False
    try:
        return not shape.isNull()
    except Exception:
        return True


def _sanitize_filename(name: str) -> str:
    return "".join(ch for ch in name.strip().replace(" ", "_") if ch not in '<>:"/\\|?*') or "part"


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _load_document(input_file: Path):
    _require_freecad()
    abs_path = os.path.abspath(str(input_file))
    logger.info("Loading document: %s", abs_path)
    doc = FreeCAD.newDocument("tmp")  # type: ignore[attr-defined]
    FreeCADImport.insert(abs_path, doc.Name)  # type: ignore[attr-defined]
    doc.recompute()
    logger.info("Document loaded, objects: %d", len(doc.Objects))
    return doc


def _get_root_objects(doc) -> List:
    roots = getattr(doc, "RootObjects", None)
    if roots:
        logger.info("Found %d root object(s)", len(roots))
        return list(roots)
    derived = [obj for obj in doc.Objects if not getattr(obj, "InList", [])]
    logger.info("Fallback: Found %d root candidates via empty InList", len(derived))
    return derived


def _unique_preserving_order(seq: Sequence) -> List:
    seen: Set[int] = set()
    out: List = []
    for item in seq:
        key = id(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _find_group_parent(obj):
    for parent in getattr(obj, "InList", []) or []:
        if hasattr(parent, "Group") and obj in getattr(parent, "Group", []):
            return parent
    return None


def _build_group_path(obj, root=None) -> List[str]:
    segments: List[str] = []
    current = obj
    while True:
        parent = _find_group_parent(current)
        if parent is None or (root is not None and parent is root):
            break
        label = getattr(parent, "Label", getattr(parent, "Name", "")) or ""
        if label:
            segments.append(_sanitize_filename(label))
        current = parent
    return list(reversed(segments))


def _collect_subtree_exportables(node) -> List:
    items: List = []

    def visit(o):
        if _has_solid_shape(o) and not getattr(o, "Name", "").startswith("Unnamed"):
            items.append(o)
        children = list(getattr(o, "Group", [])) or list(getattr(o, "OutList", []))
        for child in children:
            visit(child)

    visit(node)
    return _unique_preserving_order(items)


def _is_group_node(obj) -> bool:
    return hasattr(obj, "Group") or getattr(obj, "TypeId", "").startswith("App::Part")


def _child_nodes(node) -> List:
    children = list(getattr(node, "Group", []))
    if children:
        return children
    out_list = list(getattr(node, "OutList", []))
    return [candidate for candidate in out_list if _is_group_node(candidate) or hasattr(candidate, "Group")]


def _split_step_assembly(input_file: Path, output_dir: Path) -> List[SplitPart]:
    document = _load_document(input_file)
    parts: List[SplitPart] = []
    logger.info("Starting split for %s", input_file.name)

    try:
        roots = _get_root_objects(document)
        root_ref = roots[0] if len(roots) == 1 else None

        start_nodes: Sequence = (
            list(getattr(root_ref, "Group", [])) or list(getattr(root_ref, "OutList", []))
            if root_ref is not None
            else roots
        )

        def sort_key(obj):
            return (getattr(obj, "Label", getattr(obj, "Name", "")) or "", getattr(obj, "Name", ""))

        def walk(node, ancestors: Sequence[str]) -> None:
            label = getattr(node, "Label", getattr(node, "Name", "part"))
            safe_label = _sanitize_filename(label or "part")
            rel_dirs = list(ancestors)
            node_dir = output_dir.joinpath(*rel_dirs, safe_label) if rel_dirs else output_dir / safe_label
            _ensure_directory(node_dir)

            exportables = _collect_subtree_exportables(node)
            if exportables:
                filepath = node_dir / f"{safe_label}.stp"
                FreeCADImport.export(exportables, str(filepath))
                logger.info("Exported subgroup '%s' -> %s", label, filepath)
                children = _child_nodes(node)
                parts.append(
                    SplitPart(
                        name=safe_label,
                        hierarchy=tuple(rel_dirs),
                        has_children=bool(children),
                        step_path=filepath,
                    )
                )
                for child in sorted(children, key=sort_key):
                    walk(child, (*rel_dirs, safe_label))
            else:
                logger.info("No exportable geometry under subgroup: %s", label)

        for node in sorted(start_nodes, key=sort_key):
            walk(node, ())

        if not parts:
            raise RuntimeError("No exportable parts were detected in the CAD model.")
    finally:
        FreeCAD.closeDocument(document.Name)  # type: ignore[attr-defined]
        logger.info("Closed FreeCAD document %s", document.Name)

    logger.info("Split completed for %s (%d parts)", input_file.name, len(parts))
    return parts


def _build_remote_path(*segments: str) -> str:
    bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "").strip("/")
    if not bucket:
        raise RuntimeError("SUPABASE_STORAGE_BUCKET is not configured.")
    clean = [segment.strip("/") for segment in segments if segment]
    return "/".join([bucket, *clean])


def _upload_file(local_path: Path, remote_path: str) -> str:
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
    logger.info("Uploaded %s to %s", local_path.name, remote_path)
    return remote_path


def process_uploaded_cad(
    user_id: str,
    order_id: str,
    filename: str,
    file_stream: BinaryIO,
) -> SplitJobResult:
    user_id = user_id.strip()
    order_id = order_id.strip()
    if not user_id or not order_id:
        raise ValueError("User ID and Order ID must be provided.")

    safe_name = Path(filename or "upload.step").name
    temp_dir = Path(tempfile.mkdtemp(prefix="cad-service-"))
    temp_path = temp_dir / f"{uuid4()}_{safe_name}"

    try:
        with temp_path.open("wb") as destination:
            shutil.copyfileobj(file_stream, destination)
        logger.info("Saved upload for user %s order %s to %s", user_id, order_id, temp_path)

        parts_dir = temp_dir / "parts"
        parts = _split_step_assembly(temp_path, parts_dir)
        layout = build_part_layout(parts)

        original_remote_path = _build_remote_path(user_id, order_id, f"original{temp_path.suffix}")
        _upload_file(temp_path, original_remote_path)

        part_payloads: List[SplitPartFile] = []
        for part in parts:
            dxf_path = convert_step_to_dxf(part.step_path, part.step_path.with_suffix(".dxf"))

            step_remote = _build_remote_path(
                user_id,
                order_id,
                "parts",
                *part.hierarchy,
                part.step_path.name,
            )
            _upload_file(part.step_path, step_remote)

            dxf_remote = _build_remote_path(
                user_id,
                order_id,
                "parts",
                *part.hierarchy,
                dxf_path.name,
            )
            _upload_file(dxf_path, dxf_remote)
            logger.info("Uploaded part %s with hierarchy %s", part.name, "/".join(part.hierarchy))

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

        logger.info("Finished order %s for user %s (%d parts)", order_id, user_id, len(part_payloads))
        return result
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
