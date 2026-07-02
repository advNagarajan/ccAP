from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from pgvector.psycopg2 import register_vector

from app.core.settings import settings

DATABASE_URL = settings.database_url

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800
)

@event.listens_for(engine, "connect")
def connect(dbapi_connection, connection_record):
    register_vector(dbapi_connection)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)