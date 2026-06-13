from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import List as ListType

from app.db.session import get_db
from app.models.schema_fallback_request import SchemaFallbackRequest
from app.schemas.fallback import FallbackApproveRequest, FallbackRejectRequest, FallbackResponse
from app.services.backup_table_service import create_backup_table_for_request, reject_fallback_request

router = APIRouter(tags=["Schema Fallback Requests"])


@router.get(
    "/schema-fallbacks",
    response_model=ListType[FallbackResponse]
)
def list_fallback_requests(
    status: str = Query("PENDING", description="Filter requests by status (PENDING, APPROVED, REJECTED)"),
    db: Session = Depends(get_db)
):
    stmt = select(SchemaFallbackRequest).where(SchemaFallbackRequest.request_status == status).order_by(SchemaFallbackRequest.created_at.desc())
    results = db.execute(stmt).scalars().all()
    return results


@router.post(
    "/schema-fallbacks/{request_id}/approve",
    status_code=200
)
def approve_fallback_request(
    request_id: UUID,
    payload: FallbackApproveRequest,
    db: Session = Depends(get_db)
):
    try:
        table_name = create_backup_table_for_request(
            request_id=request_id,
            approved_by=payload.approved_by,
            review_notes=payload.review_notes,
            db=db
        )
        return {
            "message": "Backup table created successfully",
            "backup_table_name": table_name
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to approve fallback request: {str(e)}")


@router.post(
    "/schema-fallbacks/{request_id}/reject",
    status_code=200
)
def reject_fallback_request_route(
    request_id: UUID,
    payload: FallbackRejectRequest,
    db: Session = Depends(get_db)
):
    try:
        reject_fallback_request(
            request_id=request_id,
            rejected_by=payload.rejected_by,
            review_notes=payload.review_notes,
            db=db
        )
        return {
            "message": "Fallback request rejected successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reject fallback request: {str(e)}")
