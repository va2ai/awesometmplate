from pydantic import BaseModel


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
