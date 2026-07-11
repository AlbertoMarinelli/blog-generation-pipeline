from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from config import DATABASE_PATH
from app.database.models import Base


engine = create_engine(
    f"sqlite:///{DATABASE_PATH}",
    echo=False
)

SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False
)


def init_db():

    Base.metadata.create_all(engine)

    # Self-healing migration to add 'embedding' column if it does not exist
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('articles')]
    if 'embedding' not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE articles ADD COLUMN embedding BLOB"))