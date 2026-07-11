from sqlalchemy import select
from app.database.db import SessionLocal
from app.database.models import ArticleModel


class ArticleRepository:

    def __init__(self, session_factory=None):
        self.session_factory = session_factory or SessionLocal

    def save_many(self, articles):
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

    def get_all(self):
        with self.session_factory() as session:
            return session.scalars(
                select(ArticleModel)
            ).all()

    def update_article_topics(self, updates: list[dict]):
        with self.session_factory() as session:
            for update in updates:
                article = session.get(ArticleModel, update["id"])
                if article:
                    article.topic_id = update["topic_id"]
                    article.topic_label = update["topic_label"]
            session.commit()

    def update_article_embeddings(self, updates: list[dict]):
        with self.session_factory() as session:
            for update in updates:
                article = session.get(ArticleModel, update["id"])
                if article:
                    article.embedding = update["embedding"]
            session.commit()

    def get_compliant(self):
        with self.session_factory() as session:
            return session.scalars(
                select(ArticleModel).where(ArticleModel.is_compliant == True)
            ).all()

    def get_pending_compliance(self):
        with self.session_factory() as session:
            return session.scalars(
                select(ArticleModel).where(ArticleModel.is_compliant == None)
            ).all()

    def update_article_compliance(self, updates: list[dict]):
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
        with self.session_factory() as session:
            existing_urls = set(
                session.scalars(
                    select(ArticleModel.url)
                ).all()
            )
            return [a for a in articles if a.url not in existing_urls]

    def get_unused_compliant_by_topic(self, topic_id: int) -> list[ArticleModel]:
        with self.session_factory() as session:
            return session.scalars(
                select(ArticleModel).where(
                    ArticleModel.topic_id == topic_id,
                    ArticleModel.is_compliant == True,
                    ArticleModel.is_used == False
                )
            ).all()

    def mark_articles_as_used(self, article_ids: list[int]):
        with self.session_factory() as session:
            for aid in article_ids:
                article = session.get(ArticleModel, aid)
                if article:
                    article.is_used = True
            session.commit()

    def get_articles_for_training(self, days: int = 14, min_count: int = 100) -> list[ArticleModel]:
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        with self.session_factory() as session:
            # Recupera articoli degli ultimi N giorni ordinati per data inserimento
            articles = session.scalars(
                select(ArticleModel)
                .where(ArticleModel.inserted_at >= cutoff_date)
                .order_by(ArticleModel.inserted_at.desc())
            ).all()
            
            # Se sono sufficienti, ritorna la lista
            if len(articles) >= min_count:
                return list(articles)
                
            # Altrimenti, fai il fallback prendendo gli ultimi `min_count` articoli in assoluto
            return list(session.scalars(
                select(ArticleModel)
                .order_by(ArticleModel.inserted_at.desc())
                .limit(min_count)
            ).all())
