import sys
import datetime
import subprocess
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.BRep import BRep_Tool
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_EDGE
import ezdxf

# Sheet constants (mm, ISO A4)
A4_WIDTH = 297
A4_HEIGHT = 210
MARGIN = 10

# Orthogonal projections
PROJECTIONS = [
    ((0, 0, 1), 'Top'),     # Z projection
    ((0, 1, 0), 'Front'),   # Y projection
    ((1, 0, 0), 'Side'),    # X projection
]

def export_pdf_from_dxf(dxf_file, pdf_file):
    try:
        print(f"Generating PDF: {pdf_file}")
        subprocess.run([
            "inkscape", dxf_file, "--export-type=pdf", "--export-filename", pdf_file
        ], check=True)
        print(f"PDF saved: {pdf_file}")
    except Exception as e:
        print("PDF export failed:", e)

def load_shape(step_file):
    reader = STEPControl_Reader()
    status = reader.ReadFile(step_file)
    if status != IFSelect_RetDone:
        raise RuntimeError("Error: Failed to read STEP file!")
    reader.TransferRoots()
    return reader.OneShape()

def project_point(p, direction):
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

def get_bbox(edges, proj):
    min_x, min_y = float('inf'), float('inf')
    max_x, max_y = float('-inf'), float('-inf')
    for p0, p1 in edges:
        for p in [p0, p1]:
            x, y = project_point(p, proj)
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
    return (min_x, min_y, max_x, max_y)

def scale_and_center(bbox, frame_width, frame_height):
    min_x, min_y, max_x, max_y = bbox
    obj_w = max_x - min_x
    obj_h = max_y - min_y
    scale_x = frame_width / obj_w if obj_w != 0 else 1
    scale_y = frame_height / obj_h if obj_h != 0 else 1
    scale = min(scale_x, scale_y)
    offset_x = (frame_width - obj_w * scale) / 2 - min_x * scale
    offset_y = (frame_height - obj_h * scale) / 2 - min_y * scale
    return scale, offset_x, offset_y

def draw_iso_frame_and_block(doc, msp):
    doc.layers.add("FRAME")
    doc.layers.add("TITLE")
    doc.layers.add("Top")
    doc.layers.add("Front")
    doc.layers.add("Side")
    msp.add_lwpolyline([
        (0, 0), (A4_WIDTH, 0), (A4_WIDTH, A4_HEIGHT), (0, A4_HEIGHT), (0, 0)
    ], dxfattribs={'layer':'FRAME'})
    msp.add_lwpolyline([
        (MARGIN, MARGIN), (A4_WIDTH-MARGIN, MARGIN),
        (A4_WIDTH-MARGIN, A4_HEIGHT-MARGIN), (MARGIN, A4_HEIGHT-MARGIN), (MARGIN, MARGIN)
    ], dxfattribs={'layer':'FRAME'})
    tb_w = 180
    tb_h = 55
    tb_x = A4_WIDTH - tb_w - MARGIN
    tb_y = MARGIN
    msp.add_lwpolyline([
        (tb_x, tb_y), (tb_x+tb_w, tb_y), (tb_x+tb_w, tb_y+tb_h), (tb_x, tb_y+tb_h), (tb_x, tb_y)
    ], dxfattribs={'layer':'TITLE'})
    msp.add_line((tb_x, tb_y+tb_h-12), (tb_x+tb_w, tb_y+tb_h-12), dxfattribs={'layer':'TITLE'})
    msp.add_line((tb_x, tb_y+tb_h-30), (tb_x+tb_w, tb_y+tb_h-30), dxfattribs={'layer':'TITLE'})
    return tb_x, tb_y, tb_w, tb_h

def fill_title_block(msp, tb_x, tb_y, tb_w, tb_h, title, filename, company=""):
    today = str(datetime.date.today())
    msp.add_text("DRAWING TITLE:", dxfattribs={'height':6, 'layer':'TITLE', 'insert': (tb_x+2, tb_y+tb_h-8)})
    msp.add_text(title, dxfattribs={'layer':'TITLE', 'height':7, 'insert': (tb_x+75, tb_y+tb_h-8)})
    msp.add_text("FILE:", dxfattribs={'height':4.5, 'layer':'TITLE', 'insert': (tb_x+2, tb_y+tb_h-18)})
    msp.add_text(filename, dxfattribs={'layer':'TITLE', 'height':4, 'insert': (tb_x+18, tb_y+tb_h-18)})
    msp.add_text("DATE:", dxfattribs={'height':4.5, 'layer':'TITLE', 'insert': (tb_x+2, tb_y+tb_h-36)})
    msp.add_text(today, dxfattribs={'layer':'TITLE', 'height':4, 'insert': (tb_x+18, tb_y+tb_h-36)})
    msp.add_text("COMPANY:", dxfattribs={'height':4.5, 'layer':'TITLE', 'insert': (tb_x+2, tb_y+tb_h-52)})
    msp.add_text(company, dxfattribs={'layer':'TITLE', 'height':4, 'insert': (tb_x+24, tb_y+tb_h-52)})

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

    tb_x, tb_y, tb_w, tb_h = draw_iso_frame_and_block(doc, msp)
    fill_title_block(msp, tb_x, tb_y, tb_w, tb_h, title="3-View Projection", filename=step_file, company="Your Company")

    gap = 15
    view_area_w = int((A4_WIDTH - 2 * MARGIN - 2 * gap - 20) / 3)
    view_area_h = A4_HEIGHT - tb_h - 2*MARGIN - 24
    view_offsets = [
        (MARGIN+10, tb_y+tb_h+12),
        (MARGIN+10 + view_area_w + gap, tb_y+tb_h+12),
        (MARGIN+10 + 2 * (view_area_w + gap), tb_y+tb_h+12)
    ]

    for ((proj, name), offset) in zip(PROJECTIONS, view_offsets):
        bbox = get_bbox(edges, proj)
        scale, off_x, off_y = scale_and_center(bbox, view_area_w, view_area_h)
        msp.add_text(f"{name.upper()} VIEW", dxfattribs={'layer': 'TITLE', 'height':7, 'insert': (offset[0], offset[1]-12)})
        for p0, p1 in edges:
            pt1 = project_point(p0, proj)
            pt2 = project_point(p1, proj)
            pt1 = (pt1[0]*scale + offset[0] + off_x, pt1[1]*scale + offset[1] + off_y)
            pt2 = (pt2[0]*scale + offset[0] + off_x, pt2[1]*scale + offset[1] + off_y)
            msp.add_line(pt1, pt2, dxfattribs={'layer': name, 'color': 7})

    print(f"Writing DXF to: {out_dxf}")
    doc.saveas(out_dxf)
    print(f"DXF export complete. Ready for production or quoting.")

    # Generate PDF as well
    out_pdf = out_dxf.rsplit('.', 1)[0] + '.pdf'
    export_pdf_from_dxf(out_dxf, out_pdf)

if __name__ == "__main__":
    main()
