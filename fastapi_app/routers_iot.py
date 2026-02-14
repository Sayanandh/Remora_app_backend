# routers_iot.py
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import time
import logging
import os
import tempfile
import asyncio

from .utils import ai_module

router = APIRouter(
    tags=["IoT & AI Integration"]
)

logger = logging.getLogger(__name__)

# ============================================================
# 📦 DATA MODELS
# ============================================================

class SensorData(BaseModel):
    distance: float
    timestamp: float = None
    device_id: str

class SensorDataResponse(SensorData):
    id: int

class TextCommand(BaseModel):
    text: str

class UltrasoundData(BaseModel):
    distance: float
    sensor_id: str = "esp8266_01"
    timestamp: int = None

# In-memory storage for sensor data
sensor_store = []

# ============================================================
# 🌡️ SENSOR DATA ENDPOINTS (from iot/mian.py)
# ============================================================

@router.post("/sensor-data", response_model=SensorDataResponse)
async def receive_sensor_data(data: SensorData):
    """Receive sensor data from Arduino via Laptop 2"""
    try:
        # Add ID and store the data
        data_id = len(sensor_store) + 1
        
        # Ensure timestamp
        if not data.timestamp:
            data.timestamp = time.time()
            
        response_data = SensorDataResponse(
            id=data_id,
            **data.dict()
        )
        sensor_store.append(response_data)
        
        # Log the received data
        logger.info(f"✅ Received: {data.distance}cm from {data.device_id}")
        
        return response_data
    except Exception as e:
        logger.error(f"❌ Error processing data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sensor-data", response_model=List[SensorDataResponse])
async def get_all_sensor_data():
    """Get all stored sensor data"""
    return sensor_store

@router.get("/sensor-data/latest", response_model=SensorDataResponse)
async def get_latest_sensor_data():
    """Get the latest sensor reading"""
    if not sensor_store:
        raise HTTPException(status_code=404, detail="No data available")
    return sensor_store[-1]

@router.delete("/sensor-data")
async def clear_data():
    """Clear all stored data"""
    sensor_store.clear()
    return {"message": "All data cleared", "count": 0}

@router.get("/test-connection")
async def test_connection():
    """Test endpoint to verify ngrok is working"""
    return {
        "status": "active", 
        "message": "Server is reachable via ngrok!",
        "timestamp": time.time(),
        "data_count": len(sensor_store)
    }

# ============================================================
# 🤖 AI & NAVIGATION ENDPOINTS (from main/app.py)
# ============================================================

@router.post("/command")
async def api_command(command: TextCommand):
    """
    Process text command from ESP8266 or App
    """
    try:
        if not command.text or not command.text.strip():
            raise HTTPException(status_code=422, detail="Empty command text")
        text = command.text.strip()
        logger.info(f"📝 Received text command: {text}")

        # Intent classification
        intent_data = ai_module.mistral_intent(text)
        if not intent_data or intent_data.get("intent") == "error":
            # Just a warning, don't fail hard if LLM is offline, maybe fallback?
            logger.warning("Intent classification failed or LLM offline")
        
        return {
            "status": "success",
            "recognized_text": text,
            "intent": intent_data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Command error: {e}")
        raise HTTPException(status_code=500, detail=f"Command processing error: {str(e)}")

@router.post("/navigate")
async def api_navigate(obj_data: dict, background_tasks: BackgroundTasks):
    """
    Process navigation request: {"object": "chair", "bbox": [...], "distance": 100}
    """
    try:
        if "object" not in obj_data:
            raise HTTPException(status_code=400, detail="Missing 'object' field")

        logger.info(f"🧭 Navigation request for: {obj_data['object']}")
        direction_text = ai_module.find_obj(obj_data)

        # Speak the navigation directions (async)
        background_tasks.add_task(ai_module.text_to_speech, direction_text)

        return {
            "status": "success",
            "navigation_message": direction_text,
            "tts_file": "output.mp3"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Navigation error: {e}")
        raise HTTPException(status_code=500, detail=f"Navigation error: {str(e)}")

@router.post("/ultrasound-nav")
async def api_ultrasound_nav(data: UltrasoundData, background_tasks: BackgroundTasks):
    """
    Receive ultrasound distance data and provide audio feedback
    """
    try:
        distance_m = data.distance / 100  # cm → meters
        logger.info(f"📊 Ultrasound distance: {distance_m:.2f} m from sensor {data.sensor_id}")

        if distance_m < 0.5:
            nav_msg = "Obstacle very close! Stop."
        elif distance_m < 2.0:
            nav_msg = "Obstacle ahead, proceed carefully."
        else:
            nav_msg = "Path clear, move forward."

        # TTS if needed (maybe throttle this in real app to avoid spam)
        background_tasks.add_task(ai_module.text_to_speech, nav_msg)

        # Optional: send buzzer flag
        buzzer_flag = distance_m < 1.0

        return {
            "status": "success",
            "navigation_message": nav_msg,
            "distance_m": distance_m,
            "buzzer": buzzer_flag
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ultrasound data error: {str(e)}")

# ============================================================
# 🎤 AUDIO PROCESSING ENDPOINT (Backup feature for voice recording)
# ============================================================

@router.post("/process-audio")
async def process_audio(audio_file: UploadFile = File(...)):
    """
    Process audio file from app (backup feature).
    Receives audio file, converts to text using speech_to_text, and returns transcription.
    Supports .m4a, .mp3, .wav formats.
    """
    try:
        # Validate file type
        allowed_extensions = ['.m4a', '.mp3', '.wav', '.aac']
        file_ext = os.path.splitext(audio_file.filename or '')[1].lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
            )
        
        logger.info(f"🎤 Received audio file: {audio_file.filename} ({file_ext})")
        
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            tmp_path = tmp_file.name
            content = await audio_file.read()
            tmp_file.write(content)
        
        try:
            # Process audio using speech_to_text module only
            # Note: speech_to_text is synchronous, so we run it in a thread
            transcribed_text = await asyncio.to_thread(ai_module.speech_to_text, tmp_path)
            
            if transcribed_text is None:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to transcribe audio. Please check audio quality and format."
                )
            
            logger.info(f"✅ Audio transcribed via speech_to_text: {transcribed_text[:100]}...")
            
            return {
                "status": "success",
                "transcribed_text": transcribed_text,
                "filename": audio_file.filename
            }
        finally:
            # Clean up temporary files (original and converted WAV if created)
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                # Also clean up converted WAV file if it was created
                wav_path = tmp_path.rsplit('.', 1)[0] + '.wav'
                if os.path.exists(wav_path) and wav_path != tmp_path:
                    os.unlink(wav_path)
            except Exception as e:
                logger.warning(f"⚠️ Failed to delete temp file(s): {e}")
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Audio processing error: {e}")
        raise HTTPException(status_code=500, detail=f"Audio processing error: {str(e)}")
