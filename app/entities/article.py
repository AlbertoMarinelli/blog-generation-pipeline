from dataclasses import dataclass

@dataclass(slots=True)
class Article:
    title: str
    summary: str
    content: str
    url: str
    source: str
    published: str
