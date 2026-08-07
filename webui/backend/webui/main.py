"""
Quant-Math WebUI Backend - FastAPI Application

Main entry point for the WebUI backend API.
"""
import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from webui.api import routes
from webui.core.config import settings
from webui.core.database import init_db
from webui.core.websocket import ws_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    print("[WebUI] Starting Quant-Math WebUI Backend...")
    await init_db()
    await ws_manager.start()
    yield
    # Shutdown
    print("[WebUI] Shutting down Quant-Math WebUI Backend...")
    await ws_manager.stop()


app = FastAPI(
    title="Quant-Math WebUI API",
    description="Backend API for Quant-Math WebUI Dashboard",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(routes.router, prefix="/api/v1")

# Health check endpoint (must be before catch-all route)
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "quant-math-webui"}

# Serve frontend static files in production
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        index_file = frontend_dist / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"error": "Frontend not built"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "webui.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )