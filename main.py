from collections import Counter

from app.downloaders.article_downloader import ArticleDownloader
from config import RSS_FEEDS, DAILY_POST_BUDGET

from app.collectors.rss import RSSCollector
from app.preprocessing.text_cleaner import TextCleaner
from app.preprocessing.deduplicator import Deduplicator

from app.database.db import init_db
from app.database.repository import ArticleRepository
from app.topic_modeling.bertopic_model import FintechTopicModeler
from app.trend_analysis.scorer import TrendScorer
from app.compliance.compliance_filter import ComplianceFilter
from googlenewsdecoder import new_decoderv1
from app.generation.planner import PostPlanner


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

    print("\nStep 3: Decoding Google News links and deduplicating...")
    for article in articles:
        if "news.google.com" in article.url:
            try:
                decoded = new_decoderv1(article.url)
                if decoded.get("status"):
                    article.url = decoded["decoded_url"]
            except Exception:
                pass

    deduplicator = Deduplicator()
    articles = deduplicator.process(articles)
    print(f"Found {len(articles)} unique articles in feed batch.")

    print("\nStep 4: Filtering out articles already saved in the database...")
    repository = ArticleRepository()
    articles = repository.filter_new_articles(articles)
    print(f"Found {len(articles)} new articles not in the database.")

    if articles:
        print("\nStep 5: Downloading full article contents (limiting batch to 100 for speed/stability)...")
        articles = articles[:100]
        downloader = ArticleDownloader()
        articles = downloader.process(articles)
        print(f"Successfully downloaded {len(articles)} article bodies.")

        print("\nStep 6: Cleaning text and standardizing dates...")
        cleaner = TextCleaner()
        articles = cleaner.process(articles)

        print("\nStep 7: Saving new articles to database...")
        saved = repository.save_many(articles)
        print(f"Saved {saved} new articles to SQLite database.")
    else:
        print("\nSkipping download and cleaning: no new articles found.")


    # Evaluate compliance for pending articles
    print("\nStep 7a: Evaluating compliance for pending articles...")
    pending_articles = repository.get_pending_compliance()
    if pending_articles:
        comp_filter = ComplianceFilter()
        comp_filter.evaluate_articles(pending_articles, repository)
    else:
        print("No articles pending compliance check.")

    # Retrieve all articles to run BERTopic
    print("\nStep 7b: Retrieving all articles from database...")
    all_articles = repository.get_all()
    print(f"Total articles in database: {len(all_articles)}")

    if not all_articles:
        print("No articles in database to perform topic modeling.")
        return

    print("\nStep 8: Discovering topics using BERTopic...")
    modeler = FintechTopicModeler()
    try:
        topics, topic_labels = modeler.train(all_articles, repository=repository)
        
        # Prepare list of updates to save back to database
        updates = []
        for i, article in enumerate(all_articles):
            topic_id = int(topics[i])
            label = topic_labels.get(topic_id, "Unknown")
            
            # Mutate Python objects in-place so they can be immediately fed to TrendScorer
            article.topic_id = topic_id
            article.topic_label = label
            
            updates.append({
                "id": article.id,
                "topic_id": topic_id,
                "topic_label": label
            })

        print("\nStep 9: Updating article topics in database...")
        repository.update_article_topics(updates)
        print("Database updated with topic assignments.")

        print("\nStep 10: Analyzing and scoring topic trends with XGBoost...")
        scorer = TrendScorer()
        trends = scorer.calculate_trends(all_articles)
        
        print("Saving topic trends to SQLite database...")
        repository.save_topic_trends(trends)
        print("Topic trends saved.")

        # Print trends summary
        print("\n" + "=" * 60)
        print("TOPIC TRENDS SUMMARY (XGBoost Scored)")
        print("=" * 60)
        for t in trends[:10]:
            topic_id = t["topic_id"]
            topic_articles = [a for a in all_articles if a.topic_id == topic_id]
            total_vol = len(topic_articles)
            compliant_vol = sum(1 for a in topic_articles if a.is_compliant == True)
            
            print(f"[Score: {t['trend_score']:7.2f}] {t['topic_label']} "
                  f"(Volume: {total_vol}, Compliant: {compliant_vol}/{total_vol}, "
                  f"Freshness: {t['freshness_score']:.2f}, "
                  f"Sources: {int(t['source_diversity'] * total_vol)}/{total_vol})")
        print("=" * 60)

        print("\nStep 11: Generating daily post allocation plan...")
        planner = PostPlanner()
        plan = planner.plan_posts(all_articles, trends)
        
        print("Saving daily post allocation plan to SQLite database...")
        repository.save_generation_plan(plan)
        print("Daily post allocation plan saved.")

        # Print plan summary
        print("\n" + "=" * 60)
        print(f"DAILY POST ALLOCATION PLAN (Budget: {DAILY_POST_BUDGET} posts)")
        print("=" * 60)
        for p in plan:
            if p["allocated_posts"] > 0:
                print(f"[{p['allocated_posts']:2d} posts] {p['topic_label']} "
                      f"(Compliance: {int(p['compliance_rate'] * 100)}%, Trend Score: {p['trend_score']:.2f})")
        print("=" * 60)

    except Exception as e:
        print(f"Topic modeling failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()