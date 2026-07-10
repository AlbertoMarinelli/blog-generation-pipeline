from app.downloaders.article_downloader import ArticleDownloader
from config import RSS_FEEDS

from app.collectors.rss import RSSCollector
from app.preprocessing.deduplicator import Deduplicator

from app.database.db import init_db
from app.database.repository import ArticleRepository


def main():

    init_db()

    collector = RSSCollector(RSS_FEEDS)

    articles = collector.collect()

    print(f"Collected: {len(articles)}")

    downloader = ArticleDownloader()

    articles = downloader.process(articles)

    print(f"Downloaded: {len(articles)}")

    deduplicator = Deduplicator()

    articles = deduplicator.process(articles)

    print(f"Unique: {len(articles)}")

    repository = ArticleRepository()

    saved = repository.save_many(articles)

    print(f"Saved: {saved}")


if __name__ == "__main__":

    main()