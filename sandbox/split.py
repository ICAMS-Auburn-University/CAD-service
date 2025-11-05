#!/usr/bin/env python3
"""
split.py — Split a STEP assembly into separate STEP files.

Usage:
  - First-level children only (default):
      python split.py --input Rocky_House.stp --outdir parts/

  - Full split (all descendants):
      python split.py --input Rocky_House.stp --outdir parts/ --full

Notes:
  - Headless-friendly: does not depend on FreeCADGui / ViewObject.
  - Uses FreeCAD Object relationships (OutList / OutListRecursive) to
    navigate the assembly tree. See FreeCAD Wiki / Forum for API details.
"""

import os
import sys
import argparse
import logging
from typing import Iterable, List, Optional, Sequence, Set

try:
    import FreeCAD  # FreeCAD App module
    import Part
    # FreeCADGui is optional in headless mode; do not require it.
    try:
        import FreeCADGui  # noqa: F401
    except Exception:  # pragma: no cover - best‑effort detection only
        FreeCADGui = None  # type: ignore
except ImportError as e:
    # Avoid raising before logging is configured; print to stderr.
    print(f"[ERROR] FreeCAD modules could not be imported: {e}", file=sys.stderr)
    sys.exit(1)


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def has_solid_shape(obj) -> bool:
    """Return True if the object has a non-null Shape suitable for export.

    - Checks presence of `Shape` attribute.
    - Calls `Shape.isNull()` when available to exclude empty shapes.
    """
    shape = getattr(obj, "Shape", None)
    if shape is None:
        return False
    try:
        return not shape.isNull()
    except Exception:
        # Some objects may not implement isNull(); assume valid if Shape exists
        return True


def sanitize_filename(name: str) -> str:
    s = name.strip().replace(" ", "_")
    # Remove characters that are problematic on various filesystems
    forbidden = '<>:"/\\|?*'
    return "".join(ch for ch in s if ch not in forbidden)


def load_document(input_file: str):
    """Create a new FreeCAD document and insert the STEP file.

    Uses Part.insert to import STEP geometry. The document is recomputed
    afterwards. Logs object count for visibility.
    """
    abs_path = os.path.abspath(input_file)
    logging.info("Loading document: %s", abs_path)
    doc = FreeCAD.newDocument("tmp")
    # Import the STEP file into this document
    Part.insert(abs_path, doc.Name)
    doc.recompute()
    logging.info("Document loaded, objects count: %d", len(doc.Objects))
    return doc


def get_root_objects(doc) -> List:
    """Return top-level root objects of the document.

    Prefer `doc.RootObjects` when available. Otherwise, compute objects
    that have an empty `InList` (no parents). See FreeCAD API: Document
    object relationships and dependency graph.
    """
    roots = getattr(doc, "RootObjects", None)
    if roots is not None and isinstance(roots, (list, tuple)) and len(roots) > 0:
        return list(roots)
    # Fallback: derive roots as objects with no parents (InList empty)
    derived = [o for o in doc.Objects if not getattr(o, "InList", [])]
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
    """Collect first-level children under the document's root assembly.

    - If exactly one root exists: return `root.OutList` (direct children).
      (FreeCAD API: `obj.OutList` lists direct dependents/children.)
    - If multiple roots exist: treat each root as a child of an implicit
      super-root; include roots themselves if exportable, otherwise include
      their own direct children.
    - Always filter to exportable geometry via `has_solid_shape()` and name.
    """
    roots = get_root_objects(doc)
    if not roots:
        return []

    candidates: List = []
    if len(roots) == 1:
        root = roots[0]
        # Using obj.OutList to find direct children (FreeCAD Object API)
        children = list(getattr(root, "OutList", []))
        candidates.extend(children)
    else:
        # Multiple independent roots at the document level.
        for root in roots:
            if has_solid_shape(root):
                candidates.append(root)
            else:
                candidates.extend(getattr(root, "OutList", []))

    # Filter and de-duplicate while keeping order
    filtered = []
    for o in unique_preserving_order(candidates):
        if not has_solid_shape(o):
            continue
        if getattr(o, "Name", "").startswith("Unnamed"):
            continue
        filtered.append(o)
    return filtered


def get_all_parts(doc) -> List:
    """Collect all exportable parts in the document (full recursive split).

    Uses `root.OutListRecursive` to walk all descendants. See FreeCAD API
    for `OutListRecursive` behavior. Falls back to scanning all `doc.Objects`
    if needed. Filters geometry via `has_solid_shape()`.
    """
    roots = get_root_objects(doc)
    collected: List = []
    if roots:
        for root in roots:
            rec: Iterable = getattr(root, "OutListRecursive", [])
            collected.extend(list(rec) or [])
    if not collected:
        # Fallback: include any object in the document that has solid shape
        collected = list(doc.Objects)

    out: List = []
    for o in unique_preserving_order(collected):
        if not has_solid_shape(o):
            continue
        if getattr(o, "Name", "").startswith("Unnamed"):
            continue
        out.append(o)
    return out


def export_component(obj, output_path: str) -> bool:
    """Export a single object to STEP.

    Prefers `Import.export([obj], path)` (FreeCAD Import module) and falls
    back to `Part.export([obj], path)` if needed. Returns True on success.
    """
    try:
        import Import  # provided by FreeCAD; headless-friendly exporter
        Import.export([obj], output_path)
        return True
    except Exception as e1:
        logging.debug("Import.export failed for %s: %s", getattr(obj, "Name", "<obj>"), e1)
        try:
            Part.export([obj], output_path)
            return True
        except Exception as e2:
            logging.error("Export failed for %s: %s", getattr(obj, "Name", "<obj>"), e2)
            return False


def main() -> None:
    setup_logging()

    parser = argparse.ArgumentParser(description="Split STEP assembly into separate STEP files")
    parser.add_argument("--input", required=True, help="Input assembly STEP file")
    parser.add_argument("--outdir", required=True, help="Output directory for parts")
    parser.add_argument("--full", action="store_true", help="Export all descendants (full split)")
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

    try:
        if args.full:
            components = get_all_parts(doc)
        else:
            components = get_direct_children(doc)

        logging.info("Found %d components to export", len(components))

        # Sort by Label then Name for stable filenames
        def sort_key(o):
            return (getattr(o, "Label", getattr(o, "Name", "")) or "", getattr(o, "Name", ""))

        components_sorted = sorted(components, key=sort_key)

        for idx, obj in enumerate(components_sorted, start=1):
            label = getattr(obj, "Label", getattr(obj, "Name", f"obj_{idx:03d}")) or f"obj_{idx:03d}"
            fname = f"{'part' if args.full else 'child'}_{idx:03d}_{sanitize_filename(label)}.stp"
            output_path = os.path.join(outdir, fname)
            logging.info("Exporting component \"%s\" to %s", label, output_path)
            ok = export_component(obj, output_path)
            if not ok:
                logging.warning("Skipped component due to export failure: %s", label)

        logging.info("Export complete. Cleaning up.")
    finally:
        try:
            FreeCAD.closeDocument(doc.Name)
        except Exception:
            pass


if __name__ == "__main__":
    main()
