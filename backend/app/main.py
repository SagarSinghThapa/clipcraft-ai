"""Main FastAPI application entrypoint for ClipCraft AI."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import settings
from backend.app.core.logger import logger
from backend.app.core.hardware import detect_hardware
from backend.app.api.routes_projects import router as projects_router
from backend.app.api.routes_ingestion import router as ingestion_router
from backend.app.api.routes_transcription import router as transcription_router
from backend.app.api.routes_analysis import router as analysis_router
from backend.app.api.routes_clips import router as clips_router
from backend.app.api.routes_reframe import router as reframe_router
from backend.app.api.routes_captions import router as captions_router
from backend.app.api.routes_facecam import router as facecam_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Local-First Free AI Video Clipping Application",
)

# Enable CORS for local Vite dev server and browser clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
app.include_router(projects_router)
app.include_router(ingestion_router)
app.include_router(transcription_router)
app.include_router(analysis_router)
app.include_router(clips_router)
app.include_router(reframe_router)
app.include_router(captions_router)
app.include_router(facecam_router)

# Mount static serving for project media (previews & clips)
projects_path = settings.PROJECTS_DIR
projects_path.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(projects_path)), name="media")


@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    detect_hardware()
    logger.info(f"Projects directory initialized at: {settings.PROJECTS_DIR}")


@app.get("/api/health")
async def health_check():
    """Health check endpoint providing status and version."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "device": settings.DEVICE,
    }
