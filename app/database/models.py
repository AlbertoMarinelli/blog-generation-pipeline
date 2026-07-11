from datetime import datetime
from typing import Optional

from sqlalchemy import LargeBinary
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column


class Base(DeclarativeBase):
    pass


class ArticleModel(Base):

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)

    title: Mapped[str]

    summary: Mapped[str]

    content: Mapped[str]

    url: Mapped[str] = mapped_column(unique=True)

    source: Mapped[str]

    published: Mapped[str]

    inserted_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    topic_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    topic_label: Mapped[Optional[str]] = mapped_column(nullable=True)

    embedding: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)

    is_compliant: Mapped[Optional[bool]] = mapped_column(nullable=True)

    compliance_reason: Mapped[Optional[str]] = mapped_column(nullable=True)



class TopicTrendModel(Base):

    __tablename__ = "topic_trends"

    id: Mapped[int] = mapped_column(primary_key=True)

    topic_id: Mapped[int]

    topic_label: Mapped[str]

    volume: Mapped[int]

    freshness_score: Mapped[float]

    source_diversity: Mapped[float]

    trend_score: Mapped[float]

    computed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class GenerationPlanModel(Base):

    __tablename__ = "generation_plans"

    id: Mapped[int] = mapped_column(primary_key=True)

    topic_id: Mapped[int]

    topic_label: Mapped[str]

    allocated_posts: Mapped[int]

    computed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

