#!/usr/bin/env python3
"""
split.py — Recursively split a STEP assembly into STEP files by subgroup,
preserving the full hierarchy (subgroups within subgroups).

Usage:
  python split.py --input assembly.stp --outdir parts/

Notes:
  - Headless-friendly: does not depend on FreeCADGui / ViewObject.
  - Uses Import.insert to preserve grouping; traverses via `Group` to export
    every subgroup as its own STEP inside a mirrored folder structure.
  - Falls back to OutList traversal when Group is unavailable.
"""

import os
import sys
import argparse
import logging
from typing import List, Sequence, Set

import FreeCAD
import Import


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


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
    doc = FreeCAD.newDocument("tmp")
    Import.insert(abs_path, doc.Name)
    doc.recompute()
    logging.info("Document loaded, objects: %d", len(doc.Objects))
    return doc


def get_root_objects(doc) -> List:
    roots = getattr(doc, "RootObjects", None)
    if roots is not None and isinstance(roots, (list, tuple)) and len(roots) > 0:
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
        children = list(getattr(root, "Group", [])) or list(getattr(root, "OutList", []))
        return children
    return roots


def find_group_parent(obj):
    """Return the first parent whose Group contains obj, else None."""
    for p in getattr(obj, "InList", []) or []:
        if hasattr(p, "Group") and obj in getattr(p, "Group", []):
            return p
    return None


def build_group_path(obj, root=None) -> List[str]:
    """Build a list of ancestor labels using Group membership up to `root`.

    - If `root` is provided, stop before adding it.
    - If multiple parents exist, follows the first matching Group parent.
    - Returns labels from top-most ancestor down to the immediate parent.
    """
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
    """Collect exportable geometry objects under a node's subtree.

    - Traverses `Group` recursively when available (testing.py approach).
    - Falls back to `OutList` traversal if Group is not present.
    - Includes the node itself if it has a valid Shape.
    - Filters out objects without Shape, with Shape.isNull(), or names starting
      with 'Unnamed'.
    """
    items: List = []

    def visit(o):
        if has_solid_shape(o) and not getattr(o, "Name", "").startswith("Unnamed"):
            items.append(o)
        children = list(getattr(o, "Group", [])) or list(getattr(o, "OutList", []))
        for ch in children:
            visit(ch)

    visit(node)
    return unique_preserving_order(items)


def is_group_node(obj) -> bool:
    return hasattr(obj, "Group") or getattr(obj, "TypeId", "").startswith("App::Part")


def export_groups_recursive(doc, outdir: str) -> None:
    """Export every subgroup as a STEP in a mirrored folder hierarchy.

    - For a single-root document, starts from that root's direct children.
    - For multiple roots, starts from each root.
    - For each node with children, creates a folder path from its ancestor
      groups and places a STEP for that node's subtree into that folder.
    """
    roots = get_root_objects(doc)
    root_ref = roots[0] if len(roots) == 1 else None

    start_nodes: List = []
    if root_ref is not None:
        start_nodes = list(getattr(root_ref, "Group", [])) or list(getattr(root_ref, "OutList", []))
    else:
        start_nodes = roots

    def sort_key(o):
        return (getattr(o, "Label", getattr(o, "Name", "")) or "", getattr(o, "Name", ""))

    def walk(node):
        label = getattr(node, "Label", getattr(node, "Name", "")) or getattr(node, "Name", "node")
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
                "Exported subgroup '%s' with %d parts -> %s", label, len(exportables), filepath
            )
        else:
            logging.info("No exportable geometry under subgroup: %s", label)

        children = list(getattr(node, "Group", []))
        if not children:
            children = [
                c for c in getattr(node, "OutList", []) if is_group_node(c) or hasattr(c, "Group")
            ]
        for ch in sorted(children, key=sort_key):
            walk(ch)

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
    except Exception as e:
        logging.error("Failed to create output directory %s: %s", outdir, e)
        sys.exit(1)

    doc = load_document(input_file)

    # Always hierarchical subgroup export
    export_groups_recursive(doc, outdir)
    logging.info("Export complete.")
    FreeCAD.closeDocument(doc.Name)


if __name__ == "__main__":
    main()
