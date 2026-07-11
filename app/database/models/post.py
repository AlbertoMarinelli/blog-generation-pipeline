from datetime import datetime
from typing import Optional
from sqlalchemy import LargeBinary, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.models.base import Base

class GeneratedPostModel(Base):
    __tablename__ = "generated_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    title: Mapped[str]
    content: Mapped[str]
    url: Mapped[str]
    embedding: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    seo_score: Mapped[float]
    max_similarity: Mapped[float]
    needs_review: Mapped[bool] = mapped_column(default=False)
    is_published: Mapped[bool] = mapped_column(default=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    topic = relationship("TopicModel", backref="posts")
