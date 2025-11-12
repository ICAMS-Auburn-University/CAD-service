from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterable, List, Sequence, Set

import FreeCAD
import Import

from models.types.split_part import SplitPart

logger = logging.getLogger(__name__)


def has_solid_shape(obj) -> bool:
    shape = getattr(obj, "Shape", None)
    if shape is None:
        return False
    try:
        return not shape.isNull()
    except Exception:
        return True


def sanitize_filename(name: str) -> str:
    return (
        "".join(ch for ch in name.strip().replace(" ", "_") if ch not in '<>:"/\\|?*')
        or "part"
    )


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_document(input_file: Path):
    abs_path = os.path.abspath(str(input_file))
    logger.info("Loading document: %s", abs_path)
    document = FreeCAD.newDocument("tmp")  # type: ignore[attr-defined]
    logger.info("Created new FreeCAD document: %s", document.Name)
    Import.insert(abs_path, document.Name)
    logger.info("Imported file into document: %s", abs_path)
    document.recompute()
    logger.info("Document loaded, objects: %d", len(document.Objects))
    return document


def get_root_objects(document) -> List:
    roots = getattr(document, "RootObjects", None)
    if roots:
        logger.info("Found %d root object(s) via doc.RootObjects", len(roots))
        return list(roots)
    derived = [obj for obj in document.Objects if not getattr(obj, "InList", [])]
    logger.info("Fallback: Found %d root candidates via empty InList", len(derived))
    return derived


def unique_preserving_order(seq: Sequence) -> List:
    seen: Set[int] = set()
    out: List = []
    for item in seq:
        key = id(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def find_group_parent(obj):
    for parent in getattr(obj, "InList", []) or []:
        if hasattr(parent, "Group") and obj in getattr(parent, "Group", []):
            return parent
    return None


def build_group_path(obj, root=None) -> List[str]:
    segments: List[str] = []
    current = obj
    while True:
        parent = find_group_parent(current)
        if parent is None or (root is not None and parent is root):
            break
        label = getattr(parent, "Label", getattr(parent, "Name", "")) or ""
        if label:
            segments.append(sanitize_filename(label))
        current = parent
    return list(reversed(segments))


def collect_subtree_exportables(node) -> List:
    items: List = []

    def visit(obj):
        if has_solid_shape(obj) and not getattr(obj, "Name", "").startswith("Unnamed"):
            items.append(obj)
        children = list(getattr(obj, "Group", [])) or list(getattr(obj, "OutList", []))
        for child in children:
            visit(child)

    visit(node)
    return unique_preserving_order(items)


def is_group_node(obj) -> bool:
    return hasattr(obj, "Group") or getattr(obj, "TypeId", "").startswith("App::Part")


def child_nodes(node) -> List:
    children = list(getattr(node, "Group", []))
    if children:
        return children
    out_list = list(getattr(node, "OutList", []))
    return [
        candidate
        for candidate in out_list
        if is_group_node(candidate) or hasattr(candidate, "Group")
    ]


def split_step_assembly(input_file: Path, output_dir: Path) -> List[SplitPart]:
    input_path = input_file.resolve()
    output_path = output_dir.resolve()
    ensure_directory(output_path)

    document = load_document(input_path)
    parts: List[SplitPart] = []
    logger.info("Starting split for %s", input_path.name)

    try:
        roots = get_root_objects(document)
        root_ref = roots[0] if len(roots) == 1 else None

        if root_ref is not None:
            start_nodes: Sequence = list(getattr(root_ref, "Group", [])) or list(
                getattr(root_ref, "OutList", [])
            )
        else:
            start_nodes = roots

        def sort_key(obj):
            return (
                getattr(obj, "Label", getattr(obj, "Name", "")) or "",
                getattr(obj, "Name", ""),
            )

        def walk(node, ancestors: Sequence[str]) -> None:
            label = getattr(node, "Label", getattr(node, "Name", "part"))
            safe_label = sanitize_filename(label or "part")
            rel_dirs = list(ancestors)
            node_dir = (
                output_path.joinpath(*rel_dirs, safe_label)
                if rel_dirs
                else output_path / safe_label
            )
            ensure_directory(node_dir)

            exportables = collect_subtree_exportables(node)
            if exportables:
                filepath = node_dir / f"{safe_label}.stp"
                Import.export(exportables, str(filepath))
                logger.info(
                    "Exported subgroup '%s' with %d parts -> %s",
                    label,
                    len(exportables),
                    filepath,
                )
                children = child_nodes(node)
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

    logger.info("Split completed for %s (%d parts)", input_path.name, len(parts))
    return parts
