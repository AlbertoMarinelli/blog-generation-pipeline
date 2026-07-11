from datetime import datetime
from typing import Optional
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.models.base import Base

class GenerationPlanModel(Base):
    __tablename__ = "generation_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    topic_label: Mapped[str]
    allocated_posts: Mapped[int]
    computed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    keywords: Mapped[Optional[str]] = mapped_column(nullable=True)
    search_trends: Mapped[Optional[str]] = mapped_column(nullable=True)

    topic = relationship("TopicModel", backref="generation_plans")
