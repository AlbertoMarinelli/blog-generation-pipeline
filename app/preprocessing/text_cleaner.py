import re
import unicodedata
from datetime import datetime
import dateparser
from bs4 import BeautifulSoup

from app.entities.article import Article


class TextCleaner:

    def clean_text(self, text: str) -> str:
        if not text:
            return ""

        # Normalize unicode (NFKD)
        text = unicodedata.normalize("NFKD", text)

        # Remove HTML tags using BeautifulSoup
        soup = BeautifulSoup(text, "html.parser")
        text = soup.get_text()

        # Clean whitespace:
        # 1. Replace multiple spaces/tabs with a single space
        text = re.sub(r"[ \t]+", " ", text)
        # 2. Limit consecutive newlines to maximum 2 (paragraph breaks)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def parse_date(self, raw_date: str) -> str:
        if not raw_date:
            return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        try:
            parsed = dateparser.parse(raw_date)
            if parsed:
                return parsed.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

        return raw_date

    def process(self, articles: list[Article]) -> list[Article]:
        for article in articles:
            article.title = self.clean_text(article.title)
            article.summary = self.clean_text(article.summary)
            article.content = self.clean_text(article.content)
            article.published = self.parse_date(article.published)

        return articles
