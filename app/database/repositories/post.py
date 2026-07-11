from sqlalchemy import select
from app.database.db import SessionLocal
from app.database.models import GeneratedPostModel

class GeneratedPostRepository:
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or SessionLocal

    def save_post(self, topic_id: int, title: str, content: str, url: str, embedding: bytes, seo_score: float, max_similarity: float, needs_review: bool, is_published: bool = False, published_at = None):
        with self.session_factory() as session:
            db_post = GeneratedPostModel(
                topic_id=topic_id,
                title=title,
                content=content,
                url=url,
                embedding=embedding,
                seo_score=seo_score,
                max_similarity=max_similarity,
                needs_review=needs_review,
                is_published=is_published,
                published_at=published_at
            )
            session.add(db_post)
            session.commit()
            return db_post.id

    def mark_as_published(self, post_id: int, published_at = None):
        from datetime import datetime
        pub_time = published_at or datetime.utcnow()
        with self.session_factory() as session:
            db_post = session.get(GeneratedPostModel, post_id)
            if db_post:
                db_post.is_published = True
                db_post.published_at = pub_time
            session.commit()

    def get_all_embeddings(self) -> list[tuple[int, bytes]]:
        with self.session_factory() as session:
            results = session.execute(
                select(GeneratedPostModel.id, GeneratedPostModel.embedding)
            ).all()
            return [(r[0], r[1]) for r in results if r[1] is not None]

    def get_posts_by_ids(self, ids: list[int]) -> list[GeneratedPostModel]:
        if not ids:
            return []
        with self.session_factory() as session:
            return list(session.scalars(
                select(GeneratedPostModel).where(GeneratedPostModel.id.in_(ids))
            ).all())
