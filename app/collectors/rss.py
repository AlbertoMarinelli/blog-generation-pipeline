import feedparser

from app.entities.article import Article

from .base import BaseCollector


class RSSCollector(BaseCollector):
    """Collector implementation that parses articles from RSS feeds."""

    def __init__(self, feeds: list[str]):
        """Initializes the RSS collector with a list of feed URLs.

        Args:
            feeds (list[str]): List of RSS feed URLs to parse.
        """
        self.feeds = feeds

    def collect(self) -> list[Article]:
        """Parses and retrieves articles from all configured RSS feeds.

        Returns:
            list[Article]: A list of raw Article entities.
        """
        articles = []
        for feed in self.feeds:
            rss = feedparser.parse(feed)
            for entry in rss.entries:
                articles.append(
                    Article(
                        title=entry.get("title", ""),
                        summary=entry.get("summary", ""),
                        content="",
                        url=entry.get("link", ""),
                        source=rss.feed.get("title", ""),
                        published=entry.get("published", "")
                    )
                )
        return articles