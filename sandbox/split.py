#!/usr/bin/env python3
"""
split.py — Split a STEP assembly into separate STEP files.

Usage:
  - First-level children only (default):
      python split.py --input assembly.stp --outdir parts/

  - Full split (all descendants):
      python split.py --input assembly.stp --outdir parts/ --full

Notes:
  - Headless-friendly: does not depend on FreeCADGui / ViewObject.
  - Supports detecting Group objects (App::DocumentObjectGroup) as first-level containers.
  - Includes debugging dump of objects for inspection and fallback heuristics.
"""

import os
import sys
import argparse
import logging
from typing import Iterable, List, Sequence, Set

try:
    import FreeCAD
    import Part
    import Import
    try:
        import FreeCADGui  # noqa: F401
    except Exception:
        FreeCADGui = None
except ImportError as e:
    print(f"[ERROR] FreeCAD modules could not be imported: {e}", file=sys.stderr)
    sys.exit(1)


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")


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


def load_document(input_file: str):
    abs_path = os.path.abspath(input_file)
    logging.info("Loading document: %s", abs_path)
    doc = FreeCAD.newDocument("tmp")

    # Attempt to disable STEP compound merging
    try:
        prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/ImportExport/STEP")
        prefs.SetBool("EnableStepCompoundMerge", False)
        logging.info("STEP import option: 'EnableStepCompoundMerge' set to False")
    except Exception as e:
        logging.warning("Could not set STEP import preference: %s", e)

    # Import the STEP file
    Part.insert(abs_path, doc.Name)
    doc.recompute()
    logging.info("Document loaded, object count: %d", len(doc.Objects))
    return doc

# def load_document(input_file: str):
#     abs_path = os.path.abspath(input_file)
#     logging.info("Loading document: %s", abs_path)
#     doc = FreeCAD.newDocument("tmp")
#     Part.insert(abs_path, doc.Name)
#     doc.recompute()
#     logging.info("Document loaded, object count: %d", len(doc.Objects))
#     return doc

def print_object_info(root_obj) -> None:    
    prop_list = sorted(list(set(dir(root_obj)))) # Get all attributes and sort them

    for prop_name in prop_list:
        if prop_name.startswith('__'): # Skip dunder methods
            continue
        
        try:
            value = getattr(root_obj, prop_name)
            if callable(value): # Skip methods
                continue
            
            # Truncate long values for readability
            value_repr = repr(value)
            if len(value_repr) > 120:
                value_repr = value_repr[:120] + '...'
                
            logging.info(f"  {prop_name:<25}: {value_repr}")

        except Exception as e:
            logging.info(f"  {prop_name:<25}: <Error reading property: {e}>")
    logging.info("--- End of property dump ---")
    # --- End of property dump ---

def get_root_objects(doc) -> List:
    print("hello world")
    print_object_info(doc)
    print(doc.DependencyGraph)
    print(len(doc.Objects))
    print(doc.PropertiesList)



    roots = getattr(doc, "RootObjects", None)
    if roots is not None and isinstance(roots, (list, tuple)) and len(roots) > 0:
        logging.info("Found %d root object(s) via doc.RootObjects", len(roots))
        # print_object_info(roots[0])
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
        logging.warning("No root objects found; will treat all valid objects as first-level children.")
        return [o for o in doc.Objects if has_solid_shape(o) and not getattr(o, "Name", "").startswith("Unnamed")]

    # FIRST: detect group objects as first level
    group_candidates: List = [o for o in doc.Objects if (getattr(o, "TypeId", "") == "App::DocumentObjectGroup")]
    if group_candidates:
        logging.info("Detected %d group object(s) to act as first-level children", len(group_candidates))
        filtered_groups: List = []
        for g in group_candidates:
            # ensure group has members
            members = getattr(g, "Group", [])
            logging.info("Group %s has %d members", g.Name, len(members))
            if len(members) > 0:
                filtered_groups.append(g)
        if filtered_groups:
            logging.info("Using group objects as direct children (count = %d)", len(filtered_groups))
            return filtered_groups
    print(group_candidates)


    # SECOND: attempt via InList relationships

    candidates= []
    filtered: List = []
    for o in unique_preserving_order(candidates):
        if not has_solid_shape(o):
            logging.debug("Skipping %s: no solid shape", o.Name)
            continue
        if getattr(o, "Name", "").startswith("Unnamed"):
            logging.debug("Skipping %s: Name starts 'Unnamed'", o.Name)
            continue
        filtered.append(o)

    if not filtered:
        logging.warning("No children found via InList relation; fallback to all valid solid objects.")
        filtered = [o for o in doc.Objects if has_solid_shape(o) and not getattr(o, "Name", "").startswith("Unnamed")]
        logging.info("Fallback: treating %d objects as first-level children", len(filtered))

    logging.info("Direct children count: %d", len(filtered))
    return filtered


