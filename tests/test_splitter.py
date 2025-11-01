from pathlib import Path

from splitter import ModelObject, split_into_parts


def test_split_into_parts_uses_precomputed_parts(tmp_path):
    source = tmp_path / "model.step"
    source.write_text("dummy", encoding="utf-8")

    precomputed = ["bodyA", "bodyB", "bodyC"]
    model = ModelObject(source_path=source, document=None, precomputed_parts=precomputed)

    parts = split_into_parts(model)

    assert len(parts) == 3
    assert parts[0].name == "part_1"
    assert parts[-1].index == 2
