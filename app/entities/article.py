from dataclasses import dataclass

@dataclass(slots=True)
class Article:
    """Represents a standardized raw article collected from external RSS feeds."""
    title: str
    summary: str
    content: str
    url: str
    source: str
    published: str

