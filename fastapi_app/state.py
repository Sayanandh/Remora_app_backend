import threading

recording = False
recording_thread = None
stop_event = threading.Event()
