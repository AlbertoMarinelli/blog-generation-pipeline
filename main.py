from collections import Counter

from app.downloaders.article_downloader import ArticleDownloader
from config import RSS_FEEDS

from app.collectors.rss import RSSCollector
from app.preprocessing.text_cleaner import TextCleaner
from app.preprocessing.deduplicator import Deduplicator

from app.database.db import init_db
from app.database.repository import ArticleRepository
from app.topic_modeling.bertopic_model import FintechTopicModeler


def main():
    print("Step 1: Initializing Database...")
    init_db()

    print("\nStep 2: Collecting articles from RSS feeds...")
    collector = RSSCollector(RSS_FEEDS)
    articles = collector.collect()
    print(f"Collected {len(articles)} articles from RSS feeds.")

    if not articles:
        print("No articles found in feeds.")
        return

    print("\nStep 3: Downloading full article contents (limiting batch to 100 for speed/stability)...")
    articles = articles[:100]
    downloader = ArticleDownloader()
    articles = downloader.process(articles)
    print(f"Successfully downloaded {len(articles)} article bodies.")

    print("\nStep 4: Cleaning text and standardizing dates...")
    cleaner = TextCleaner()
    articles = cleaner.process(articles)

    print("\nStep 5: Deduplicating articles...")
    deduplicator = Deduplicator()
    articles = deduplicator.process(articles)
    print(f"Found {len(articles)} unique articles in this batch.")

    print("\nStep 6: Saving new articles to database...")
    repository = ArticleRepository()
    saved = repository.save_many(articles)
    print(f"Saved {saved} new articles to SQLite database.")

    # Retrieve all articles from DB to run BERTopic
    print("\nStep 7: Retrieving all articles from database...")
    all_articles = repository.get_all()
    print(f"Total articles in database: {len(all_articles)}")

    if not all_articles:
        print("No articles in database to perform topic modeling.")
        return

    print("\nStep 8: Discovering topics using BERTopic...")
    modeler = FintechTopicModeler()
    try:
        topics, topic_labels = modeler.train(all_articles)
        
        # Prepare list of updates to save back to database
        updates = []
        for i, article in enumerate(all_articles):
            topic_id = int(topics[i])
            updates.append({
                "id": article.id,
                "topic_id": topic_id,
                "topic_label": topic_labels.get(topic_id, "Unknown")
            })

        print("\nStep 9: Updating article topics in database...")
        repository.update_article_topics(updates)
        print("Database updated with topic assignments.")

        # Print topics summary
        topic_counts = Counter(topics)
        print("\n" + "=" * 60)
        print("DISCOVERED TOPICS SUMMARY")
        print("=" * 60)
        for topic_id, count in topic_counts.most_common():
            label = topic_labels.get(topic_id, "Other / Unclassified")
            print(f"[{count:3d} articles] {label}")
        print("=" * 60)

    except Exception as e:
        print(f"Topic modeling failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()