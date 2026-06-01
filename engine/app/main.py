"""FastAPI entrypoint."""

import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.aggregates import router as aggregates_router
from app.api.findings import router as findings_router
from app.api.scans import router as scans_router
from app.detectors.image.warmup import models_ready, warm_image_models

app = FastAPI(title="Bosch GDPR Scan Engine", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scans_router)
app.include_router(aggregates_router)
app.include_router(findings_router)


@app.on_event("startup")
def _prewarm_image_models() -> None:
    """Load the torch-free image models (YOLO ONNX + RapidOCR) off the request path.

    Non-blocking: the server answers /health immediately while a daemon thread warms
    the onnxruntime sessions (~3-5 s). The first image scan then starts promptly.
    """
    threading.Thread(target=warm_image_models, name="image-model-warmup", daemon=True).start()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/capabilities")
def capabilities() -> dict:
    return {"graph_access": False, "models_ready": models_ready()}
