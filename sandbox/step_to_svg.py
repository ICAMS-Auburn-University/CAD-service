import sys
import FreeCAD
import Import

def export_svg(step_file, out_svg):
    doc = FreeCAD.newDocument()
    Import.open(step_file)
    part = doc.Objects[-1]
    
    # Use doc.saveAs with SVG format
    # This bypasses the buggy importSVG module entirely
    part.Shape.exportBrep("/tmp/temp_shape.brep")
    
    # Now use the lower-level approach: write geometry data manually
    # Or: save the document and extract/convert
    
    # Simplest: Use Part module's built-in methods
    import Part
    Part.export([part], out_svg)
    print(f"SVG exported: {out_svg}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: freecadcmd step_to_svg.py input_file.stp output_file.svg")
        sys.exit(1)
    export_svg(sys.argv[1], sys.argv[2])
