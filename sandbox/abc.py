#!/usr/bin/env python3
"""
step_assembly_inspect_schema_check.py — inspect STEP assemblies in pythonOCC-core headless,
including schema/version warning and graceful fallback.

Usage:
    python step_assembly_inspect_schema_check.py /path/to/assembly.stp
"""

import sys
import os

from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.TDF import TDF_LabelSequence
from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool_ShapeTool
from OCC.Core.TDataStd import TDataStd_Name
from OCC.Core.TopoDS import TopoDS_Shape
from OCC.Core.BRepBndLib import brepbndlib_Add
from OCC.Core.Bnd import Bnd_Box

def get_label_name(label):
    """Get name of a label, if set via TDataStd_Name."""
    try:
        if label.FindAttribute(TDataStd_Name.GetID()):
            name_attr = label.FindAttribute(TDataStd_Name.GetID())
            return name_attr.Get()
    except Exception:
        pass
    return "<unnamed>"

def shape_bounding_box(shape: TopoDS_Shape):
    """Compute bounding box of shape."""
    bbox = Bnd_Box()
    brepbndlib_Add(shape, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    return xmin, ymin, zmin, xmax, ymax, zmax

def inspect_document_caf(step_file):
    """Try reading via STEPCAF (assembly + product tree)."""
    reader = STEPCAFControl_Reader()
    ret = reader.ReadFile(step_file)
    if ret != 0:
        print(f"[ERROR] STEPCAFControl_Reader.ReadFile returned {ret}")
        print("  → Likely schema unsupported or file contains unsupported entities.")
        return False
    doc = TDocStd_Document("inspectdoc")
    try:
        reader.Transfer(doc)
    except Exception as e:
        print(f"[ERROR] Transfer to document failed: {e}")
        return False

    print(f"Document transferred (CAF mode): {step_file}")

    shape_tool = XCAFDoc_DocumentTool_ShapeTool(doc.Main())
    labels = TDF_LabelSequence()
    shape_tool.GetFreeShapes(labels)
    n = labels.Length()
    print(f"Top-level shapes count: {n}")

    for i in range(1, n+1):
        lbl = labels.Value(i)
        name = get_label_name(lbl)
        try:
            is_assembly = shape_tool.IsAssembly(lbl)
        except Exception:
            is_assembly = False
        try:
            is_shape = shape_tool.IsShape(lbl)
        except Exception:
            is_shape = False

        print(f"Label {i}: name={name!r}, is_assembly={is_assembly}, is_shape={is_shape}")

        if is_shape:
            try:
                shp = shape_tool.GetShape(lbl)
                if not shp.IsNull():
                    xmin, ymin, zmin, xmax, ymax, zmax = shape_bounding_box(shp)
                    print(f"  BoundingBox x[{xmin:.3f},{xmax:.3f}] y[{ymin:.3f},{ymax:.3f}] z[{zmin:.3f},{zmax:.3f}]")
                else:
                    print("  Shape is null")
            except Exception as e:
                print(f"  Error retrieving shape/bbox: {e}")
        print("----")
    return True

def inspect_document_simple(step_file):
    """Fallback: read via STEPControl (geometry only)."""
    reader = STEPControl_Reader()
    ret = reader.ReadFile(step_file)
    if ret != 0:
        print(f"[ERROR] STEPControl_Reader.ReadFile returned {ret}")
        print("  → Geometry mode also failed. File may be corrupt or use unsupported schema/entities.")
        return
    reader.TransferRoots()
    try:
        shp = reader.OneShape()
    except Exception as e:
        print(f"[ERROR] reader.OneShape() failed: {e}")
        return
    print(f"Geometry mode: found shape {shp}")
    try:
        xmin, ymin, zmin, xmax, ymax, zmax = shape_bounding_box(shp)
        print(f"  BoundingBox x[{xmin:.3f},{xmax:.3f}] y[{ymin:.3f},{ymax:.3f}] z[{zmin:.3f},{zmax:.3f}]")
    except Exception as e:
        print(f"  Error computing bounding box: {e}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python step_assembly_inspect_schema_check.py /path/to/file.stp")
        sys.exit(1)
    input_file = sys.argv[1]
    if not os.path.isfile(input_file):
        print(f"Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    print("=== Inspecting STEP file:", input_file)
    print("Note: If this STEP uses AP242 (ed2/ed3) you may hit unsupported schema issues in OCCT.")

    worked = inspect_document_caf(input_file)
    if not worked:
        print("Falling back to simple geometry inspection.")
        inspect_document_simple(input_file)

if __name__ == "__main__":
    main()
