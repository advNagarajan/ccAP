from fastapi import FastAPI

app = FastAPI(
    title = "Smart Data Landing and Schema Intelligence Platform",
    version = "0.0.1"
)

@app.get("/")
def health():
    return {
        "status" : "running"
    }