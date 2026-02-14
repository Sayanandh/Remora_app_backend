# utils/ai_module.py
import sys
import subprocess
import asyncio
import re
import json
import logging
import requests
from pydub import AudioSegment
import speech_recognition as stt

# Try importing edge_tts and pyttsx3, handle if missing
try:
    import edge_tts as tts
except ImportError:
    tts = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

logger = logging.getLogger(__name__)

# ============================================================
# 🗣️ TEXT TO SPEECH (TTS)
# ============================================================
async def edge_tts_speak(text, output_file='output.mp3', timeout=15):
    if not tts:
        logger.error("edge_tts module not installed")
        return False
        
    comm = tts.Communicate(text, voice='en-US-AriaNeural')
    try:
        await asyncio.wait_for(comm.save(output_file), timeout=timeout)
        logger.info(f"✅ TTS saved as {output_file}")
        return True
    except asyncio.TimeoutError:
        logger.warning("⏳ Edge-TTS timed out.")
        return False
    except Exception as e:
        logger.error(f"❌ Edge-TTS failed: {e}")
        return False

def pyttsx3_speak(text):
    if not pyttsx3:
        logger.error("pyttsx3 module not installed")
        return
        
    try:
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        logger.info("🗣️ Fallback offline TTS spoken.")
    except Exception as e:
        logger.error(f"❌ pyttsx3 failed: {e}")

async def text_to_speech(text, output_file='output.mp3', timeout=15):
    """
    Main TTS function. Tries Edge-TTS first, falls back to pyttsx3.
    """
    success = await edge_tts_speak(text, output_file, timeout)
    if not success:
        # Run pyttsx3 in a thread to avoid blocking the event loop
        await asyncio.to_thread(pyttsx3_speak, text)

# ============================================================
# 🎧 SPEECH TO TEXT (STT)
# ============================================================
def speech_to_text(audio_path):
    try:
        rec = stt.Recognizer()
        
        # If input is mp3 convert to wav first
        if audio_path.endswith(".mp3"):
            try:
                sound = AudioSegment.from_mp3(audio_path)
                audio_wav = audio_path.replace(".mp3", ".wav")
                sound.export(audio_wav, format="wav")
                audio_path = audio_wav
            except Exception as e:
                logger.error(f"Failed to convert MP3 to WAV: {e}")
                return None

        with stt.AudioFile(audio_path) as source:
            audio_data = rec.record(source)

        text = rec.recognize_google(audio_data)
        logger.info(f"🎤 STT Recognized: {text}")
        return text
    except Exception as e:
        logger.error(f'❌ STT Error: {e}')
        return None

# ============================================================
# 🧩 JSON HELPER
# ============================================================
def extract_json(text):
    try:
        # try find first balanced JSON object with regex
        match = re.search(r'\{(?:[^{}]|(?R))*\}', text)
        if match:
            return json.loads(match.group())
        # fallback: search for a simple {...}
        match2 = re.search(r'\{[^{}]*\}', text)
        if match2:
            return json.loads(match2.group())
    except Exception as e:
        logger.warning(f"⚠️ Error extracting JSON: {e}")
    return {"intent": "error", "target": None}

# ============================================================
# 🧠 MISTRAL INTENT CLASSIFICATION
# ============================================================
def mistral_intent(command):
    prompt = f"""Classify this command for a blind navigation assistant:
Examples:
"find me a chair" -> {{"intent": "find_object", "target": "chair"}}
"navigate to kitchen" -> {{"intent": "navigate_place", "target": "kitchen"}}
"stop" -> {{"intent": "stop", "target": null}}
Command: "{command}"
Output:"""
    try:
        # Use localhost for now, assume Mistral is running there
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={'model': 'mistral', 'prompt': prompt, 'stream': False},
            timeout=30
        )
        resp_json = response.json()
        # try multiple possible keys
        llm_output = resp_json.get("response") or resp_json.get("output") or resp_json.get("text") or json.dumps(resp_json)
        logger.info(f"🧠 LLM output: {llm_output}")
        
        parsed = extract_json(llm_output)
        logger.info(f"✅ Parsed intent: {parsed}")
        return parsed
    except Exception as e:
        logger.error(f"❌ Mistral error: {e}")
        return {'intent': 'error', 'target': None}

# ============================================================
# 🧭 OBJECT NAVIGATION LOGIC
# ============================================================
def find_obj(obj_json):
    """
    Generates navigation instructions based on object data.
    """
    target = obj_json.get("object", "object")
    bbox = obj_json.get("bbox", [0.5, 0.5, 0.1, 0.1])
    distance = obj_json.get("distance", 100.0)  # assume cm by default from ESP
    
    # Convert cm -> meters for human phrasing / threshold
    try:
        distance_m = float(distance) / 100.0
    except:
        distance_m = 1.0

    x_center = 0.5
    try:
        if isinstance(bbox, list) and len(bbox) > 0:
            x_center = float(bbox[0])
    except:
        x_center = 0.5

    if x_center < 0.4:
        direction = "left"
    elif x_center > 0.6:
        direction = "right"
    else:
        direction = "ahead"

    if distance_m < 0.5:
        message = f"{target} is very close. Stop."
    else:
        message = f"{target} is {distance_m:.1f} meters away, move {direction}."

    logger.info(f"🧭 Navigation: {message}")
    return message
