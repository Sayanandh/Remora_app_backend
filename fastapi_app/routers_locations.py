from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from .auth import get_current_user
from .db import get_database, serialize_mongo_document
from .realtime import emit_location_new

router = APIRouter(prefix="/locations", tags=["locations"])


class LocationCreate(BaseModel):
    recipientId: str
    latitude: float
    longitude: float
    accuracy: float | None = None
    battery: int | None = None
    recordedAt: datetime | None = None


@router.get("/", response_model=List[Dict[str, Any]])
async def list_locations(
    recipientId: Optional[str] = Query(default=None),
    limit: Optional[int] = Query(default=50),
    _current_user: Dict[str, Any] = Depends(get_current_user),
):
    if not recipientId:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="recipientId required")

    db = get_database()
    cursor = (
        db["Location"]
        .find({"recipientId": recipientId})
        .sort("recordedAt", -1)
        .limit(limit or 50)
    )
    items: List[Dict[str, Any]] = []
    async for doc in cursor:
        items.append(serialize_mongo_document(doc) or {})
    return items


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_location(
    body: LocationCreate,
    _current_user: Dict[str, Any] = Depends(get_current_user),
):
    if not body.recipientId or body.latitude is None or body.longitude is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing fields")

    db = get_database()
    doc: Dict[str, Any] = {
        "recipientId": body.recipientId,
        "latitude": body.latitude,
        "longitude": body.longitude,
        "accuracy": body.accuracy,
        "battery": body.battery,
        "recordedAt": body.recordedAt or datetime.now(timezone.utc),
    }
    result = await db["Location"].insert_one(doc)
    created = await db["Location"].find_one({"_id": ObjectId(result.inserted_id)})
    payload = serialize_mongo_document(created) or {}
    emit_location_new(body.recipientId, payload)
    return payload






