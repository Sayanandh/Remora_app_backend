## FastAPI Backend (Python)

This directory contains the FastAPI-based backend that talks to MongoDB using the same `DATABASE_URL` as your previous backend.

---

### How to run

- **Install dependencies**:

```bash
python -m pip install -r requirements.txt
```

- **Run the API + Socket.IO server**:

```bash
uvicorn fastapi_app.main:app_scope --reload --port 4000
```

The API will be served under:

- `GET /health` → `{ "status": "ok" }`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/users/me`
- Other routers: `/recipients`, `/alerts`, `/notifications`, `/locations`, `/activities`, `/patients`

The server also exposes a Socket.IO endpoint compatible with the existing frontend events:

- Client emits `joinRecipientRoom` with a `recipientId`
- Server emits `alert:new` and `location:new` to rooms named `recipient:{recipientId}`

---

### Environment

The FastAPI app uses the same env vars as the previous backend:

- `DATABASE_URL` – MongoDB connection string (same as Prisma)
- `JWT_SECRET` – secret for signing JWTs
- `CLIENT_ORIGIN` – frontend origin (for CORS); `*` by default
- `PORT` – port to run on (default `4000`, must match frontend expectations)

---

### Database & Collections (MongoDB schema)

All database access goes through `fastapi_app/db.py`. The helper `get_database()` connects to the database selected by `DATABASE_URL` (default logical name: `remora`) and returns an `AsyncIOMotorDatabase` instance.

Collections are created automatically by MongoDB when documents are inserted. This section documents the collections and the fields we expect to exist.

#### 1. `User` collection

- **Purpose**: Store all authenticated users (both caregivers and patients).
- **Created/used in**: `fastapi_app/auth.py`

**Fields**

- **_id**: `ObjectId` – primary key created by MongoDB.
- **email**: `string` – unique email address for login.
- **passwordHash**: `string` – bcrypt hash of the user’s password.
- **name**: `string` – display name.
- **role**: `string` – `"CAREGIVER"` or `"PATIENT"`.
- **createdAt**: `datetime` (UTC) – when the user was created.
- **updatedAt**: `datetime` (UTC) – last update timestamp.

**Notes**

- When serializing, `_id` is exposed as `id` via `serialize_mongo_document()` in `db.py`.
- The FastAPI `/api/auth/register` endpoint allows the client to send a `role` (`"CAREGIVER"` / `"PATIENT"`). If omitted, it defaults to `"CAREGIVER"` to keep existing behavior.

#### 2. `PatientLocation` collection

- **Purpose**: Store periodic GPS pings from **patient** users.
- **Created/used in**: `fastapi_app/routers_patients.py` (`ping_my_location` endpoint).

**Fields**

- **_id**: `ObjectId` – primary key created by MongoDB.
- **userId**: `string` – stringified `_id` of the corresponding `User` document (must be a `"PATIENT"` user).
- **latitude**: `number` (float) – current latitude from the device.
- **longitude**: `number` (float) – current longitude from the device.
- **accuracy**: `number` (float, optional) – GPS accuracy in meters if the client sends it.
- **battery**: `number` (int, optional) – battery level in percent if the client sends it.
- **recordedAt**: `datetime` (UTC) – when this location sample was recorded.

**How data is written**

- Endpoint: `POST /api/patients/me/location`
- Auth: requires a valid JWT for a user whose `role` is `"PATIENT"` (`get_current_patient` in `auth.py` guards this).
- Example request body:

```json
{
  "latitude": 12.9716,
  "longitude": 77.5946,
  "accuracy": 10.5,
  "battery": 87
}
```

If `recordedAt` is not sent by the client, the backend fills it with `datetime.now(timezone.utc)`.

On the Flutter side (`lib/screens/patient_dashboard_screen.dart`), a logged-in patient calls this endpoint every 30 seconds (using `Geolocator` to get the current GPS location).

#### 3. Patient–Caregiver relationship (future)

- **Planned purpose**: Link each patient user to one or more caregiver users using a code or ID.
- **Current implementation**: only a stub endpoint exists; no collection is persisted yet.

**Endpoint**

- `POST /api/patients/connect-caregiver`
- Request body:

```json
{
  "caregiverCode": "ABC123"
}
```

- Currently returns:

```json
{
  "status": "NOT_IMPLEMENTED",
  "message": "Connect-to-caregiver logic will be implemented later."
}
```

**Suggested future schema**

When you are ready to implement this, you will probably add a new collection, for example:

- **Collection name**: `PatientCaregiverLink`

Fields:

- **_id**: `ObjectId`
- **patientUserId**: `string` – `_id` from `User` where `role == "PATIENT"`.
- **caregiverUserId**: `string` – `_id` from `User` where `role == "CAREGIVER"`.
- **createdAt**: `datetime` (UTC)
- **status**: `string` – `"PENDING"`, `"ACTIVE"`, `"REJECTED"`, etc. (optional).

The `connect-caregiver` endpoint would then:

1. Look up a caregiver user by some `caregiverCode` (could be stored on the caregiver’s `User` record or in another collection).
2. Insert a new `PatientCaregiverLink` document with the `patientUserId` and `caregiverUserId`.
3. Optionally enforce uniqueness (one active caregiver per patient, etc.).

#### 4. Other existing collections

The backend also mirrors your earlier API and uses several other collections via the routers:

- `Recipients` – accessed from `routers_recipients.py`
- `Alerts` – accessed from `routers_alerts.py`
- `Locations` – accessed from `routers_locations.py` (for caregiver-side tracking/alerts)
- `Activities` – accessed from `routers_activities.py`
- `Notifications` – accessed from `routers_notifications.py`

Those schemas follow your existing Node/Prisma data model; this FastAPI backend reads/writes them using the same field names so that both backends are compatible with the same MongoDB.

If you want, we can further expand this document with full field-by-field schemas for each of those collections as well.
