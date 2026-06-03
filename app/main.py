from fastapi import FastAPI
from app.api.configuration_routes import router as configuration_router
from app.api.source_routes import router as source_router
from app.api.ingestion_routes import router as ingestion_router

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