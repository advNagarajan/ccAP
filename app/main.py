from fastapi import FastAPI
from app.api.configuration_routes import router as configuration_router
from app.api.source_routes import router as source_router
from app.api.ingestion_routes import router as ingestion_router
from app.api.job_routes import router as job_router
from app.api.target_routes import router as target_router
from app.api.feedback_routes import router as feedback_router
from app.api.fallback_routes import router as fallback_router
from app.api.recipient_routes import router as recipient_router
from app.api.auth_routes import router as auth_router

app = FastAPI(
    title = "Smart Data Landing and Schema Intelligence Platform",
    version = "0.0.1"
)

@app.get("/")
def health():
    return {
        "status" : "running"
    }

app.include_router(source_router)
app.include_router(configuration_router)
app.include_router(ingestion_router)
app.include_router(job_router)
app.include_router(target_router)
app.include_router(feedback_router)
app.include_router(fallback_router)
app.include_router(recipient_router)
app.include_router(auth_router)