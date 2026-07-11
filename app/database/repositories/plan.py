from sqlalchemy import select
from app.database.db import SessionLocal
from app.database.models import GenerationPlanModel


class GenerationPlanRepository:

    def __init__(self, session_factory=None):
        self.session_factory = session_factory or SessionLocal

    def save_generation_plan(self, plan: list[dict]):
        with self.session_factory() as session:
            # Clear old plan snapshot
            session.query(GenerationPlanModel).delete()

            for p in plan:
                session.add(
                    GenerationPlanModel(
                        topic_id=p["topic_id"],
                        topic_label=p["topic_label"],
                        allocated_posts=p["allocated_posts"],
                        keywords=p.get("keywords"),
                        search_trends=p.get("search_trends")
                    )
                )
            session.commit()

    def get_active_plans(self) -> list[GenerationPlanModel]:
        """
        Ritorna la lista dei piani di generazione attivi (con budget post > 0)
        ordinati per numero di post decrescente.
        """
        with self.session_factory() as session:
            return session.scalars(
                select(GenerationPlanModel)
                .where(GenerationPlanModel.allocated_posts > 0)
                .order_by(GenerationPlanModel.allocated_posts.desc())
            ).all()
