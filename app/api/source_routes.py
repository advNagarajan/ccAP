from sqlalchemy import select

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.source import Source
from app.schemas.source import SourceResponse

from fastapi import HTTPException
from uuid import UUID

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

@router.get(
    "/sources/{source_id}",
    response_model=SourceResponse
)
def get_source(
    source_id: UUID,
    db: Session = Depends(get_db)
):
    source = db.get(
        Source,
        source_id
    )

    if source is None:
        raise HTTPException(
            status_code=404,
            detail="Source not found"
        )

    return source