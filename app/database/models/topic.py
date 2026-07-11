from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from app.database.models.base import Base

class TopicModel(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int]  # Il topic_id di BERTopic (-1, 0, 1, ...)
    label: Mapped[str]
    keywords: Mapped[Optional[str]] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
