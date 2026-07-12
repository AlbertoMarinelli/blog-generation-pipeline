from sqlalchemy import select
from app.database.db import SessionLocal
from app.database.models import TopicModel

class TopicRepository:
    """Repository class for managing topic classifications and active labels."""

    def __init__(self, session_factory=None):
        self.session_factory = session_factory or SessionLocal

    def save_topics(self, topics_list: list[dict]) -> dict[int, int]:
        """Deactivates old topics, inserts new ones, and returns a mapping from BERTopic ID to Database ID.

        Args:
            topics_list (list[dict]): List of discovered topic details.

        Returns:
            dict[int, int]: Mapping between BERTopic IDs and database primary IDs.
        """
        with self.session_factory() as session:
            # Deactivate previous active topics
            session.query(TopicModel).filter(TopicModel.is_active == True).update({"is_active": False})
            
            db_topics = []
            for t in topics_list:
                db_topic = TopicModel(
                    topic_id=t["topic_id"],
                    label=t["label"],
                    keywords=t.get("keywords"),
                    is_active=True
                )
                session.add(db_topic)
                db_topics.append((t["topic_id"], db_topic))
            
            session.commit()
            # Return mapping dictionary: {bertopic_id: db_id}
            return {bt_id: db_t.id for bt_id, db_t in db_topics}

    def get_active_topics_map(self) -> dict[int, int]:
        """Retrieves a dictionary mapping BERTopic IDs to Database IDs for active topics.

        Returns:
            dict[int, int]: Mapping of active topics.
        """
        with self.session_factory() as session:
            active = session.scalars(
                select(TopicModel).where(TopicModel.is_active == True)
            ).all()
            return {t.topic_id: t.id for t in active}

    def get_active_topic_labels_map(self) -> dict[int, str]:
        """Retrieves a dictionary mapping BERTopic IDs to labels for active topics.

        Returns:
            dict[int, str]: Mapping of active topic labels.
        """
        with self.session_factory() as session:
            active = session.scalars(
                select(TopicModel).where(TopicModel.is_active == True)
            ).all()
            return {t.topic_id: t.label for t in active}
