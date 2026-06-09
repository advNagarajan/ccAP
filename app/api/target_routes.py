from uuid import UUID
from datetime import datetime
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.target_catalog import TargetCatalog
from app.models.llm_feedback_loop import LlmFeedbackLoop
from app.schemas.target import (
    TargetCatalogCreate,
    TargetCatalogCreateResponse,
    TargetCatalogResponse,
    TargetCatalogUpdate
)
from app.schemas.feedback import (
    FeedbackCreate,
    FeedbackResponse
)
from app.pubsub.publisher import (
    publish_target_mutated,
    publish_feedback_submitted
)

router = APIRouter(tags=["Targets"])

VALID_TARGET_TYPES = {
    "POSTGRESQL",
    "MYSQL",
    "BIGQUERY",
    "GCS",
    "S3",
    "DELTA",
    "SNOWFLAKE"
}


@router.post(
    "/targets",
    response_model=TargetCatalogCreateResponse,
    status_code=201
)
def create_target(
    payload: TargetCatalogCreate,
    db: Session = Depends(get_db)
):
    if payload.target_type.upper() not in VALID_TARGET_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Invalid target type"
        )

    existing_target = db.execute(
        select(TargetCatalog)
        .where(TargetCatalog.target_name == payload.target_name)
    ).scalar_one_or_none()

    if existing_target:
        raise HTTPException(
            status_code=409,
            detail="Target already exists"
        )

    target = TargetCatalog(
        target_name=payload.target_name,
        target_type=payload.target_type.upper(),
        business_domain=payload.business_domain,
        connection_details=payload.connection_details,
        schema_definition=payload.schema_definition,
        is_system_generated=payload.is_system_generated,
        description=payload.description,
        target_status="ACTIVE"
    )

    db.add(target)
    db.commit()
    db.refresh(target)

    # Trigger async vectorization
    try:
        publish_target_mutated(target.target_id)
    except Exception as e:
        print(f"Error publishing target-mutated event: {e}")

    return target


@router.get(
    "/targets",
    response_model=list[TargetCatalogResponse]
)
def get_targets(
    target_type: str | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db)
):
    stmt = select(TargetCatalog)

    if target_type:
        stmt = stmt.where(
            TargetCatalog.target_type == target_type.upper()
        )

    if not include_inactive:
        stmt = stmt.where(
            TargetCatalog.target_status == "ACTIVE"
        )

    result = db.execute(stmt)
    return result.scalars().all()


@router.get(
    "/targets/{target_id}",
    response_model=TargetCatalogResponse
)
def get_target(
    target_id: UUID,
    include_inactive: bool = False,
    db: Session = Depends(get_db)
):
    target = db.get(TargetCatalog, target_id)

    if target is None:
        raise HTTPException(
            status_code=404,
            detail="Target not found"
        )

    if not include_inactive and target.target_status != "ACTIVE":
        raise HTTPException(
            status_code=404,
            detail="Target not found"
        )

    return target


@router.patch(
    "/targets/{target_id}",
    response_model=TargetCatalogResponse
)
def update_target(
    target_id: UUID,
    payload: TargetCatalogUpdate,
    db: Session = Depends(get_db)
):
    target = db.get(TargetCatalog, target_id)

    if target is None:
        raise HTTPException(
            status_code=404,
            detail="Target not found"
        )

    updates = payload.model_dump(exclude_unset=True)

    for field, value in updates.items():
        if field == "target_type" and value is not None:
            value = value.upper()
            if value not in VALID_TARGET_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid target type"
                )
        setattr(target, field, value)

    target.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(target)

    # Trigger async vectorization
    try:
        publish_target_mutated(target.target_id)
    except Exception as e:
        print(f"Error publishing target-mutated event: {e}")

    return target


@router.delete(
    "/targets/{target_id}",
    status_code=204
)
def delete_target(
    target_id: UUID,
    db: Session = Depends(get_db)
):
    target = db.get(TargetCatalog, target_id)

    if target is None:
        raise HTTPException(
            status_code=404,
            detail="Target not found"
        )

    target.target_status = "INACTIVE"
    target.updated_at = datetime.utcnow()
    db.commit()

    return Response(status_code=204)


@router.post(
    "/targets/{target_id}/feedback",
    response_model=FeedbackResponse,
    status_code=201
)
def submit_feedback(
    target_id: UUID,
    payload: FeedbackCreate,
    db: Session = Depends(get_db)
):
    target = db.get(TargetCatalog, target_id)

    if target is None:
        raise HTTPException(
            status_code=404,
            detail="Target not found"
        )

    feedback = LlmFeedbackLoop(
        job_id=payload.job_id,
        target_id=target_id,
        observed_flattened_paths=payload.observed_flattened_paths,
        user_action=payload.user_action,
        engineer_notes=payload.engineer_notes
    )

    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    # Trigger async feedback loops
    try:
        publish_feedback_submitted(
            job_id=feedback.job_id,
            target_id=target_id,
            user_action=feedback.user_action,
            notes=feedback.engineer_notes
        )
    except Exception as e:
        print(f"Error publishing feedback-submitted event: {e}")

    return feedback
