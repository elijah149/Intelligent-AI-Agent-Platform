from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import settings
from backend.app.models.database import Base


database_url = settings.database_url
if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://", "postgresql+psycopg://", 1
    )
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace(
        "postgresql://", "postgresql+psycopg://", 1
    )

engine = create_engine(
    database_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def create_tables():
    Base.metadata.create_all(bind=engine)
