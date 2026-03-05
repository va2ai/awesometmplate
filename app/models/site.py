from pydantic import BaseModel


class ResearchRequest(BaseModel):
    topic: str
    items: list[dict] = []
    instructions: str = ""


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
