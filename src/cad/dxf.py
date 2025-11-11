import datetime
import logging
import subprocess
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import ezdxf
from OCC.Core.BRep import BRep_Tool
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.TopAbs import TopAbs_EDGE
from OCC.Core.TopExp import TopExp_Explorer

logger = logging.getLogger(__name__)

A4_WIDTH = 297
A4_HEIGHT = 210
MARGIN = 10
TITLE_BLOCK_WIDTH = 180
TITLE_BLOCK_HEIGHT = 55
VIEW_GAP = 15

PROJECTIONS: Sequence[Tuple[Tuple[int, int, int], str]] = (
    ((0, 0, 1), "Top"),
    ((0, 1, 0), "Front"),
    ((1, 0, 0), "Side"),
)


def export_pdf_from_dxf(dxf_file: Path, pdf_file: Path) -> None:
    try:
        subprocess.run(
            ["inkscape", str(dxf_file), "--export-type=pdf", "--export-filename", str(pdf_file)],
            check=True,
        )
        logger.info("Generated PDF %s from %s", pdf_file.name, dxf_file.name)
    except Exception:
        pass


def load_shape(step_file: Path):
    reader = STEPControl_Reader()
    status = reader.ReadFile(str(step_file))
    if status != IFSelect_RetDone:
        raise RuntimeError(f"Failed to read STEP file: {step_file}")
    reader.TransferRoots()
    return reader.OneShape()


def project_point(point, direction: Tuple[int, int, int]) -> Tuple[float, float]:
    if direction == (0, 0, 1):
        return (point.X(), point.Y())
    if direction == (0, 1, 0):
        return (point.X(), point.Z())
    if direction == (1, 0, 0):
        return (point.Y(), point.Z())
    return (point.X(), point.Y())


def collect_edges(shape) -> List[Tuple]:
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


def get_bbox(
    edges: Iterable[Tuple], projection: Tuple[int, int, int]
) -> Tuple[float, float, float, float]:
    min_x, min_y = float("inf"), float("inf")
    max_x, max_y = float("-inf"), float("-inf")

    for p0, p1 in edges:
        for point in (p0, p1):
            x, y = project_point(point, projection)
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)

    return (min_x, min_y, max_x, max_y)


def scale_and_center(
    bbox: Tuple[float, float, float, float], frame_width: float, frame_height: float
):
    min_x, min_y, max_x, max_y = bbox
    obj_w = max_x - min_x or 1
    obj_h = max_y - min_y or 1
    scale = min(frame_width / obj_w, frame_height / obj_h)
    offset_x = (frame_width - obj_w * scale) / 2 - min_x * scale
    offset_y = (frame_height - obj_h * scale) / 2 - min_y * scale
    return scale, offset_x, offset_y


def draw_iso_frame_and_block(doc, msp):
    doc.layers.add("FRAME")
    doc.layers.add("TITLE")
    for _, name in PROJECTIONS:
        doc.layers.add(name)

    msp.add_lwpolyline(
        [(0, 0), (A4_WIDTH, 0), (A4_WIDTH, A4_HEIGHT), (0, A4_HEIGHT), (0, 0)],
        dxfattribs={"layer": "FRAME"},
    )
    msp.add_lwpolyline(
        [
            (MARGIN, MARGIN),
            (A4_WIDTH - MARGIN, MARGIN),
            (A4_WIDTH - MARGIN, A4_HEIGHT - MARGIN),
            (MARGIN, A4_HEIGHT - MARGIN),
            (MARGIN, MARGIN),
        ],
        dxfattribs={"layer": "FRAME"},
    )

    tb_x = A4_WIDTH - TITLE_BLOCK_WIDTH - MARGIN
    tb_y = MARGIN
    msp.add_lwpolyline(
        [
            (tb_x, tb_y),
            (tb_x + TITLE_BLOCK_WIDTH, tb_y),
            (tb_x + TITLE_BLOCK_WIDTH, tb_y + TITLE_BLOCK_HEIGHT),
            (tb_x, tb_y + TITLE_BLOCK_HEIGHT),
            (tb_x, tb_y),
        ],
        dxfattribs={"layer": "TITLE"},
    )
    msp.add_line(
        (tb_x, tb_y + TITLE_BLOCK_HEIGHT - 12),
        (tb_x + TITLE_BLOCK_WIDTH, tb_y + TITLE_BLOCK_HEIGHT - 12),
        dxfattribs={"layer": "TITLE"},
    )
    msp.add_line(
        (tb_x, tb_y + TITLE_BLOCK_HEIGHT - 30),
        (tb_x + TITLE_BLOCK_WIDTH, tb_y + TITLE_BLOCK_HEIGHT - 30),
        dxfattribs={"layer": "TITLE"},
    )
    return tb_x, tb_y, TITLE_BLOCK_WIDTH, TITLE_BLOCK_HEIGHT


