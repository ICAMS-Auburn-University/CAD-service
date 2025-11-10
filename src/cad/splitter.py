from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Sequence, Set

import FreeCAD
import Import

from cad.types import SplitPart


def sanitize_filename(name: str) -> str:
    clean = name.strip().replace(" ", "_")
    forbidden = '<>:"/\\|?*'
    return "".join(ch for ch in clean if ch not in forbidden) or "part"


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_document(input_file: Path):
    abs_path = input_file.resolve()
    document = FreeCAD.newDocument(f"tmp_{os.getpid()}")  # type: ignore[attr-defined]
    Import.insert(str(abs_path), document.Name)
    document.recompute()
    return document


def get_root_objects(document) -> List:
    roots = getattr(document, "RootObjects", None)
    if roots:
        return list(roots)
    derived = [obj for obj in document.Objects if not getattr(obj, "InList", [])]
    return derived


def unique_preserving_order(items: Iterable) -> List:
    seen: Set[int] = set()
    ordered: List = []
    for item in items:
        marker = id(item)
        if marker in seen:
            continue
        seen.add(marker)
        ordered.append(item)
    return ordered


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
        if parent is None:
            break
        if root is not None and parent is root:
            break
        label = getattr(parent, "Label", getattr(parent, "Name", "")) or ""
        if label:
            segments.append(sanitize_filename(label))
        current = parent
    return list(reversed(segments))


def collect_subtree_exportables(node) -> List:
    collected: List = []

    def visit(obj):
        shape = getattr(obj, "Shape", None)
        if shape is not None:
            try:
                if not shape.isNull():
                    collected.append(obj)
            except Exception:
                collected.append(obj)
        children = list(getattr(obj, "Group", [])) or list(getattr(obj, "OutList", []))
        for child in children:
            visit(child)

    visit(node)
    return unique_preserving_order(collected)


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
    """Split the STEP assembly into hierarchical STEP exports."""

    input_path = Path(input_file).resolve()
    output_path = Path(output_dir).resolve()
    ensure_directory(output_path)

    document = load_document(input_path)
    parts: List[SplitPart] = []

    try:
        roots = get_root_objects(document)
        root_reference = roots[0] if len(roots) == 1 else None

        if root_reference is not None:
            start_nodes: Sequence = list(getattr(root_reference, "Group", [])) or list(
                getattr(root_reference, "OutList", [])
            )
        else:
            start_nodes = roots

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
                step_file = node_dir / f"{safe_label}.stp"
                Import.export(exportables, str(step_file))
                children = child_nodes(node)
                parts.append(
                    SplitPart(
                        name=safe_label,
                        hierarchy=tuple(rel_dirs),
                        has_children=bool(children),
                        step_path=step_file,
                    )
                )
                for child in children:
                    walk(child, (*rel_dirs, safe_label))

        for node in start_nodes:
            walk(node, ())

        if not parts:
            raise RuntimeError("No exportable parts were detected in the CAD model.")
    finally:
        FreeCAD.closeDocument(document.Name)  # type: ignore[attr-defined]

    return parts