def get_all_parts(doc) -> List:
    roots = get_root_objects(doc)
    collected: List = []
    if roots:
        for root in roots:
            rec = getattr(root, "OutListRecursive", [])
            logging.info("Root %s: OutListRecursive length = %d", root.Name, len(rec))
            if rec:
                collected.extend(list(rec))
    if not collected:
        logging.info("No descendants collected via OutListRecursive; fallback to all objects.")
        collected = list(doc.Objects)

    out: List = []
    for o in unique_preserving_order(collected):
        if not has_solid_shape(o):
            logging.debug("Skipping %s: no solid shape", o.Name)
            continue
        if getattr(o, "Name", "").startswith("Unnamed"):
            logging.debug("Skipping %s: Name begins 'Unnamed'", o.Name)
            continue
        out.append(o)

    logging.info("All parts count: %d", len(out))
    return out


def export_component(obj, output_path: str) -> bool:
    try:
        logging.debug("Trying Import.export for %s", obj.Name)
        Import.export([obj], output_path)
        return True
    except Exception as e1:
        logging.debug("Import.export failed for %s: %s", obj.Name, e1)
        try:
            logging.debug("Trying Part.export for %s", obj.Name)
            Part.export([obj], output_path)
            return True
        except Exception as e2:
            logging.error("Export failed for %s: %s", obj.Name, e2)
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

    for o in doc.Objects:
        logging.info("Object: Name=%s, TypeId=%s", o.Name, getattr(o, "TypeId", "<none>"))
        try:
            grp = o.getGroup() if hasattr(o, "getGroup") else None
        except Exception as e:
            grp = None
            logging.info("  getGroup() raised exception for %s: %s", o.Name, e)
        logging.info("  getGroup -> %s", grp.Name if grp else None)
        # Also log InList, OutList sizes
        inlist = getattr(o, "InList", [])
        outlist = getattr(o, "OutList", [])
        logging.info("  InList size=%d, OutList size=%d", len(inlist), len(outlist))
        # If it is something like App::Part, log number of objects “inside”
        if o.TypeId.startswith("App::Part"):
            # maybe inspect its subobjects
            children = [c for c in doc.Objects if o in getattr(c, "InList", [])]
            logging.info("  Potential Part container: %s has %d children via InList", o.Name, len(children))



    try:
        if args.full:
            components = get_all_parts(doc)
        else:
            components = get_direct_children(doc)

        mode = "full" if args.full else "direct"
        logging.info("Found %d components to export (mode = %s)", len(components), mode)

        def sort_key(o):
            return (getattr(o, "Label", getattr(o, "Name", "")) or "",
                    getattr(o, "Name", ""))

        components_sorted = sorted(components, key=sort_key)

        for idx, obj in enumerate(components_sorted, start=1):
            label = getattr(obj, "Label", getattr(obj, "Name", f"obj_{idx:03d}")) or f"obj_{idx:03d}"
            fname = f"{'part' if args.full else 'child'}_{idx:03d}_{sanitize_filename(label)}.stp"
            output_path = os.path.join(outdir, fname)
            logging.info("=> Exporting [%d/%d] \"%s\" -> %s", idx, len(components_sorted), label, output_path)
            if not export_component(obj, output_path):
                logging.warning("Skipped component due to export failure: %s", label)

        logging.info("Export complete.")
    finally:
        try:
            FreeCAD.closeDocument(doc.Name)
        except Exception:
            pass


if __name__ == "__main__":
    main()
