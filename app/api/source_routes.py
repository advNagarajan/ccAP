from sqlalchemy import select

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.source import Source
from app.schemas.source import SourceResponse

router = APIRouter(tags=["Sources"])


@router.get(
    "/sources",
    response_model=list[SourceResponse]
)
def get_sources(
    source_type: str | None = None,
    db: Session = Depends(get_db)
):
    stmt = select(Source)

    if source_type:
        stmt = stmt.where(
            Source.source_type == source_type
        )

    result = db.execute(stmt)

    return result.scalars().all()