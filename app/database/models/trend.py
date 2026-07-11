from datetime import datetime
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.models.base import Base

class TopicTrendModel(Base):
    __tablename__ = "topic_trends"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    topic_label: Mapped[str]
    volume: Mapped[int]
    freshness_score: Mapped[float]
    source_diversity: Mapped[float]
    trend_score: Mapped[float]
    computed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    topic = relationship("TopicModel", backref="trends")
