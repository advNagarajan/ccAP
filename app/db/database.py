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
    try:
        if hasattr(dbapi_connection, "adapters"):
            from pgvector.psycopg import register_vector as register_v3
            register_v3(dbapi_connection)
        else:
            from pgvector.psycopg2 import register_vector as register_v2
            register_v2(dbapi_connection)
    except Exception:
        pass

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)