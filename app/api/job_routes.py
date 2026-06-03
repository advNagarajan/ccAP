from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db

from app.models.job import Job

from app.constants.job_status import JobStatus

from app.schemas.job import JobResponse

router = APIRouter(tags=["Jobs"])

VALID_JOB_STATUSES = {
    JobStatus.RECEIVED,
    JobStatus.VALIDATING,
    JobStatus.RUNNING,
    JobStatus.COMPLETED,
    JobStatus.FAILED
}

@router.get(
    "/jobs",
    response_model=list[JobResponse]
)
def get_jobs(
    status: str | None = None,
    db: Session = Depends(get_db)
):
    stmt = select(Job)

    if status:

        status = status.upper()

        if status not in VALID_JOB_STATUSES:
            raise HTTPException(
                status_code=400,
                detail="Invalid status filter"
            )

        stmt = stmt.where(
            Job.status == status
        )

    result = db.execute(stmt)

    return result.scalars().all()


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse
)
def get_job(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    job = db.get(
        Job,
        job_id
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    return job