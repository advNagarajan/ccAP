from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session

from app.db.session import get_db

from app.models.source import Source
from app.models.job import Job

from app.constants.job_status import JobStatus

from app.schemas.ingestion import (
    IngestionCreate,
    IngestionResponse
)

from app.pubsub.publisher import (
    publish_ingestion_requested
)

router = APIRouter(tags=["Ingestions"])


@router.post(
    "/ingestions",
    response_model=IngestionResponse,
    status_code=201
)
def create_ingestion(
    payload: IngestionCreate,
    db: Session = Depends(get_db)
):
    source = db.get(
        Source,
        payload.source_id
    )

    if source is None:
        raise HTTPException(
            status_code=404,
            detail="Source not found"
        )

    job = Job(
        source_id=payload.source_id,
        status=JobStatus.RECEIVED
    )

    db.add(job)

    db.commit()

    db.refresh(job)

    publish_ingestion_requested(
        job.job_id,
        job.source_id
    )

    return job