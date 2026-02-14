# ngrok HTTP-Only Setup for ESP8266

## Problem
ESP8266 cannot handle HTTPS redirects from ngrok. When ngrok forces HTTPS, ESP8266 gets HTTP code -1 (connection failure).

## Solution: Use ngrok HTTP-only mode

### Step 1: Start ngrok in HTTP-only mode

```bash
ngrok http 4000 --scheme=http
```

**Important:** Use `--scheme=http` flag to disable HTTPS redirect.

### Step 2: Copy the HTTP URL

ngrok will show:
```
Forwarding   http://xxxx-xxxx-xxxx.ngrok-free.app -> http://localhost:4000
```

Copy the **HTTP URL** (starts with `http://`, not `https://`)

### Step 3: Update ESP8266 code

Replace in `ESP8266_SOS_Example.ino`:

```cpp
// OLD (HTTPS - doesn't work with ESP8266)
const char* SOS_URL = "https://heptagonal-darron-maniform.ngrok-free.dev/api/sos";
const char* VOICE_TOGGLE_URL = "https://heptagonal-darron-maniform.ngrok-free.dev/api/sos/voice-toggle";

// NEW (HTTP - works with ESP8266)
const char* SOS_URL = "http://xxxx-xxxx-xxxx.ngrok-free.app/api/sos";
const char* VOICE_TOGGLE_URL = "http://xxxx-xxxx-xxxx.ngrok-free.app/api/sos/voice-toggle";
```

### Step 4: Verify the exact API path

Your FastAPI route is:
- Router prefix: `/sos`
- Route: `/voice-toggle`
- API prefix: `/api`
- **Full path: `/api/sos/voice-toggle`** ✅

The ESP8266 code already uses the correct path.

## Test the setup

### From terminal (verify backend works):
```bash
curl -X POST http://xxxx-xxxx-xxxx.ngrok-free.app/api/sos/voice-toggle \
  -H "Content-Type: application/json" \
  -d '{"device":"esp8266","deviceToken":"YOUR_TOKEN"}'
```

Expected: `200 OK` with `{"success": true, ...}`

### From ESP8266:
1. Upload updated code
2. Press voice toggle button (D6)
3. Check Serial Monitor - should see:
   ```
   ➡ POST http://xxxx-xxxx-xxxx.ngrok-free.app/api/sos/voice-toggle
   ⬅ HTTP Code: 200
   ✅ Request successful!
   ```

## Alternative: Direct HTTP backend (no ngrok)

If you're on the same network:
```cpp
const char* VOICE_TOGGLE_URL = "http://192.168.1.100:4000/api/sos/voice-toggle";
```
(Replace `192.168.1.100` with your backend server's local IP)

## Production recommendation

For production SOS systems:
- ✅ Use ESP32 (handles HTTPS/TLS properly)
- ✅ Use static backend URL (not ngrok)
- ✅ Consider MQTT for IoT communication

ESP8266 + HTTPS is not reliable for production systems.

