from datetime import datetime, timezone
from typing import Any, Dict, List

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from .auth import get_current_user
from .db import get_database, serialize_mongo_document

router = APIRouter(prefix="/recipients", tags=["recipients"])


class RecipientCreate(BaseModel):
    name: str
    age: int | None = None
    relationship: str | None = None
    avatarUrl: str | None = None


class RecipientUpdate(BaseModel):
    name: str | None = None
    age: int | None = None
    relationship: str | None = None
    avatarUrl: str | None = None


@router.get("/", response_model=List[Dict[str, Any]])
async def list_recipients(current_user: Dict[str, Any] = Depends(get_current_user)):
    db = get_database()
    caregiver_id = current_user["id"]
    links_cursor = db["CaregiverOnRecipient"].find({"caregiverId": caregiver_id})
    recipients: List[Dict[str, Any]] = []
    async for link in links_cursor:
        rec_raw = await db["CareRecipient"].find_one({"_id": ObjectId(link["recipientId"])})
        rec = serialize_mongo_document(rec_raw)
        if rec:
            recipients.append(rec)
    return recipients


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_recipient(
    body: RecipientCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    caregiver_id = current_user["id"]

    recipient_doc: Dict[str, Any] = {
        "name": body.name,
        "age": body.age,
        "relationship": body.relationship,
        "avatarUrl": body.avatarUrl,
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    result = await db["CareRecipient"].insert_one(recipient_doc)
    await db["CaregiverOnRecipient"].insert_one(
        {
            "caregiverId": caregiver_id,
            "recipientId": str(result.inserted_id),
            "assignedAt": datetime.now(timezone.utc),
        }
    )
    created = await db["CareRecipient"].find_one({"_id": result.inserted_id})
    return serialize_mongo_document(created)


@router.get("/{recipient_id}")
async def get_recipient(recipient_id: str):
    db = get_database()
    rec_raw = await db["CareRecipient"].find_one({"_id": ObjectId(recipient_id)})
    if not rec_raw:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return serialize_mongo_document(rec_raw)


@router.put("/{recipient_id}")
async def update_recipient(recipient_id: str, body: RecipientUpdate):
    db = get_database()
    update_doc = {k: v for k, v in body.dict(exclude_unset=True).items()}
    update_doc["updatedAt"] = datetime.now(timezone.utc)
    result = await db["CareRecipient"].find_one_and_update(
        {"_id": ObjectId(recipient_id)},
        {"$set": update_doc},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return serialize_mongo_document(result)


@router.delete("/{recipient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recipient(recipient_id: str):
    db = get_database()
    await db["CaregiverOnRecipient"].delete_many({"recipientId": recipient_id})
    await db["CareRecipient"].delete_one({"_id": ObjectId(recipient_id)})
    return None






