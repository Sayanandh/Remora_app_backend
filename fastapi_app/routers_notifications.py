from datetime import datetime, timezone
from typing import Any, Dict, List

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from .auth import get_current_user
from .db import get_database, serialize_mongo_document

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationCreate(BaseModel):
    title: str
    message: str
    type: str


@router.get("/", response_model=List[Dict[str, Any]])
async def list_notifications(current_user: Dict[str, Any] = Depends(get_current_user)):
    db = get_database()
    user_id = current_user["id"]
    cursor = db["Notification"].find({"userId": user_id}).sort("createdAt", -1)
    items: List[Dict[str, Any]] = []
    async for doc in cursor:
        items.append(serialize_mongo_document(doc) or {})
    return items


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_notification(
    body: NotificationCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    if not body.title or not body.message or not body.type:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing fields")

    db = get_database()
    doc: Dict[str, Any] = {
        "userId": current_user["id"],
        "title": body.title,
        "message": body.message,
        "type": body.type,
        "isRead": False,
        "createdAt": datetime.now(timezone.utc),
    }
    result = await db["Notification"].insert_one(doc)
    created = await db["Notification"].find_one({"_id": result.inserted_id})
    return serialize_mongo_document(created)


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    _current_user: Dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    updated = await db["Notification"].find_one_and_update(
        {"_id": ObjectId(notification_id)},
        {"$set": {"isRead": True}},
        return_document=True,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return serialize_mongo_document(updated)






