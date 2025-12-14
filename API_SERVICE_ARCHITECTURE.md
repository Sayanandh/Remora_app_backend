# ApiService Architecture & Integration Guide

This document explains the architecture, responsibilities, data flows, and recommended improvements for the Flutter `ApiService` located at `remora_patient/lib/services/api_service.dart`.

It is intended for frontend engineers who need to understand how the Flutter app integrates with the Remora FastAPI backend (auth, users, patients, locations, and realtime updates).

---

## Table of Contents
- Overview
- Responsibilities
- Configuration
- Endpoints used
- Authentication flow & token management
- Location flow (live updates)
- Error handling & robustness
- Socket.IO (realtime) integration
- Best practices and production hardening
- Example usage snippets (Flutter)
- Suggested improvements & roadmap

---

## Overview

`ApiService` is a static helper class providing HTTP wrappers for backend endpoints used by the patient-facing Flutter app. It centralizes:
- Authentication (register/login)
- Profile and user retrieval
- Caregiver search & linking
- Sending patient location pings
- Retrieving caregivers and other resources

By centralizing network logic, it simplifies maintenance and enables consistent headers, token usage, and JSON handling.

---

## Responsibilities

- Build correct URIs for backend endpoints (baseUrl + path).
- Add appropriate headers (`Content-Type`, `Authorization`).
- Serialize / deserialize JSON payloads.
- Persist JWT token locally using `SharedPreferences`.
- Provide synchronous method signatures that the UI can `await`.

The class is intentionally static (no instance), making usage simple but testability harder.

---

## Configuration

- `baseUrl` is defined as a static constant. In the current file it points to an ngrok host; for production this should be replaced with a config-managed value (flavors, env file, or CI replacement).

Example options:
- Use dart-define during build: `--dart-define=API_BASE_URL=https://api.remora.example`
- Use a runtime config provider (local JSON or remote config) if you need dynamic switching.

---

## Endpoints used (summary)

These endpoints are called by the `ApiService`:

- `POST /api/auth/register` — Register user (role: PATIENT)
- `POST /api/auth/login` — Authenticate and receive JWT
- `GET /api/users/me` — Get current user profile
- `GET /api/users/caregivers?query=` — Search caregivers
- `POST /api/patients/connect-caregiver` — Connect patient to caregiver
- `GET /api/patients/me/caregivers` — List connected caregivers
- `POST /api/patients/me/location` — Send patient location (creates/updates PatientLocation)

Note: `ApiService` assumes the backend routes are prefixed with `/api`.

---

## Authentication flow & token management

1. User authenticates via `login()`.
   - `POST /api/auth/login` returns a JSON `{ token, user }` structure.
   - `ApiService.login` saves the token to `SharedPreferences` via `saveToken()`.

2. For protected endpoints, `getToken()` is called to fetch the token and included as an `Authorization: Bearer <token>` header.

3. To logout, `clearToken()` removes the token from storage.

Security considerations:
- Stored token in `SharedPreferences` is persistent and readable by the app only; on rooted devices it can be compromised. For stronger protection consider platform secure storage (Keychain / Keystore) via packages like `flutter_secure_storage`.
- Tokens have expiry — the app must handle 401 responses by forcing re-login or triggering token refresh flow (the backend currently issues only short-lived JWTs with no refresh endpoint implemented in the provided backend code).

---

## Location flow (live updates)

The `sendLocation()` method posts pings to:

- `POST /api/patients/me/location` — expects 201 Created on success.

Payload shape used by the service:
```json
{
  "latitude": 12.345678,
  "longitude": -98.765432,
  "accuracy": 5.0,            // optional
  "battery": 84,              // optional
  "recordedAt": "2025-12-13T12:34:56Z" // optional
}
```

Server-side behavior (backend):
- Backend ensures a `PatientProfile` exists for the user
- It upserts `PatientLocation` so the latest location per patient is stored
- Backend emits a Socket.IO event `location:new` for recipients/rooms

How to achieve continuous live location:
- On the patient device, poll the device location provider (platform-specific) at a reasonable interval (for example, 15–60s).
- Call `ApiService.sendLocation()` each interval with the latest coordinates and battery/accuracy.
- Keep a watchdog to avoid sending pings when the app is backgrounded or battery critical.

Battery & privacy note:
- High-frequency GPS sampling drains battery quickly; tune interval based on use-case.
- Respect user privacy and obtain runtime permission for location tracking (foreground and background if needed).

---

## Error handling & robustness

Current `ApiService` behaviors to be aware of:
- The code often does `jsonDecode(response.body)` on non-200 responses. If backend returns non-JSON (HTML error page or empty body), `jsonDecode` will throw and crash.
- Token absence is handled by throwing `Exception('Not authenticated')` — caller must catch and route to login.

