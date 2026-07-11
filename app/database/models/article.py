from datetime import datetime
from typing import Optional
from sqlalchemy import LargeBinary, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.models.base import Base

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
    
    topic_id: Mapped[Optional[int]] = mapped_column(ForeignKey("topics.id"), nullable=True)
    topic_label: Mapped[Optional[str]] = mapped_column(nullable=True)
    
    embedding: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    is_compliant: Mapped[Optional[bool]] = mapped_column(nullable=True)
    compliance_reason: Mapped[Optional[str]] = mapped_column(nullable=True)
    is_used: Mapped[bool] = mapped_column(default=False)

    topic = relationship("TopicModel", backref="articles")
