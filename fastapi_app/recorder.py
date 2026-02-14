import sounddevice as sd
import soundfile as sf
import time
from .state import stop_event

FS = 44100
FILE_NAME = "recorded_audio.wav"

def record_audio():
    with sf.SoundFile(FILE_NAME, mode="w", samplerate=FS, channels=1) as file:
        with sd.InputStream(
            samplerate=FS,
            channels=1,
            callback=lambda indata, frames, time_info, status: file.write(indata)
        ):
            while not stop_event.is_set():
                time.sleep(0.1)
