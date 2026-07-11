from sqlalchemy import select

from app.database.db import SessionLocal
from app.database.models import ArticleModel, TopicTrendModel


class ArticleRepository:

    def save_many(self, articles):

        with SessionLocal() as session:

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

        with SessionLocal() as session:

            return session.scalars(
                select(ArticleModel)
            ).all()

    def update_article_topics(self, updates: list[dict]):

        with SessionLocal() as session:

            for update in updates:

                article = session.get(ArticleModel, update["id"])

                if article:

                    article.topic_id = update["topic_id"]

                    article.topic_label = update["topic_label"]

            session.commit()

    def update_article_embeddings(self, updates: list[dict]):

        with SessionLocal() as session:

            for update in updates:

                article = session.get(ArticleModel, update["id"])

                if article:

                    article.embedding = update["embedding"]

            session.commit()

    def save_topic_trends(self, trends: list[dict]):

        with SessionLocal() as session:

            # Clear old trends to keep it as a fresh snapshot
            session.query(TopicTrendModel).delete()

            for t in trends:

                session.add(

                    TopicTrendModel(

                        topic_id=t["topic_id"],

                        topic_label=t["topic_label"],

                        volume=t["volume"],

                        freshness_score=t["freshness_score"],

                        source_diversity=t["source_diversity"],

                        trend_score=t["trend_score"]

                    )

                )

            session.commit()

    def get_compliant(self):

        with SessionLocal() as session:

            return session.scalars(
                select(ArticleModel).where(ArticleModel.is_compliant == True)
            ).all()

    def get_pending_compliance(self):

        with SessionLocal() as session:

            return session.scalars(
                select(ArticleModel).where(ArticleModel.is_compliant == None)
            ).all()

    def update_article_compliance(self, updates: list[dict]):

        with SessionLocal() as session:

            for update in updates:

                article = session.get(ArticleModel, update["id"])

                if article:

                    article.is_compliant = update["is_compliant"]

                    article.compliance_reason = update["compliance_reason"]

                    if "embedding" in update:

                        article.embedding = update["embedding"]

            session.commit()