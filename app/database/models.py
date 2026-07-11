from datetime import datetime
from typing import Optional

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