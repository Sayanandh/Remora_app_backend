import logging
import os

import dotenv
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse
from starlette.status import HTTP_200_OK
from starlette.types import Scope

from .auth import router as auth_router
from .config import get_settings
from .realtime import sio
from .routers_activities import router as activities_router
from .routers_alerts import router as alerts_router
from .routers_locations import router as locations_router
from .routers_notifications import router as notifications_router
from .routers_patients import router as patients_router
from .routers_recipients import router as recipients_router
from .routers_users import router as users_router

# Configure logging to show INFO level and above in console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

dotenv.load_dotenv()

settings = get_settings()

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


@app.get("/health", status_code=HTTP_200_OK)
async def health():
    return JSONResponse({"status": "ok"})


# Backward compatibility: include routers on main app for old paths without /api prefix
# This allows both /users/* and /api/users/* to work, etc.
app.include_router(auth_router)  # /auth/* and /api/auth/*
app.include_router(users_router)  # /users/* and /api/users/*
app.include_router(patients_router)  # /patients/* and /api/patients/*

api = FastAPI(root_path="/api")
api.include_router(auth_router)
api.include_router(users_router)
api.include_router(recipients_router)
api.include_router(alerts_router)
api.include_router(notifications_router)
api.include_router(locations_router)
api.include_router(activities_router)
api.include_router(patients_router)

app.mount("/api", api)


socket_app = socketio.ASGIApp(sio, other_asgi_app=app)


def get_app() -> callable:
    # Helper for uvicorn: uvicorn fastapi_app.main:get_app
    return socket_app


async def app_scope(scope: Scope, receive, send):
    # Entry point when running with `uvicorn fastapi_app.main:app_scope`.
    await socket_app(scope, receive, send)




