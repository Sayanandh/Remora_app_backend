import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from .auth import get_current_user
from .db import get_database, serialize_mongo_document
from .realtime import emit_alert_new, emit_device_voice_toggle

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sos", tags=["sos"])


class SOSRequest(BaseModel):
    type: str = "sos"
    device: str
    timestamp: Optional[int] = None
    userId: Optional[str] = None  # Optional: can be sent in body or query param
    deviceToken: Optional[str] = None  # Device token for dynamic user identification


class DeviceRegisterRequest(BaseModel):
    deviceName: Optional[str] = "ESP8266"
    deviceType: Optional[str] = "esp8266"


class VoiceToggleRequest(BaseModel):
    """Request from IoT device to toggle voice recording on the patient app."""
    device: str = "esp8266"
    deviceToken: Optional[str] = None


@router.get("/voice-toggle")
async def voice_toggle_get():
    """
    GET handler for voice-toggle endpoint - returns helpful error message.
    This endpoint only accepts POST requests from IoT devices.
    """
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail={
            "error": "Method Not Allowed",
            "message": "This endpoint only accepts POST requests. Use POST with JSON body containing 'deviceToken'.",
            "example": {
                "method": "POST",
                "url": "/api/sos/voice-toggle",
                "headers": {
                    "Content-Type": "application/json",
                    "ngrok-skip-browser-warning": "true"
                },
                "body": {
                    "device": "esp8266",
                    "deviceToken": "your-device-token-here"
                }
            }
        }
    )


@router.post("/voice-toggle", status_code=status.HTTP_200_OK)
async def voice_toggle(
    request: Request,
    body: VoiceToggleRequest,
    deviceToken: Optional[str] = Query(default=None, description="Device token"),
):
    """
    When the IoT button is pressed (for voice recording), the device calls this endpoint.
    The backend notifies the patient app via Socket.IO to start or stop voice recording.
    Same device token as SOS; no auth required (device token identifies the patient).
    """
    # Log request details for debugging
    try:
        user_agent = request.headers.get("user-agent", "unknown")
        ngrok_header = request.headers.get("ngrok-skip-browser-warning", "not set")
        logger.info(f"[VOICE TOGGLE] POST request - User-Agent: {user_agent[:50]}, ngrok-header: {ngrok_header}")
    except Exception:
        pass
    
    token = body.deviceToken or deviceToken
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="deviceToken is required (body or query)",
        )
    db = get_database()
    user_raw = await db["User"].find_one({"deviceTokens.token": token})
    if not user_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid device token",
        )
    user_id = str(user_raw["_id"])
    emit_device_voice_toggle(user_id)
    logger.info(f"[VOICE TOGGLE] Emitted device:voice_toggle for user {user_id}")
    return {"success": True, "message": "Voice toggle sent to app", "userId": user_id}


