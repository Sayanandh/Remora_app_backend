from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from .auth import get_current_user
from .db import get_database, serialize_mongo_document
from .realtime import emit_alert_new

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertCreate(BaseModel):
    recipientId: str
    title: str
    message: str
    type: str
    severity: str | None = None


@router.get("/", response_model=List[Dict[str, Any]])
async def list_alerts(
    recipientId: Optional[str] = Query(default=None),
    _current_user: Dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    where: Dict[str, Any] = {}
    if recipientId:
        where["recipientId"] = recipientId
    cursor = db["Alert"].find(where).sort("createdAt", -1)
    alerts: List[Dict[str, Any]] = []
    async for doc in cursor:
        alerts.append(serialize_mongo_document(doc) or {})
    return alerts


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_alert(
    body: AlertCreate,
    _current_user: Dict[str, Any] = Depends(get_current_user),
):
    if not body.recipientId or not body.title or not body.message or not body.type:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing fields")

    db = get_database()
    doc: Dict[str, Any] = {
        "recipientId": body.recipientId,
        "title": body.title,
        "message": body.message,
        "type": body.type,
        "severity": body.severity or "INFO",
        "isAcknowledged": False,
        "createdAt": datetime.now(timezone.utc),
    }
    result = await db["Alert"].insert_one(doc)
    created = await db["Alert"].find_one({"_id": result.inserted_id})
    payload = serialize_mongo_document(created) or {}

    emit_alert_new(body.recipientId, payload)
    return payload


@router.post("/{alert_id}/ack")
async def acknowledge_alert(
    alert_id: str,
    _current_user: Dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    updated = await db["Alert"].find_one_and_update(
        {"_id": ObjectId(alert_id)},
        {"$set": {"isAcknowledged": True}},
        return_document=True,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return serialize_mongo_document(updated)






