from sqlalchemy import select

from app.database.db import SessionLocal
from app.database.models import ArticleModel


class ArticleRepository:

    def save_many(self, articles):

        with SessionLocal() as session:

            existing_urls = set(
                session.scalars(
                    select(ArticleModel.url)
                ).all()
            )

            new_articles = []

            for article in articles:

                if article.url in existing_urls:
                    continue

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