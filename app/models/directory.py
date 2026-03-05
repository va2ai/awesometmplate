from pydantic import BaseModel


class Block(BaseModel):
    """A flexible content block. Claude picks the type."""
    type: str
    label: str = ""
    content: dict = {}


class Section(BaseModel):
    title: str
    icon_class: str = "i-ph:folder-bold"
    color: str = "orange"
    description: str = ""
    url: str = ""
    stars: str = ""
    blocks: list[Block] = []


class Directory(BaseModel):
    title: str
    subtitle: str = ""
    sections: list[Section] = []
