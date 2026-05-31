"""FastAPI entrypoint."""

from fastapi import FastAPI

from app.api.scans import router as scans_router

app = FastAPI(title="Bosch GDPR Scan Engine", version="0.1.0")
app.include_router(scans_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
