from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from .auth import get_current_user
from .db import get_database, serialize_mongo_document

router = APIRouter(prefix="/activities", tags=["activities"])


class ActivityCreate(BaseModel):
    recipientId: str
    kind: str
    value: float | None = None
    unit: str | None = None
    metadata: Dict[str, Any] | None = None
    recordedAt: datetime | None = None


@router.get("/", response_model=List[Dict[str, Any]])
async def list_activities(
    recipientId: Optional[str] = Query(default=None),
    kind: Optional[str] = Query(default=None),
    from_: Optional[str] = Query(default=None, alias="from"),
    to: Optional[str] = Query(default=None),
    _current_user: Dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    where: Dict[str, Any] = {}
    if recipientId:
        where["recipientId"] = recipientId
    if kind:
        where["kind"] = kind
    if from_ or to:
        recorded: Dict[str, Any] = {}
        if from_:
            recorded["$gte"] = datetime.fromisoformat(from_)
        if to:
            recorded["$lte"] = datetime.fromisoformat(to)
        where["recordedAt"] = recorded

    cursor = (
        db["Activity"]
        .find(where)
        .sort("recordedAt", -1)
        .limit(200)
    )

    items: List[Dict[str, Any]] = []
    async for doc in cursor:
        items.append(serialize_mongo_document(doc) or {})
    return items


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_activity(
    body: ActivityCreate,
    _current_user: Dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    if not body.recipientId or not body.kind:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing fields")

    doc: Dict[str, Any] = {
        "recipientId": body.recipientId,
        "kind": body.kind,
        "value": body.value,
        "unit": body.unit,
        "metadata": body.metadata,
        "recordedAt": body.recordedAt or datetime.utcnow(),
    }
    result = await db["Activity"].insert_one(doc)
    created = await db["Activity"].find_one({"_id": ObjectId(result.inserted_id)})
    return serialize_mongo_document(created)






