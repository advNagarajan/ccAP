from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.configuration_routes import router as configuration_router

from app.api.source_routes import router as source_router
from app.api.ingestion_routes import router as ingestion_router
from app.api.job_routes import router as job_router
from app.api.target_routes import router as target_router
from app.api.feedback_routes import router as feedback_router
from app.api.fallback_routes import router as fallback_router
from app.api.recipient_routes import router as recipient_router
from app.api.auth_routes import router as auth_router
from app.api.audit_routes import router as audit_router

app = FastAPI(
    title = "Smart Data Landing and Schema Intelligence Platform",
    version = "0.0.1"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {
            "status" : "running",
            "database" : "connected"
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection failed: {str(e)}"
        )

app.include_router(source_router)
app.include_router(configuration_router)
app.include_router(ingestion_router)
app.include_router(job_router)
app.include_router(target_router)
app.include_router(feedback_router)
app.include_router(fallback_router)
app.include_router(recipient_router)
app.include_router(auth_router)
app.include_router(audit_router)