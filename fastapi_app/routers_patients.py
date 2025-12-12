import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
from bson import ObjectId

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from .auth import get_current_caregiver, get_current_patient, get_current_user
from .db import get_database, serialize_mongo_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patients", tags=["patients"])


class PatientLocationPing(BaseModel):
    latitude: float
    longitude: float
    accuracy: float | None = None
    battery: int | None = None
    recordedAt: datetime | None = None


async def _ensure_patient_profile(user_id: str) -> Dict[str, Any]:
    """
    Make sure a PatientProfile document exists for this user.

    Schema (Mongo collection: PatientProfile):
    - _id: ObjectId
    - userId: string (User._id of the patient)
    - createdAt: datetime (UTC)
    - updatedAt: datetime (UTC)
    """
    db = get_database()
    existing = await db["PatientProfile"].find_one({"userId": user_id})
    if existing:
        # touch updatedAt
        await db["PatientProfile"].update_one(
            {"_id": existing["_id"]},
            {"$set": {"updatedAt": datetime.now(timezone.utc)}},
        )
        return serialize_mongo_document(existing) or {}

    doc: Dict[str, Any] = {
        "userId": user_id,
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    result = await db["PatientProfile"].insert_one(doc)
    created = await db["PatientProfile"].find_one({"_id": result.inserted_id})
    return serialize_mongo_document(created) or {}


@router.post("/me/location", status_code=status.HTTP_201_CREATED)
async def ping_my_location(
    body: PatientLocationPing,
    current_user: Dict[str, Any] = Depends(get_current_patient),
):
    """
    Endpoint for PATIENT users to send their current device location.

    The mobile app can call this every ~30 seconds after login.

    Side effect:
    - Ensures a PatientProfile document exists for the current user.
    - Inserts a new record into PatientLocation linked via userId.
    """
    db = get_database()
    db_name = db.name
    user_id = current_user["id"]
    user_email = current_user.get("email", "unknown")

    logger.info(f"[PATIENT LOCATION] Saving location for patient: email={user_email}, userId={user_id}")
    logger.info(f"[PATIENT LOCATION] Database: '{db_name}', Collections: 'PatientProfile', 'PatientLocation'")
    logger.info(f"[PATIENT LOCATION] Location data: lat={body.latitude}, lng={body.longitude}, accuracy={body.accuracy}")

    # Ensure per-patient profile document exists
    await _ensure_patient_profile(user_id)

    now = datetime.now(timezone.utc)
    doc: Dict[str, Any] = {
        "userId": user_id,
        "latitude": body.latitude,
        "longitude": body.longitude,
        "accuracy": body.accuracy,
        "battery": body.battery,
        "recordedAt": body.recordedAt or now,
        "updatedAt": now,
    }

    # Upsert so we keep only the latest location per patient (replace instead of creating new docs)
    await db["PatientLocation"].update_one(
        {"userId": user_id},
        {"$set": doc, "$setOnInsert": {"createdAt": now}},
        upsert=True,
    )

    # Return the latest document
    created = await db["PatientLocation"].find_one({"userId": user_id})
    payload = serialize_mongo_document(created)
    if not payload:
        logger.error(f"[PATIENT LOCATION] ✗ Failed to save location for userId={user_id} in database '{db_name}'")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save patient location",
        )
    logger.info(f"[PATIENT LOCATION] ✓ Location saved successfully: userId={user_id}, locationId={payload.get('id')} in database '{db_name}', collection 'PatientLocation'")
    return payload


class ConnectCaregiverRequest(BaseModel):
    # This could be a code shown on the caregiver app, or a caregiver user id.
    caregiverCode: str


