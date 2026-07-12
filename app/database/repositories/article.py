from sqlalchemy import select
from app.database.db import SessionLocal
from app.database.models import ArticleModel


class ArticleRepository:
    """Repository class for persisting, updating, and querying collected articles."""

    def __init__(self, session_factory=None):
        self.session_factory = session_factory or SessionLocal

    def save_many(self, articles) -> int:
        """Saves a list of raw Article entities to the database, skipping duplicates.

        Args:
            articles (list[Article]): The list of raw articles to save.

        Returns:
            int: The number of new articles successfully saved.
        """
        with self.session_factory() as session:
            existing_urls = set(
                session.scalars(
                    select(ArticleModel.url)
                ).all()
            )

            seen_in_batch = set()
            new_articles = []

            for article in articles:
                if article.url in existing_urls or article.url in seen_in_batch:
                    continue

                seen_in_batch.add(article.url)
                new_articles.append(
                    ArticleModel(
                        title=article.title,
                        summary=article.summary,
                        content=article.content,
                        url=article.url,
                        source=article.source,
                        published=article.published
                    )
                )

            session.add_all(new_articles)
            session.commit()
            return len(new_articles)

    def get_all(self) -> list[ArticleModel]:
        """Retrieves all articles in the database.

        Returns:
            list[ArticleModel]: All articles.
        """
        with self.session_factory() as session:
            return list(session.scalars(
                select(ArticleModel)
            ).all())

    def update_article_topics(self, updates: list[dict]):
        """Updates assigned topic ids and labels for a batch of articles.

        Args:
            updates (list[dict]): List of dicts, each with 'id', 'topic_id', and 'topic_label'.
        """
        with self.session_factory() as session:
            for update in updates:
                article = session.get(ArticleModel, update["id"])
                if article:
                    article.topic_id = update["topic_id"]
                    article.topic_label = update["topic_label"]
            session.commit()

    def update_article_embeddings(self, updates: list[dict]):
        """Updates binary embedding buffers for a batch of articles.

        Args:
            updates (list[dict]): List of dicts, each with 'id' and 'embedding'.
        """
        with self.session_factory() as session:
            for update in updates:
                article = session.get(ArticleModel, update["id"])
                if article:
                    article.embedding = update["embedding"]
            session.commit()

    def get_compliant(self) -> list[ArticleModel]:
        """Retrieves all brand-compliant articles.

        Returns:
            list[ArticleModel]: Compliant articles.
        """
        with self.session_factory() as session:
            return list(session.scalars(
                select(ArticleModel).where(ArticleModel.is_compliant == True)
            ).all())

    def get_pending_compliance(self) -> list[ArticleModel]:
        """Retrieves all articles pending brand compliance evaluation.

        Returns:
            list[ArticleModel]: Pending articles.
        """
        with self.session_factory() as session:
            return list(session.scalars(
                select(ArticleModel).where(ArticleModel.is_compliant == None)
            ).all())

    def update_article_compliance(self, updates: list[dict]):
        """Updates compliance status, reasons, and optional embeddings for a batch of articles.

        Args:
            updates (list[dict]): List of compliance update dictionaries.
        """
        with self.session_factory() as session:
            for update in updates:
                article = session.get(ArticleModel, update["id"])
                if article:
                    article.is_compliant = update["is_compliant"]
                    article.compliance_reason = update["compliance_reason"]
                    if "embedding" in update:
                        article.embedding = update["embedding"]
            session.commit()

    def filter_new_articles(self, articles: list) -> list:
        """Filters out articles that already exist in the database based on URL.

        Args:
            articles (list): List of crawled articles.

        Returns:
            list: List of articles not yet present in the database.
        """
        with self.session_factory() as session:
            existing_urls = set(
                session.scalars(
                    select(ArticleModel.url)
                ).all()
            )
            return [a for a in articles if a.url not in existing_urls]

    def get_unused_compliant_by_topic(self, topic_id: int) -> list[ArticleModel]:
        """Retrieves compliant, unused articles belonging to a specific topic.

        Args:
            topic_id (int): Database topic ID.

        Returns:
            list[ArticleModel]: Compliant, unused articles.
        """
        with self.session_factory() as session:
            return list(session.scalars(
                select(ArticleModel).where(
                    ArticleModel.topic_id == topic_id,
                    ArticleModel.is_compliant == True,
                    ArticleModel.is_used == False
                )
            ).all())

    def mark_articles_as_used(self, article_ids: list[int]):
        """Marks a batch of articles as used in post generation.

        Args:
            article_ids (list[int]): Database IDs of the articles.
        """
        with self.session_factory() as session:
            for aid in article_ids:
                article = session.get(ArticleModel, aid)
                if article:
                    article.is_used = True
            session.commit()

    def get_articles_for_training(self, days: int = 14, min_count: int = 100) -> list[ArticleModel]:
        """Retrieves recent articles for BERTopic training.

        Args:
            days (int): Sliding window size in days.
            min_count (int): Minimum required articles for training fallback.

        Returns:
            list[ArticleModel]: Articles matching criteria or fallback count.
        """
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        with self.session_factory() as session:
            # Retrieve articles from the last N days ordered by insertion date
            articles = session.scalars(
                select(ArticleModel)
                .where(ArticleModel.inserted_at >= cutoff_date)
                .order_by(ArticleModel.inserted_at.desc())
            ).all()
            
            # If the result count satisfies the minimum requirement, return them
            if len(articles) >= min_count:
                return list(articles)
                
            # [DIDACTIC_LIMITATION] Fallback to retrieving the most recent articles up to min_count (default 100)
            # to ensure there is enough training data for BERTopic in sandbox/educational settings.
            return list(session.scalars(
                select(ArticleModel)
                .order_by(ArticleModel.inserted_at.desc())
                .limit(min_count)
            ).all())