def fill_title_block(
    msp, tb_x, tb_y, tb_w, tb_h, title: str, filename: str, company: str = ""
) -> None:
    today = str(datetime.date.today())
    msp.add_text(
        "DRAWING TITLE:",
        dxfattribs={"height": 6, "layer": "TITLE", "insert": (tb_x + 2, tb_y + tb_h - 8)},
    )
    msp.add_text(
        title,
        dxfattribs={"layer": "TITLE", "height": 7, "insert": (tb_x + 75, tb_y + tb_h - 8)},
    )
    msp.add_text(
        "FILE:",
        dxfattribs={"height": 4.5, "layer": "TITLE", "insert": (tb_x + 2, tb_y + tb_h - 18)},
    )
    msp.add_text(
        filename,
        dxfattribs={"layer": "TITLE", "height": 4, "insert": (tb_x + 18, tb_y + tb_h - 18)},
    )
    msp.add_text(
        "DATE:",
        dxfattribs={"height": 4.5, "layer": "TITLE", "insert": (tb_x + 2, tb_y + tb_h - 36)},
    )
    msp.add_text(
        today,
        dxfattribs={"layer": "TITLE", "height": 4, "insert": (tb_x + 18, tb_y + tb_h - 36)},
    )
    msp.add_text(
        "COMPANY:",
        dxfattribs={"height": 4.5, "layer": "TITLE", "insert": (tb_x + 2, tb_y + tb_h - 52)},
    )
    msp.add_text(
        company,
        dxfattribs={"layer": "TITLE", "height": 4, "insert": (tb_x + 24, tb_y + tb_h - 52)},
    )


def convert_step_to_dxf(
    step_file: Path,
    out_dxf: Path | None = None,
    *,
    company: str = "",
    title: str | None = None,
    export_pdf: bool = False,
) -> Path:
    """Convert a STEP file into a DXF drawing with three orthogonal views."""

    step_path = Path(step_file).resolve()
    if out_dxf is None:
        dxf_path = step_path.with_suffix(".dxf")
    else:
        dxf_path = Path(out_dxf).resolve()

    logger.info("Generating DXF for %s -> %s", step_path.name, dxf_path.name)
    shape = load_shape(step_path)
    edges = collect_edges(shape)

    doc = ezdxf.new(setup=True)
    msp = doc.modelspace()

    tb_x, tb_y, tb_w, tb_h = draw_iso_frame_and_block(doc, msp)
    fill_title_block(
        msp,
        tb_x,
        tb_y,
        tb_w,
        tb_h,
        title=title or step_path.stem,
        filename=step_path.name,
        company=company,
    )

    view_area_width = int((A4_WIDTH - 2 * MARGIN - 2 * VIEW_GAP - 20) / len(PROJECTIONS))
    view_area_height = A4_HEIGHT - tb_h - 2 * MARGIN - 24

    for index, (projection, name) in enumerate(PROJECTIONS):
        origin_x = MARGIN + 10 + index * (view_area_width + VIEW_GAP)
        origin_y = tb_y + tb_h + 12
        bbox = get_bbox(edges, projection)
        scale, offset_x, offset_y = scale_and_center(bbox, view_area_width, view_area_height)

        msp.add_text(
            f"{name.upper()} VIEW",
            dxfattribs={"layer": "TITLE", "height": 7, "insert": (origin_x, origin_y - 12)},
        )

        for p0, p1 in edges:
            pt1 = project_point(p0, projection)
            pt2 = project_point(p1, projection)
            pt1 = (pt1[0] * scale + origin_x + offset_x, pt1[1] * scale + origin_y + offset_y)
            pt2 = (pt2[0] * scale + origin_x + offset_x, pt2[1] * scale + origin_y + offset_y)
            msp.add_line(pt1, pt2, dxfattribs={"layer": name, "color": 7})

    doc.saveas(str(dxf_path))
    logger.info("DXF saved to %s", dxf_path)

    if export_pdf:
        pdf_path = dxf_path.with_suffix(".pdf")
        export_pdf_from_dxf(dxf_path, pdf_path)

    return dxf_path
