#!/usr/bin/env python3
"""
step_to_dxf_flat.py — Convert a STEP (.stp) file into a DXF drawing (.dxf) using FreeCAD headless.

Usage:
    freecadcmd step_to_dxf_flat.py input_file.stp output_file.dxf
"""

import sys
import os
import FreeCAD
import Import   # the import module for STEP
import importDXF

def export_dxf(step_file, out_dxf):
    print(f"Starting conversion: {step_file} → {out_dxf}")
    # Create new FreeCAD document
    doc = FreeCAD.newDocument()
    # Import the STEP file
    try:
        Import.open(step_file)
    except Exception as e:
        print(f"[ERROR] Failed to import STEP file: {e}", file=sys.stderr)
        sys.exit(1)
    # Check objects in document
    objs = doc.Objects
    if not objs:
        print("[ERROR] No objects found after import", file=sys.stderr)
        sys.exit(1)
    # Pick the last object (assuming the main geometry)
    part = objs[-1]
    print(f"Imported object: Name={part.Name}, Type={part.TypeId}")
    # Export to DXF
    try:
        importDXF.export([part], out_dxf)
    except Exception as e:
        print(f"[ERROR] Failed to export DXF: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"DXF exported successfully: {out_dxf}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: freecadcmd step_to_dxf_flat.py input_file.stp output_file.dxf", file=sys.stderr)
        sys.exit(1)
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    if not os.path.isfile(input_file):
        print(f"Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)
    # Optional: ensure output directory exists
    out_dir = os.path.dirname(output_file)
    if out_dir and not os.path.isdir(out_dir):
        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception as e:
            print(f"[ERROR] Cannot create output directory {out_dir}: {e}", file=sys.stderr)
            sys.exit(1)
    export_dxf(input_file, output_file)
