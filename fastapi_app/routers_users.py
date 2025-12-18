from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from .auth import get_current_user, get_current_caregiver
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


@router.get("/me/patients", response_model=List[Dict[str, Any]])
async def get_my_patients(
    current_user: Dict[str, Any] = Depends(get_current_caregiver),
):
    """
    Get list of all patients connected to the current caregiver.
    Returns patients that have connected to this caregiver via PatientCaregiverLink.
    """
    db = get_database()
    caregiver_id = current_user["id"]
    
    # Find all active links where this caregiver is connected
    links = await db["PatientCaregiverLink"].find({
        "caregiverUserId": caregiver_id,
        "status": "ACTIVE",
    }).to_list(length=100)
    
    patients: List[Dict[str, Any]] = []
    for link in links:
        patient_id = link.get("patientUserId")
        if patient_id:
            patient = await db["User"].find_one({"_id": ObjectId(patient_id)})
            if patient:
                serialized = serialize_mongo_document(patient)
                if serialized:
                    # Get patient's latest location if available
                    latest_location = await db["PatientLocation"].find_one(
                        {"userId": patient_id},
                        sort=[("recordedAt", -1)]
                    )
                    
                    patient_data = {
                        "id": serialized.get("id"),
                        "name": serialized.get("name"),
                        "email": serialized.get("email"),
                        "connectedAt": link.get("createdAt").isoformat() if link.get("createdAt") else None,
                    }
                    
                    # Add latest location if available
                    if latest_location:
                        patient_data["latestLocation"] = {
                            "latitude": latest_location.get("latitude"),
                            "longitude": latest_location.get("longitude"),
                            "recordedAt": latest_location.get("recordedAt").isoformat() if latest_location.get("recordedAt") else None,
                            "accuracy": latest_location.get("accuracy"),
                            "battery": latest_location.get("battery"),
                        }
                    
                    patients.append(patient_data)
    
    return patients






