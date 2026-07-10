from sqlalchemy import create_engine
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