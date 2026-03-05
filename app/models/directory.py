import re

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
    """A topic's full content: title, subtitle, and sections with blocks."""
    title: str
    subtitle: str = ""
    sections: list[Section] = []


class TopicEntry(BaseModel):
    """A topic listed on a parent page. Points to its own Directory file."""
    slug: str
    title: str
    description: str = ""
    icon: str = "i-ph:folder-bold"
    color: str = "orange"
    stars: str = ""
    url: str = ""

    @staticmethod
    def slugify(title: str) -> str:
        s = title.lower().strip()
        s = re.sub(r'[^a-z0-9\s-]', '', s)
        s = re.sub(r'[\s-]+', '-', s).strip('-')
        return s[:60]


class PageIndex(BaseModel):
    """Parent page index: lists topics within this page."""
    title: str
    subtitle: str = ""
    topics: list[TopicEntry] = []
