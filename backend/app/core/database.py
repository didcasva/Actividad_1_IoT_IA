from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
Session = sessionmaker(engine)


class Base(DeclarativeBase):
    pass