@router.post("/register-device", status_code=status.HTTP_200_OK)
async def register_device(
    body: DeviceRegisterRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Register a device (like ESP8266) for the currently logged-in user.
    Returns a device token that can be used for SOS requests.
    
    The device token should be stored on the ESP8266 and sent with SOS requests.
    """
    db = get_database()
    user_id = current_user["id"]
    
    # Generate a secure device token
    device_token = secrets.token_urlsafe(32)  # 32 bytes = 43-44 char URL-safe string
    
    # Store device token in user document
    # Add deviceTokens array if it doesn't exist, or append to existing array
    now = datetime.now(timezone.utc)
    
    device_info = {
        "token": device_token,
        "deviceName": body.deviceName,
        "deviceType": body.deviceType,
        "registeredAt": now,
    }
    
    # Update user document to include device token
    result = await db["User"].update_one(
        {"_id": ObjectId(user_id)},
        {
            "$push": {"deviceTokens": device_info},
            "$set": {"updatedAt": now}
        }
    )
    
    if result.modified_count == 0:
        # User might not exist (shouldn't happen, but handle gracefully)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    logger.info(f"[SOS DEVICE REGISTER] Device registered for user {user_id} - token: {device_token[:10]}...")
    
    return {
        "success": True,
        "deviceToken": device_token,
        "deviceName": body.deviceName,
        "deviceType": body.deviceType,
        "message": "Device registered successfully. Store this token on your ESP8266."
    }


@router.get("/health", status_code=status.HTTP_200_OK)
async def sos_health():
    """Health check endpoint for SOS service."""
    return {"status": "ok", "service": "sos", "message": "SOS endpoint is accessible"}


@router.post("", status_code=status.HTTP_200_OK)
async def handle_sos(
    body: SOSRequest,
    userId: Optional[str] = Query(default=None, description="User ID (can be provided as query param or in body)"),
    deviceToken: Optional[str] = Query(default=None, description="Device token for dynamic user identification"),
):
    """
    Handle SOS requests from ESP8266 or other devices.
    Updates the user's status to 'emergency' in the database.
    
    User identification can be provided via:
    - deviceToken (recommended): Token obtained from /api/sos/register-device
    - userId: Direct user ID (query param or in body)
    
    If deviceToken is provided, the user is automatically identified from the token.
    """
    try:
        logger.info(f"[SOS REQUEST RECEIVED] Device: {body.device}, Token: {deviceToken or body.deviceToken or 'None'}, UserId: {userId or body.userId or 'None'}")
        
        db = get_database()
        
        # Priority: deviceToken > userId (body) > userId (query param)
        device_token = body.deviceToken or deviceToken
        user_id = body.userId or userId
    
        user_object_id = None
        
        # If device token is provided, look up user by token
        if device_token:
            # Find user by device token
            user_raw = await db["User"].find_one({
                "deviceTokens.token": device_token
            })
            
            if not user_raw:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid device token"
                )
            
            user_object_id = user_raw["_id"]
            user_id = str(user_object_id)
            logger.info(f"[SOS] User identified via device token: {user_id}")
        
        # Fallback to userId if no device token
        elif user_id:
            try:
                user_object_id = ObjectId(user_id)
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid userId format"
                )
            
            user_raw = await db["User"].find_one({"_id": user_object_id})
            if not user_raw:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            logger.info(f"[SOS] User identified via userId: {user_id}")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either deviceToken or userId is required. Use deviceToken for dynamic user identification."
            )
        
        # Update user status to 'emergency' and update timestamp
        now = datetime.now(timezone.utc)
        result = await db["User"].update_one(
            {"_id": user_object_id},
            {
                "$set": {
                    "status": "emergency",
                    "updatedAt": now,
                    "emergencyTriggeredAt": now,  # Track when emergency was triggered
                }
            }
        )
        
        if result.modified_count == 0:
            logger.warning(f"[SOS] User {user_id} status update had no effect (may already be emergency)")
        
        # Get user info for notifications
        user_name = user_raw.get("name", "Patient")
        user_email = user_raw.get("email", "Unknown")
        
        # Find connected caregivers via PatientCaregiverLink
        links = await db["PatientCaregiverLink"].find({
            "patientUserId": user_id,
            "status": "ACTIVE",
        }).to_list(length=100)
        
        caregiver_ids = [link["caregiverUserId"] for link in links]
        
        # Get patient's latest location if available
        latest_location = await db["PatientLocation"].find_one(
            {"userId": user_id},
            sort=[("recordedAt", -1)]
        )
        
        # Create notifications for all connected caregivers
        notifications_created = 0
        for caregiver_id in caregiver_ids:
            notification_doc = {
                "userId": caregiver_id,
                "title": f"🚨 SOS Alert from {user_name}",
                "message": f"{user_name} has triggered an emergency SOS alert. Immediate attention required!",
                "type": "SOS",
                "isRead": False,
                "createdAt": now,
                "relatedPatientId": user_id,
                "relatedPatientName": user_name,
                "latitude": latest_location.get("latitude") if latest_location else None,
                "longitude": latest_location.get("longitude") if latest_location else None,
            }
            await db["Notification"].insert_one(notification_doc)
            notifications_created += 1
        
        # Create alert for real-time notification via Socket.IO
        # Use recipientId pattern for alerts (caregivers subscribe to their patient's alerts)
        alert_doc = {
            "recipientId": user_id,  # Patient ID (caregivers listen to patient alerts)
            "title": f"SOS Alert from {user_name}",
            "message": f"{user_name} ({user_email}) has triggered an emergency SOS alert.",
            "type": "SOS",
            "severity": "CRITICAL",
            "isAcknowledged": False,
            "createdAt": now,
            "patientUserId": user_id,
            "caregiverUserIds": caregiver_ids,
            "latitude": latest_location.get("latitude") if latest_location else None,
            "longitude": latest_location.get("longitude") if latest_location else None,
        }
        try:
            alert_result = await db["Alert"].insert_one(alert_doc)
            alert = serialize_mongo_document(await db["Alert"].find_one({"_id": alert_result.inserted_id}))
            
            # Emit real-time alert to caregivers (they should be listening to patient's alerts)
            if alert:
                for caregiver_id in caregiver_ids:
                    # Caregivers can subscribe to alerts for their patients
                    emit_alert_new(user_id, alert)  # Emit to patient's room, caregivers listen
        except Exception as e:
            logger.error(f"[SOS] Error creating/emitting alert: {e}", exc_info=True)
            alert = None
        
        logger.info(f"[SOS] Emergency status set for user {user_id}. Notified {notifications_created} caregivers.")
        
        # Convert UTC to IST for response
        try:
            IST = timezone(timedelta(hours=5, minutes=30))
            now_ist = now.astimezone(IST)
            timestamp_ist = now_ist.isoformat()
        except Exception as e:
            logger.error(f"[SOS] Error converting timestamp to IST: {e}", exc_info=True)
            # Fallback to UTC
            timestamp_ist = now.isoformat()
        
        # Return success response with server timestamp in IST
        return {
            "success": True,
            "message": "SOS received and user status updated to emergency",
            "userId": user_id,
            "status": "emergency",
            "device": body.device,
            "timestamp": timestamp_ist,
            "emergencyTriggeredAt": timestamp_ist,
            "caregiversNotified": notifications_created,
            "alertId": alert.get("id") if alert else None,
        }
    except HTTPException:
        # Re-raise HTTP exceptions (they're intentional)
        raise
    except Exception as e:
        logger.error(f"[SOS] Unexpected error in handle_sos: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

