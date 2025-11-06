import sys
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.BRep import BRep_Tool
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_EDGE
from OCC.Core.gp import gp_Pnt
import ezdxf

# Orthogonal projections for 3 views (Front, Top, Side)
PROJECTIONS = [
    ((0, 0, 1), 'Top'),    # Z projection
    ((0, 1, 0), 'Front'),  # Y projection
    ((1, 0, 0), 'Side'),   # X projection
]

def load_shape(step_file):
    reader = STEPControl_Reader()
    status = reader.ReadFile(step_file)
    if status != IFSelect_RetDone:
        raise RuntimeError("Error: Failed to read STEP file!")
    reader.TransferRoots()
    return reader.OneShape()

def project_point(p, direction):
    """
    Ortho project a 3D point onto a plane normal to 'direction'.
    Returns a 2D (x, y) tuple for DXF.
    """
    # For Top view (0,0,1): Keep X, Y, drop Z
    # For Front (0,1,0): Keep X, Z, drop Y
    # For Side (1,0,0): Keep Y, Z, drop X
    if direction == (0, 0, 1):      # Top
        return (p.X(), p.Y())
    elif direction == (0, 1, 0):    # Front
        return (p.X(), p.Z())
    elif direction == (1, 0, 0):    # Side
        return (p.Y(), p.Z())
    else:
        return (p.X(), p.Y())

def collect_edges(shape):
    edges = []
    explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    while explorer.More():
        edge = explorer.Current()
        curve_handle, first, last = BRep_Tool.Curve(edge)
        p0 = curve_handle.Value(first)
        p1 = curve_handle.Value(last)
        edges.append((p0, p1))
        explorer.Next()
    return edges

def write_dxf(edges, projection, name, doc, msp, offset=(0,0)):
    # Apply projection
    for p0, p1 in edges:
        pt1 = project_point(p0, projection)
        pt2 = project_point(p1, projection)
        # Offset each view for layout
        pt1 = (pt1[0]+offset[0], pt1[1]+offset[1])
        pt2 = (pt2[0]+offset[0], pt2[1]+offset[1])
        msp.add_line(pt1, pt2, dxfattribs={'layer': name})

def main():
    if len(sys.argv) != 3:
        print("Usage: python step_to_dxf.py input_file.stp output_file.dxf")
        sys.exit(1)

    step_file = sys.argv[1]
    out_dxf = sys.argv[2]

    print(f"Loading STEP file: {step_file}")
    shape = load_shape(step_file)
    print("Extracting edges ...")
    edges = collect_edges(shape)

    doc = ezdxf.new(setup=True)
    msp = doc.modelspace()
    # Arrange 3 views side by side for manufacturer drawings
    view_spacing = 200  # Space between views (units depend on your model scale)
    offsets = [
        (0,0),                  # Top left for Top view
        (view_spacing,0),       # Next for Front view
        (2*view_spacing,0),     # Next for Side view
    ]
    for (proj, name), offset in zip(PROJECTIONS, offsets):
        print(f"Projecting {name} view ...")
        write_dxf(edges, proj, name, doc, msp, offset=offset)
    print(f"Writing DXF to: {out_dxf}")
    doc.saveas(out_dxf)
    print(f"DXF export complete.")

if __name__ == "__main__":
    main()
