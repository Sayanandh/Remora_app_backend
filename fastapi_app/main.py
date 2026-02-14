import logging
import os
import time
import threading

import dotenv
import socketio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from starlette.responses import JSONResponse
from starlette.status import HTTP_200_OK
from starlette.types import Scope
from starlette.middleware.base import BaseHTTPMiddleware

from .auth import router as auth_router
from .config import get_settings
from .realtime import sio
from . import state
from .recorder import record_audio
from .routers_activities import router as activities_router
from .routers_alerts import router as alerts_router
from .routers_locations import router as locations_router
from .routers_notifications import router as notifications_router
from .routers_patients import router as patients_router
from .routers_recipients import router as recipients_router
from .routers_sos import router as sos_router
from .routers_sos import router as sos_router
from .routers_users import router as users_router
from . import routers_iot

# Configure logging to show INFO level and above in console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

dotenv.load_dotenv()

settings = get_settings()


# Request logging middleware
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        # Log incoming request
        client_host = request.client.host if request.client else 'unknown'
        logger.info(f"[REQUEST] {request.method} {request.url.path} - Client: {client_host}")
        if request.url.query:
            logger.info(f"[REQUEST] Query params: {request.url.query}")
        
        # Log important headers for debugging ngrok issues
        if request.url.path.startswith('/api/sos'):
            ngrok_header = request.headers.get('ngrok-skip-browser-warning', 'NOT SET')
            user_agent = request.headers.get('user-agent', 'NOT SET')
            content_type = request.headers.get('content-type', 'NOT SET')
            logger.info(f"[REQUEST] Headers - ngrok-skip-browser-warning: {ngrok_header}, User-Agent: {user_agent[:50] if len(user_agent) > 50 else user_agent}, Content-Type: {content_type}")
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        logger.info(f"[RESPONSE] {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.3f}s")
        
        return response

# Check for required environment variables on startup
if not settings.database_url:
    import sys
    print("\n" + "="*60, file=sys.stderr)
    print("ERROR: DATABASE_URL environment variable is not set!", file=sys.stderr)
    print("="*60, file=sys.stderr)
    print("Please set DATABASE_URL in your .env file or environment variables.", file=sys.stderr)
    print("Example: DATABASE_URL=mongodb+srv://user:pass@cluster.mongodb.net/remora", file=sys.stderr)
    print("="*60 + "\n", file=sys.stderr)
    # Don't exit immediately, let it fail on first DB access with a clearer error

app = FastAPI(title=settings.app_name)

# Add request logging middleware first (outermost)
app.add_middleware(RequestLoggingMiddleware)

if settings.client_origin == "*":
    origins = ["*"]
else:
    origins = [settings.client_origin]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])


# Audio Recording Models and Endpoints
class ToggleRequest(BaseModel):
    source: str  # esp8266 / flutter


@app.post("/toggle")
def toggle_recording(req: ToggleRequest):
    """Start or stop audio recording from specified source."""
    if not state.recording:
        state.stop_event.clear()
        state.recording_thread = threading.Thread(target=record_audio)
        state.recording_thread.start()
        state.recording = True
        return {
            "recording": True,
            "action": "started",
            "source": req.source
        }
    else:
        state.stop_event.set()
        state.recording_thread.join()
        state.recording = False
        return {
            "recording": False,
            "action": "stopped",
            "source": req.source
        }


@app.get("/recording-status")
def get_recording_status():
    """Get current recording status."""
    return {
        "recording": state.recording
    }


@app.get("/health", status_code=HTTP_200_OK)
async def health():
    return JSONResponse({"status": "ok"})


# Backward compatibility: include routers on main app for old paths without /api prefix
# This allows both /users/* and /api/users/* to work, etc.
app.include_router(auth_router)  # /auth/* and /api/auth/*
app.include_router(users_router)  # /users/* and /api/users/*
app.include_router(patients_router)  # /patients/* and /api/patients/*
app.include_router(routers_iot.router) # /sensor-data, etc. for IoT Legacy

api = FastAPI(root_path="/api")
api.include_router(auth_router)
api.include_router(users_router)
api.include_router(recipients_router)
api.include_router(sos_router)
api.include_router(alerts_router)
api.include_router(notifications_router)
api.include_router(locations_router)
api.include_router(activities_router)
api.include_router(patients_router)
api.include_router(routers_iot.router) # /api/command, /api/navigate

app.mount("/api", api)


socket_app = socketio.ASGIApp(sio, other_asgi_app=app)


def get_app() -> callable:
    # Helper for uvicorn: uvicorn fastapi_app.main:get_app
    return socket_app


async def app_scope(scope: Scope, receive, send):
    # Entry point when running with `uvicorn fastapi_app.main:app_scope`.
    await socket_app(scope, receive, send)




