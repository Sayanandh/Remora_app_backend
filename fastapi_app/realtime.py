from typing import Any

import socketio

from .config import get_settings

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[get_settings().client_origin] if get_settings().client_origin != "*" else "*",
)


@sio.event
async def connect(sid: str, environ: dict, auth: Any):
    # Connection established; nothing special to do.
    return True


@sio.event
async def joinRecipientRoom(sid: str, recipientId: str):
    await sio.enter_room(sid, f"recipient:{recipientId}")


def emit_alert_new(recipient_id: str, payload: Any):
    sio.start_background_task(sio.emit, "alert:new", payload, room=f"recipient:{recipient_id}")


def emit_location_new(recipient_id: str, payload: Any):
    sio.start_background_task(sio.emit, "location:new", payload, room=f"recipient:{recipient_id}")


def emit_device_voice_toggle(recipient_id: str):
    """Emit device:voice_toggle to patient's room so the app can start/stop voice recording."""
    sio.start_background_task(sio.emit, "device:voice_toggle", {}, room=f"recipient:{recipient_id}")