@router.post("/connect-caregiver")
async def connect_to_caregiver(
    body: ConnectCaregiverRequest,
    current_user: Dict[str, Any] = Depends(get_current_patient),
):
    """
    Connect a PATIENT to a CAREGIVER using caregiver email (Gmail supported) or ID.
    Creates a PatientCaregiverLink document.
    """
    db = get_database()
    patient_id = current_user["id"]
    patient_name = current_user.get("name", "Patient")
    
    # Normalize the caregiver code (trim whitespace, lowercase for email)
    caregiver_code = body.caregiverCode.strip()
    
    # Try to find caregiver by email or ID
    from bson import ObjectId
    query: Dict[str, Any] = {"role": "CAREGIVER"}
    
    # Check if it's an email (contains @) or try as ObjectId
    if "@" in caregiver_code:
        # It's an email - search case-insensitively
        query["email"] = {"$regex": f"^{caregiver_code}$", "$options": "i"}
    else:
        # Try to parse as ObjectId first
        try:
            if len(caregiver_code) == 24:
                query["_id"] = ObjectId(caregiver_code)
            else:
                # If not ObjectId format, treat as email anyway (might be partial)
                query["email"] = {"$regex": caregiver_code, "$options": "i"}
        except:
            # Invalid ObjectId, treat as email search
            query["email"] = {"$regex": caregiver_code, "$options": "i"}
    
    caregiver = await db["User"].find_one(query)
    
    if not caregiver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Caregiver not found with email/code: {caregiver_code}. Please check the email address and try again."
        )
    
    caregiver_id = str(caregiver["_id"])
    caregiver_email = caregiver.get("email", "")
    caregiver_name = caregiver.get("name", "Caregiver")
    
    # Prevent self-connection
    if caregiver_id == patient_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot connect to yourself as a caregiver"
        )
    
    # Check if link already exists
    existing = await db["PatientCaregiverLink"].find_one({
        "patientUserId": patient_id,
        "caregiverUserId": caregiver_id,
    })
    
    if existing:
        return {
            "status": "ALREADY_CONNECTED",
            "message": f"You are already connected to {caregiver_name} ({caregiver_email})",
            "caregiverId": caregiver_id,
            "caregiverName": caregiver_name,
            "caregiverEmail": caregiver_email,
        }
    
    # Create the link
    link_doc: Dict[str, Any] = {
        "patientUserId": patient_id,
        "caregiverUserId": caregiver_id,
        "status": "ACTIVE",
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    result = await db["PatientCaregiverLink"].insert_one(link_doc)
    
    logger.info(f"[PATIENT] Connected patient {patient_id} ({patient_name}) to caregiver {caregiver_id} ({caregiver_name})")
    
    return {
        "status": "CONNECTED",
        "message": f"Successfully connected to {caregiver_name}",
        "caregiverId": caregiver_id,
        "caregiverName": caregiver_name,
        "caregiverEmail": caregiver_email,
    }


@router.get("/me/caregivers", response_model=List[Dict[str, Any]])
async def get_my_caregivers(
    current_user: Dict[str, Any] = Depends(get_current_patient),
):
    """
    Get list of all caregivers connected to the current patient.
    """
    db = get_database()
    patient_id = current_user["id"]
    
    # Find all active links for this patient
    links = await db["PatientCaregiverLink"].find({
        "patientUserId": patient_id,
        "status": "ACTIVE",
    }).to_list(length=100)
    
    caregivers: List[Dict[str, Any]] = []
    for link in links:
        caregiver_id = link.get("caregiverUserId")
        if caregiver_id:
            caregiver = await db["User"].find_one({"_id": ObjectId(caregiver_id)})
            if caregiver:
                serialized = serialize_mongo_document(caregiver)
                if serialized:
                    caregivers.append({
                        "id": serialized.get("id"),
                        "name": serialized.get("name"),
                        "email": serialized.get("email"),
                        "connectedAt": link.get("createdAt").isoformat() if link.get("createdAt") else None,
                    })
    
    return caregivers


@router.post("/sos")
async def send_sos_alert(
    current_user: Dict[str, Any] = Depends(get_current_patient),
):
    """
    Send an SOS alert for a PATIENT user.
    Creates an alert and notifies connected caregivers.
    """
    db = get_database()
    patient_id = current_user["id"]
    patient_name = current_user.get("name", "Patient")
    
    # Find connected caregivers
    links = await db["PatientCaregiverLink"].find({
        "patientUserId": patient_id,
        "status": "ACTIVE",
    }).to_list(length=100)
    
    caregiver_ids = [link["caregiverUserId"] for link in links]
    
    # Get patient's latest location
    latest_location = await db["PatientLocation"].find_one(
        {"userId": patient_id},
        sort=[("recordedAt", -1)]
    )
    
    # Create SOS alert
    alert_doc: Dict[str, Any] = {
        "type": "SOS",
        "severity": "CRITICAL",
        "title": f"SOS Alert from {patient_name}",
        "message": f"{patient_name} has triggered an SOS alert. Immediate attention required.",
        "patientUserId": patient_id,
        "caregiverUserIds": caregiver_ids,
        "latitude": latest_location.get("latitude") if latest_location else None,
        "longitude": latest_location.get("longitude") if latest_location else None,
        "isAcknowledged": False,
        "createdAt": datetime.now(timezone.utc),
    }
    
    result = await db["Alert"].insert_one(alert_doc)
    alert = serialize_mongo_document(await db["Alert"].find_one({"_id": result.inserted_id}))
    
    logger.info(f"[PATIENT SOS] Patient {patient_id} triggered SOS alert. Notifying {len(caregiver_ids)} caregivers.")
    
    return {
        "status": "SENT",
        "message": "SOS alert sent successfully",
        "alertId": alert.get("id") if alert else None,
        "caregiversNotified": len(caregiver_ids),
    }


@router.get("/caregiver/my-patients", response_model=List[Dict[str, Any]])
async def list_caregiver_patients(
    current_user: Dict[str, Any] = Depends(get_current_caregiver),
):
    """
    For a CAREGIVER, return all linked patients with their latest location (if any).
    """
    db = get_database()
    caregiver_id = current_user["id"]

    links = await db["PatientCaregiverLink"].find(
        {"caregiverUserId": caregiver_id, "status": "ACTIVE"}
    ).to_list(length=200)

    patients: List[Dict[str, Any]] = []

    for link in links:
        patient_id = link.get("patientUserId")
        if not patient_id:
            continue

        patient_raw = await db["User"].find_one({"_id": ObjectId(patient_id)})
        patient = serialize_mongo_document(patient_raw)
        if not patient:
            continue

        latest_location = await db["PatientLocation"].find_one({"userId": patient_id})
        location_payload = serialize_mongo_document(latest_location) if latest_location else None

        patients.append(
            {
                "id": patient.get("id"),
                "name": patient.get("name"),
                "email": patient.get("email"),
                "location": location_payload,
            }
        )

    return patients
