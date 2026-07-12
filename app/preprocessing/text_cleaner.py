import re
import unicodedata
from datetime import datetime
import dateparser
from bs4 import BeautifulSoup

from app.entities.article import Article


class TextCleaner:
    """Pre-processing module that cleans raw text content and parses publication dates."""

    def clean_text(self, text: str) -> str:
        """Cleans unicode representations, strips HTML tags, and standardizes whitespace in text.

        Args:
            text (str): The raw input text.

        Returns:
            str: The cleaned and normalized text.
        """
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
        """Parses raw date string into a standardized date format (%Y-%m-%d %H:%M:%S).

        Args:
            raw_date (str): The raw string representation of a date.

        Returns:
            str: Standardized UTC date string.
        """
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
        """Cleans textual attributes (title, summary, content) and parses dates for a list of articles.

        Args:
            articles (list[Article]): The list of raw articles to clean.

        Returns:
            list[Article]: Cleaned and processed articles.
        """
        for article in articles:
            article.title = self.clean_text(article.title)
            article.summary = self.clean_text(article.summary)
            article.content = self.clean_text(article.content)
            article.published = self.parse_date(article.published)

        return articles