Recommended improvements:
- Wrap `jsonDecode` calls in try/catch and fallback to `response.body` or a generic error.
- Create a typed exception class (e.g., `ApiException`) with `statusCode`, `body`, `message` for better handling.
- Centralize HTTP request logic into a private `_request()` helper to avoid repeating token retrieval and header assembly.
- Add automatic 401 handling to clear token and optionally redirect to login.

Example safe decode helper:
```dart
Map<String, dynamic>? tryDecode(String body) {
  try { return jsonDecode(body) as Map<String, dynamic>?; }
  catch (_) { return null; }
}
```

---

## Socket.IO (realtime) integration

The backend emits events via Socket.IO (server-side `emit_location_new` and `emit_alert_new`) to a room named `recipient:{recipientId}`.

To receive live updates in Flutter, use `socket_io_client` (or `adhara_socket_io` / similar). The key steps:
1. Connect to the backend Socket.IO endpoint (same host as `baseUrl`, consider `wss://` for production).
2. Authenticate if needed (many Socket.IO setups accept token during handshake or a separate auth event).
3. Emit `joinRecipientRoom` with `recipientId` to subscribe.
4. Listen for `location:new` and `alert:new` events.

Example client behavior (Dart):
```dart
import 'package:socket_io_client/socket_io_client.dart' as IO;

IO.Socket socket = IO.io('https://your-host', <String, dynamic>{
  'transports': ['websocket'],
  'autoConnect': false,
  'extraHeaders': {'Authorization': 'Bearer $token'},
});

socket.connect();

socket.on('connect', (_) => print('connected'));

socket.emit('joinRecipientRoom', recipientId);

socket.on('location:new', (data) {
  // parse and update UI map
});

socket.on('alert:new', (data) {
  // show notification / alert card
});
```

Notes:
- Confirm the backend accepts token via `extraHeaders` on handshake; if not, join room after standard auth request.
- Use secure websockets in production; enable `wss://` and TLS.

---

## Best practices and production hardening

- Replace `baseUrl` with environment-configured value (`--dart-define` or runtime config).
- Use `flutter_secure_storage` to store JWT tokens securely.
- Add centralized request wrapper to:
  - add default headers
  - decode responses safely
  - retry transient network failures
  - handle 401 globally
- Implement token refresh on the backend (refresh tokens) or shorten JWT lifetime if security demands it and implement refresh flow.
- Implement exponential backoff for failed network calls.
- Avoid logging sensitive tokens or user data in production.
- Validate network reachability and degrade gracefully if offline (queue pings when offline and flush when online).

---

## Example usage snippets (concrete)

### Periodic location sender (Flutter)

```dart
import 'dart:async';

Timer? _locationTimer;

void startLocationSharing() {
  // send every 30 seconds while app is active
  _locationTimer = Timer.periodic(Duration(seconds: 30), (_) async {
    final loc = await _locationService.getLocation();
    try {
      await ApiService.sendLocation(
        latitude: loc.latitude,
        longitude: loc.longitude,
        accuracy: loc.accuracy,
        battery: await deviceBatteryLevel(),
        recordedAt: DateTime.now().toUtc(),
      );
    } catch (e) {
      // handle — maybe queue for retry
    }
  });
}

void stopLocationSharing() {
  _locationTimer?.cancel();
}
```

### Socket.IO connection example

```dart
import 'package:socket_io_client/socket_io_client.dart' as IO;

Future<IO.Socket> connectSocket(String token, String recipientId) async {
  final socket = IO.io(ApiService.baseUrl.replaceAll('http', 'https'), {
    'transports': ['websocket'],
    'extraHeaders': {'Authorization': 'Bearer $token'},
  });

  socket.connect();
  socket.on('connect', (_) {
    socket.emit('joinRecipientRoom', recipientId);
  });

  return socket;
}
```

Be careful with the `baseUrl` scheme — Socket.IO often uses a different path, confirm with backend.

---

## Suggested improvements & roadmap

1. Centralize HTTP logic in `_request()` with typed responses and unified error handling.
2. Use `flutter_secure_storage` for tokens.
3. Add request timeouts and retry policies.
4. Implement presence and connection status on the Socket.IO client.
5. Add offline queueing for location pings and sync on reconnect.
6. Add unit tests / integration tests around `ApiService` using dependency injection or by extracting an interface so you can mock HTTP.
7. Add environment-specific configuration management.

---

## File Location

Saved to: `remora_patient/API_SERVICE_ARCHITECTURE.md`

---

If you want, I can:
- convert this into a README-style page in the Flutter project,
- implement a `_request()` wrapper inside `ApiService` and refactor methods to use it, or
- add the Socket.IO client implementation into the Flutter project (create `realtime_service.dart`).

Which of these would you like next?