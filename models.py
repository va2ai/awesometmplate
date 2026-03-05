from pydantic import BaseModel


class ResearchRequest(BaseModel):
    topic: str
    items: list[dict] = []
    instructions: str = ""


class LinkItem(BaseModel):
    title: str
    url: str = ""
    description: str = ""
    stars: str = ""


class CodeCard(BaseModel):
    title: str
    description: str = ""
    code: str = ""
    language: str = ""


class InfoCard(BaseModel):
    title: str
    description: str = ""
    icon: str = ""


class ComparisonItem(BaseModel):
    label: str
    points: list[str] = []


class StatCard(BaseModel):
    value: str
    label: str
    description: str = ""


class StepItem(BaseModel):
    title: str
    description: str = ""
    code: str = ""


class TableRow(BaseModel):
    cells: list[str] = []


class FAQItem(BaseModel):
    question: str
    answer: str


class TimelineEvent(BaseModel):
    date: str = ""
    title: str
    description: str = ""


class BadgeItem(BaseModel):
    label: str
    color: str = "gray"


class ChecklistItem(BaseModel):
    text: str
    checked: bool = False


class Block(BaseModel):
    """A flexible content block. Claude picks the type."""
    type: str  # link_list, code_grid, info_grid, comparison, stats, steps, tip, text, table, faq, timeline, alert, badges, checklist
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


class Page(BaseModel):
    slug: str
    title: str
    subtitle: str = ""
    icon: str = "i-ph:folder-bold"
    color: str = "orange"


class SiteConfig(BaseModel):
    title: str = "AWESOME KNOWLEDGE BASE"
    subtitle: str = "Organize anything with Claude AI"
    pages: list[Page] = []
