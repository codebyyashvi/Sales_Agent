import os
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.database import connect_db, close_db, get_db
from app.api import calls, customers, products, analytics, agents
from app.websocket.twilio_stream import handle_twilio_media_stream
from app.websocket.browser_stream import handle_dashboard_websocket, handle_browser_voice_stream

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("sales_agent.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up AI Sales Calling Agent server...")
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.winmm.timeBeginPeriod(1)
            logger.info("Enabled Windows 1ms high-precision multimedia timer.")
        except Exception as e:
            logger.warning(f"Could not enable Windows high-precision timer: {e}")
    await connect_db()
    yield
    logger.info("Shutting down AI Sales Calling Agent server...")
    await close_db()
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.winmm.timeEndPeriod(1)
        except Exception:
            pass

app = FastAPI(
    title="Real-Time AI Voice Sales Agent",
    description="Full-duplex AI sales calling agent powered by Twilio Media Streams, Gnani STT/TTS, and LLM brain.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for local and web frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include REST API routers
app.include_router(calls.router, tags=["Calls & Twilio Webhooks"])
app.include_router(customers.router, tags=["Customers CRM"])
app.include_router(agents.router, tags=["Sales Agents"])
app.include_router(products.router, tags=["Product Knowledge"])
app.include_router(analytics.router, tags=["Call Analytics"])

# Mount WebSockets
@app.websocket("/ws/twilio-media")
async def ws_twilio_endpoint(websocket: WebSocket):
    """Bidirectional Media Stream WebSocket for Twilio."""
    await handle_twilio_media_stream(websocket)

@app.websocket("/ws/dashboard")
async def ws_dashboard_endpoint(websocket: WebSocket):
    """Real-time live broadcast WebSocket for frontend dashboard."""
    await handle_dashboard_websocket(websocket)

@app.websocket("/ws/browser-voice/{call_id}")
async def ws_browser_voice_endpoint(websocket: WebSocket, call_id: str):
    """Direct browser microphone voice testing endpoint."""
    await handle_browser_voice_stream(websocket, call_id)

@app.get("/health")
async def health_check():
    """System health check and provider readiness status."""
    db = get_db()
    db_connected = False
    if db is not None:
        try:
            await db.command("ping")
            db_connected = True
        except Exception:
            db_connected = False

    return {
        "status": "healthy",
        "twilio_configured": bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN),
        "twilio_phone": settings.TWILIO_PHONE_NUMBER,
        "gnani_configured": bool(settings.GNANI_API_KEY),
        "gnani_stt_model": settings.GNANI_STT_MODEL,
        "gnani_tts_voice": settings.GNANI_TTS_VOICE,
        "llm_provider": settings.LLM_PROVIDER,
        "mongodb_connected": db_connected,
        "silence_threshold_ms": settings.SILENCE_THRESHOLD_MS
    }

# Mount React Vite frontend build
frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
dist_dir = frontend_dir / "dist"

if dist_dir.exists():
    # Mount built assets
    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/")
    async def serve_react_root():
        index_file = dist_dir / "index.html"
        return FileResponse(index_file)

    @app.get("/{full_path:path}")
    async def serve_spa_fallback(full_path: str):
        # Allow API, Twilio, and WebSocket routes to pass through
        if full_path.startswith(("api", "twilio", "ws", "docs", "openapi.json", "health")):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        index_file = dist_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse({"message": "Frontend not found, see /docs for API"})

elif frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    @app.get("/")
    async def serve_index():
        index_file = frontend_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse({"message": "Frontend index.html not found, see /docs for Swagger UI"})


