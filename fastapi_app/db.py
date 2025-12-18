import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict
from urllib.parse import urlparse

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .config import get_settings

# India Standard Time (IST) is UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.database_url:
            logger.error("[DB] ERROR: DATABASE_URL environment variable is not set!")
            raise ValueError(
                "DATABASE_URL environment variable is required. "
                "Please set it in your .env file or environment variables. "
                "Example: DATABASE_URL=mongodb+srv://user:pass@cluster.mongodb.net/remora"
            )
        # For MongoDB Atlas (mongodb+srv://), TLS/SSL is automatically handled
        # Add connection parameters for better reliability
        try:
            _client = AsyncIOMotorClient(
                settings.database_url,
                serverSelectionTimeoutMS=30000,
                connectTimeoutMS=30000,
                retryWrites=True,
            )
            # Log connection info (mask password)
            safe_url = settings.database_url
            if safe_url and "@" in safe_url:
                parts = safe_url.split("@")
                if ":" in parts[0]:
                    user_pass = parts[0].split("://")[1]
                    if ":" in user_pass:
                        user = user_pass.split(":")[0]
                        safe_url = safe_url.replace(user_pass, f"{user}:***")
            logger.info(f"[DB] Connecting to MongoDB: {safe_url}")
        except Exception as e:
            logger.error(f"[DB] Failed to create MongoDB client: {type(e).__name__}: {str(e)}")
            raise
    return _client


def _get_db_name_from_url(url: str) -> str | None:
    """Extract the database name from a MongoDB URL if present."""
    parsed = urlparse(url)
    # path is like "/Remora" or "/remora_caregiver"
    if parsed.path and parsed.path != "/":
        return parsed.path.lstrip("/").split("/", 1)[0].split("?", 1)[0]
    return None


def get_database() -> AsyncIOMotorDatabase:
    """Return the target database, using the exact name from DATABASE_URL.

    If the DATABASE_URL includes a path, we use that as the db name (exact case).
    Otherwise we fall back to "remora" (lowercase default).
    
    Note: MongoDB is case-sensitive. If you have an existing database like "Remora",
    make sure your DATABASE_URL uses the exact same case: /Remora
    """
    client = get_client()
    settings = get_settings()
    if not settings.database_url:
        raise ValueError("DATABASE_URL is not set. Cannot determine database name.")
    # Use the database name exactly as it appears in the URL (case-sensitive)
    db_name = _get_db_name_from_url(settings.database_url) or "remora"
    logger.info(f"[DB] Using database: '{db_name}' (exact case from URL)")
    return client[db_name]


def _convert_to_ist(dt: datetime) -> str:
    """Convert UTC datetime to India Standard Time (IST) and return as ISO string."""
    try:
        if dt.tzinfo is None:
            # If no timezone info, assume it's UTC
            dt = dt.replace(tzinfo=timezone.utc)
        # Convert to IST
        ist_time = dt.astimezone(IST)
        return ist_time.isoformat()
    except Exception as e:
        # Fallback to UTC if conversion fails
        logger.warning(f"[DB] Failed to convert datetime to IST: {e}, using UTC")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()


def serialize_mongo_document(doc: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not doc:
        return None
    result = dict(doc)
    # Map Mongo `_id` to `id` to mimic Prisma's schema mapping.
    _id = result.pop("_id", None)
    if _id is not None:
        result["id"] = str(_id)
    
    # Convert datetime objects to IST and return as ISO format strings
    # MongoDB stores in UTC, but we convert to IST for API responses
    for key, value in result.items():
        if isinstance(value, datetime):
            # Convert UTC to IST and return as ISO string
            result[key] = _convert_to_ist(value)
        elif isinstance(value, dict):
            # Recursively handle nested dictionaries
            result[key] = _serialize_datetime_in_dict(value)
        elif isinstance(value, list):
            # Handle lists that might contain datetime objects
            result[key] = [_serialize_datetime_in_dict(item) if isinstance(item, dict) 
                          else _convert_to_ist(item) if isinstance(item, datetime) else item 
                          for item in value]
    
    return result


def _serialize_datetime_in_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to recursively serialize datetime objects in dictionaries."""
    result = {}
    for key, value in d.items():
        if isinstance(value, datetime):
            result[key] = _convert_to_ist(value)
        elif isinstance(value, dict):
            result[key] = _serialize_datetime_in_dict(value)
        elif isinstance(value, list):
            result[key] = [_serialize_datetime_in_dict(item) if isinstance(item, dict) 
                          else _convert_to_ist(item) if isinstance(item, datetime) else item 
                          for item in value]
        else:
            result[key] = value
    return result




