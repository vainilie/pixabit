import re
from typing import Any, Optional

from pixabit.config import ATTRIBUTE_MAP, TAG_MAP
from pixabit.utils.generic_repr import generic_repr as repr

attribute_string = {"🜄": "con", "🜂": "str", "🜁": "int", "🜃": "per", "᛭": "legacy"}


class Tag:
    def __init__(
        self,
        tag: dict[str, Any],
        type: str = "basic",
        origin: Optional[str] = None,
        attr: Optional[str] = None,
        parent: Optional["Tag"] = None,
        child: Optional[list["Tag"]] = None,
        position: Optional[int] = None,
    ) -> None:
        """Initialize a Tag object."""
        self.name: Optional[str] = tag.get("name")
        self.id: Optional[str] = tag.get("id")
        self.challenge: bool = tag.get("challenge", False)
        self.child: Optional[list[Tag]] = child
        self.parent: Optional[Tag] = parent
        self.type: Optional[str] = type
        self.origin: Optional[str] = origin
        self.attr: Optional[str] = attr
        self.position: Optional[int] = position

    def __repr__(self) -> str:
        return repr(self)


def process_tag(i: int, tag_info: dict[str, Any]) -> Optional[Tag]:
    """Manages tags and their categories for Habitica."""
    tag_map: dict[str, str] = TAG_MAP
    attr_map: dict[str, str] = ATTRIBUTE_MAP
    area_map: dict[str, str] = attribute_string

    tag = Tag(tag_info)
    tag.position = i
    if tag_info.get("id") in tag_map:
        tag.type = "parent"
        tag.origin = tag_map[tag_info.get("id")]
    elif tag_info.get("id") in attr_map:
        tag.type = "parent"
        tag.attr = attr_map[tag_info.get("id")]
    symbol_match = re.search(r"([🜄🜂🜁🜃᛭])", tag_info.get("name"))
    if symbol_match and symbol_match.group(1) in area_map:
        tag.type = "child"
        tag.attr = area_map[symbol_match.group(1)]
        for k, v in attr_map.items():
            if tag.attr == v:
                tag.parent = k
        for k, v in tag_map.items():
            if tag.parent == v:
                tag.origin = k

    return tag


def proccess_tags(tags: list[dict[str, Any]]) -> list[Tag]:
    """Processes a list of tags and returns a list of Tag objects."""
    processed_tags: list[Tag] = []
    for i, tag_info in enumerate(tags):
        tag = process_tag(i, tag_info)
        if tag:
            processed_tags.append(tag)
    return processed_tags
