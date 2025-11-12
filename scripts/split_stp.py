import argparse
import logging
import os
import sys
from typing import List, Sequence, Set

import FreeCAD
import Import


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )


def has_solid_shape(obj) -> bool:
    shape = getattr(obj, "Shape", None)
    if shape is None:
        return False
    try:
        return not shape.isNull()
    except Exception:
        return True


def sanitize_filename(name: str) -> str:
    s = name.strip().replace(" ", "_")
    forbidden = '<>:"/\\|?*'
    return "".join(ch for ch in s if ch not in forbidden)


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def load_document(input_file: str):
    abs_path = os.path.abspath(input_file)
    logging.info("Loading document: %s", abs_path)
    doc = FreeCAD.newDocument("tmp")  # type: ignore[attr-defined]
    Import.insert(abs_path, doc.Name)
    doc.recompute()
    logging.info("Document loaded, objects: %d", len(doc.Objects))
    return doc


def get_root_objects(doc) -> List:
    roots = getattr(doc, "RootObjects", None)
    if roots:
        logging.info("Found %d root object(s) via doc.RootObjects", len(roots))
        return list(roots)
    derived = [o for o in doc.Objects if not getattr(o, "InList", [])]
    logging.info("Fallback: Found %d root candidates via empty InList", len(derived))
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


def get_direct_children(doc) -> List:
    roots = get_root_objects(doc)
    if not roots:
        return []
    if len(roots) == 1:
        root = roots[0]
        children = list(getattr(root, "Group", [])) or list(
            getattr(root, "OutList", [])
        )
        return children
    return roots


def find_group_parent(obj):
    """Return the first parent whose Group contains obj, else None."""

    for parent in getattr(obj, "InList", []) or []:
        if hasattr(parent, "Group") and obj in getattr(parent, "Group", []):
            return parent
    return None


def build_group_path(obj, root=None) -> List[str]:
    """Build a list of ancestor labels using Group membership up to `root`."""

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
    """Collect exportable geometry objects under a node's subtree."""

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


def export_groups_recursive(doc, outdir: str) -> None:
    """Export every subgroup as a STEP in a mirrored folder hierarchy."""

    roots = get_root_objects(doc)
    root_ref = roots[0] if len(roots) == 1 else None

    if root_ref is not None:
        start_nodes = list(getattr(root_ref, "Group", [])) or list(
            getattr(root_ref, "OutList", [])
        )
    else:
        start_nodes = roots

    def sort_key(obj):
        return (
            getattr(obj, "Label", getattr(obj, "Name", "")) or "",
            getattr(obj, "Name", ""),
        )

    def walk(node):
        label = getattr(node, "Label", getattr(node, "Name", "")) or getattr(
            node, "Name", "node"
        )
        rel_dirs = build_group_path(node, root=root_ref)
        node_dir = (
            os.path.join(outdir, *rel_dirs, sanitize_filename(label))
            if rel_dirs
            else os.path.join(outdir, sanitize_filename(label))
        )
        ensure_dir(node_dir)

        exportables = collect_subtree_exportables(node)
        if exportables:
            filepath = os.path.join(node_dir, f"{sanitize_filename(label)}.stp")
            Import.export(exportables, filepath)
            logging.info(
                "Exported subgroup '%s' with %d parts -> %s",
                label,
                len(exportables),
                filepath,
            )
        else:
            logging.info("No exportable geometry under subgroup: %s", label)

        children = list(getattr(node, "Group", []))
        if not children:
            children = [
                child
                for child in getattr(node, "OutList", [])
                if is_group_node(child) or hasattr(child, "Group")
            ]
        for child in sorted(children, key=sort_key):
            walk(child)

    for node in sorted(start_nodes, key=sort_key):
        walk(node)


def main() -> None:
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Split STEP assembly into subgroup STEP files (hierarchical)"
    )
    parser.add_argument("--input", required=True, help="Input assembly STEP file")
    parser.add_argument("--outdir", required=True, help="Output directory for parts")
    args = parser.parse_args()

    input_file = args.input
    outdir = args.outdir

    if not os.path.isfile(input_file):
        logging.error("Input file not found: %s", input_file)
        sys.exit(1)

    try:
        os.makedirs(outdir, exist_ok=True)
    except Exception as exc:
        logging.error("Failed to create output directory %s: %s", outdir, exc)
        sys.exit(1)

    doc = load_document(input_file)

    export_groups_recursive(doc, outdir)
    logging.info("Export complete.")
    FreeCAD.closeDocument(doc.Name)


if __name__ == "__main__":
    main()
