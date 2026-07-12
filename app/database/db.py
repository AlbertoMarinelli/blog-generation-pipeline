import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from config import DATABASE_PATH
from app.database.models import Base


# Load DATABASE_URL from environment if present, otherwise fallback to local SQLite
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")

engine = create_engine(
    DATABASE_URL,
    echo=False
)

SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False
)


def init_db():
    """Initializes the database schema and performs self-healing schema migrations."""
    Base.metadata.create_all(engine)

    # Self-healing migration to add 'embedding' column if it does not exist
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('articles')]
    if 'embedding' not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE articles ADD COLUMN embedding BLOB"))
    if 'is_compliant' not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE articles ADD COLUMN is_compliant BOOLEAN"))
    if 'compliance_reason' not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE articles ADD COLUMN compliance_reason TEXT"))
    if 'is_used' not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE articles ADD COLUMN is_used BOOLEAN DEFAULT 0"))

    # Self-healing migration to add 'keywords' and 'search_trends' to generation_plans table
    columns_gp = [col['name'] for col in inspector.get_columns('generation_plans')]
    if 'keywords' not in columns_gp:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE generation_plans ADD COLUMN keywords TEXT"))
    if 'search_trends' not in columns_gp:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE generation_plans ADD COLUMN search_trends TEXT"))

