import feedparser

from app.models.article import Article

from .base import BaseCollector


class RSSCollector(BaseCollector):

    def __init__(self, feeds):

        self.feeds = feeds

    def collect(self):

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