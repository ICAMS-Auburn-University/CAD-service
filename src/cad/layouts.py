import logging
from typing import Any, Dict, List, Sequence

from models.types.split_part import SplitPart

logger = logging.getLogger(__name__)


class LayoutNode:
    def __init__(self) -> None:
        self.children: Dict[str, "LayoutNode"] = {}
        self.leaves: List[str] = []

    def add(self, hierarchy: Sequence[str], name: str, has_children: bool) -> None:
        node = self
        for segment in hierarchy:
            node = node.children.setdefault(segment, LayoutNode())
        if has_children:
            node = node.children.setdefault(name, LayoutNode())
        else:
            node.leaves.append(name)

    def serialize(self) -> Dict[str, Any] | List[str]:
        serialized_children = {
            key: child.serialize() for key, child in sorted(self.children.items())
        }
        deduped_leaves = list(dict.fromkeys(self.leaves))

        if serialized_children and deduped_leaves:
            serialized_children["_parts"] = deduped_leaves
            return serialized_children
        if serialized_children:
            return serialized_children
        return deduped_leaves


def build_part_layout(parts: Sequence[SplitPart]) -> Dict[str, Any] | List[str]:
    root = LayoutNode()
    for part in parts:
        root.add(part.hierarchy, part.name, part.has_children)
    logger.info("Built layout tree for %d parts", len(parts))

    serialized = {
        key: child.serialize() for key, child in sorted(root.children.items())
    }
    if root.leaves:
        deduped = list(dict.fromkeys(root.leaves))
        if serialized:
            serialized["_parts"] = deduped
            return serialized
        return deduped

    return serialized
