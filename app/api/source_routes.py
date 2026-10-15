from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db

from app.models.db.source import Source
from app.models.db.processing_configuration import ProcessingConfiguration

from app.schemas.source import (
    SourceCreate,
    SourceCreateResponse,
    SourceResponse,
    SourceUpdate
)

from datetime import datetime

router = APIRouter(tags=["Sources"])

VALID_SOURCE_TYPES = {
    "BIGQUERY",
    "FIRESTORE",
    "GCS",
    "S3"
}

@router.post(
    "/sources",
    response_model=SourceCreateResponse,
    status_code=201
)
def create_source(
    payload: SourceCreate,
    db: Session = Depends(get_db)
):
    if payload.source_type.upper() not in VALID_SOURCE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Invalid source type"
        )

    config = db.get(ProcessingConfiguration, payload.config_id)

    if config is None:
        raise HTTPException(
            status_code=404,
            detail="Configuration not found"
        )

    existing_source = db.execute(
        select(Source)
        .where(Source.name == payload.name)
    ).scalar_one_or_none()

    if existing_source:
        raise HTTPException(
            status_code=409,
            detail="Source already exists"
        )

    source = Source(
        config_id=payload.config_id,
        name=payload.name,
        source_type=payload.source_type.upper(),
        connection_details=payload.connection_details,
        description=payload.description,
        status="ACTIVE"
    )

    db.add(source)

    db.commit()

    db.refresh(source)

    return source

@router.get(
    "/sources",
    response_model=list[SourceResponse]
)
def get_sources(
    source_type: str | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db)
):
    stmt = select(Source)

    if source_type:
        stmt = stmt.where(
            Source.source_type == source_type.upper()
        )

    if not include_inactive:
        stmt = stmt.where(
            Source.status == "ACTIVE"
        )

    result = db.execute(stmt)

    return result.scalars().all()


@router.get(
    "/sources/{source_id}",
    response_model=SourceResponse
)
def get_source(
    source_id: UUID,
    include_inactive: bool = False,
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

    if (
        not include_inactive
        and source.status != "ACTIVE"
    ):
        raise HTTPException(
            status_code=404,
            detail="Source not found"
        )

    return source

@router.patch(
    "/sources/{source_id}",
    response_model=SourceResponse
)
def update_source(
    source_id: UUID,
    payload: SourceUpdate,
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

    if payload.config_id is not None:
        config = db.get(ProcessingConfiguration, payload.config_id)
        if config is None:
            raise HTTPException(
                status_code=404,
                detail="Configuration not found"
            )

    updates = payload.model_dump(
        exclude_unset=True
    )

    for field, value in updates.items():
        setattr(
            source,
            field,
            value
        )

    source.updated_at = datetime.utcnow()

    db.commit()

    db.refresh(source)

    return source

@router.delete(
    "/sources/{source_id}",
    status_code=204
)
def delete_source(
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

    source.status = "INACTIVE"

    source.updated_at = datetime.utcnow()

    db.commit()

    return Response(status_code=204)