from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from .auth import get_current_user
from .db import get_database, serialize_mongo_document

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    db = get_database()
    user_raw = await db["User"].find_one({"_id": ObjectId(current_user["id"])})
    user = serialize_mongo_document(user_raw)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user.get("name"),
        "role": user.get("role"),
    }


@router.get("/caregivers", response_model=List[Dict[str, Any]])
async def search_caregivers(
    query: Optional[str] = Query(default=None, description="Search by name or email (Gmail supported)"),
    _current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Search for caregivers by name or email (including Gmail).
    Returns list of caregivers matching the query.
    Prioritizes exact email matches.
    """
    db = get_database()
    search_filter: Dict[str, Any] = {"role": "CAREGIVER"}
    
    if query:
        query = query.strip().lower()  # Normalize query
        # Check if query looks like an email
        is_email_query = "@" in query
        
        from bson.regex import Regex
        if is_email_query:
            # For email queries, prioritize exact match, then partial match
            search_filter["$or"] = [
                {"email": query},  # Exact match (case-insensitive handled by MongoDB)
                {"email": Regex(query, "i")},  # Partial match
            ]
        else:
            # For name queries, search by name or email
            search_filter["$or"] = [
                {"name": Regex(query, "i")},
                {"email": Regex(query, "i")},
            ]
    
    cursor = db["User"].find(search_filter).limit(50)
    caregivers: List[Dict[str, Any]] = []
    exact_matches: List[Dict[str, Any]] = []
    
    async for doc in cursor:
        serialized = serialize_mongo_document(doc)
        if serialized:
            caregiver_data = {
                "id": serialized.get("id"),
                "name": serialized.get("name"),
                "email": serialized.get("email"),
            }
            # Prioritize exact email matches
            if query and "@" in query and serialized.get("email", "").lower() == query:
                exact_matches.append(caregiver_data)
            else:
                caregivers.append(caregiver_data)
    
    # Return exact matches first, then others
    return exact_matches + caregivers






