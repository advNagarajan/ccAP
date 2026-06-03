from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.source import Source

db = SessionLocal()

try:
    result = db.execute(
        select(Source)
    )

    for source in result.scalars():
        print(source.name)

finally:
    db.close()