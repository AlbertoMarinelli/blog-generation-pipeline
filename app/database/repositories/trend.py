from sqlalchemy import select
from app.database.db import SessionLocal
from app.database.models import TopicTrendModel


class TopicTrendRepository:

    def __init__(self, session_factory=None):
        self.session_factory = session_factory or SessionLocal

    def save_topic_trends(self, trends: list[dict]):
        with self.session_factory() as session:
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
