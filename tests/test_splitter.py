from pathlib import Path

from models.types.split_part import SplitPart
from cad.layouts import build_part_layout


def test_build_part_layout_nested_structure():
    parts = [
        SplitPart(
            name="main_build", hierarchy=tuple(), has_children=True, step_path=Path("main.stp")
        ),
        SplitPart(
            name="sub_build1",
            hierarchy=("main_build",),
            has_children=True,
            step_path=Path("sub1.stp"),
        ),
        SplitPart(
            name="sub_build2",
            hierarchy=("main_build",),
            has_children=False,
            step_path=Path("sub2.stp"),
        ),
        SplitPart(
            name="plate_a",
            hierarchy=("main_build", "sub_build1"),
            has_children=False,
            step_path=Path("plate_a.stp"),
        ),
        SplitPart(
            name="plate_b",
            hierarchy=("main_build", "sub_build1"),
            has_children=False,
            step_path=Path("plate_b.stp"),
        ),
    ]

    layout = build_part_layout(parts)

    assert layout == {
        "main_build": {
            "sub_build1": ["plate_a", "plate_b"],
            "_parts": ["sub_build2"],
        }
    }


def test_build_part_layout_top_level_leaves():
    parts = [
        SplitPart(name="widget_a", hierarchy=tuple(), has_children=False, step_path=Path("a.stp")),
        SplitPart(name="widget_b", hierarchy=tuple(), has_children=False, step_path=Path("b.stp")),
    ]

    layout = build_part_layout(parts)

    assert layout == ["widget_a", "widget_b"]
