# Remora Backend - Complete Detailed Documentation

## Table of Contents
1. [Overview](#overview)
2. [Project Structure](#project-structure)
3. [Core Configuration Files](#core-configuration-files)
4. [Database Layer](#database-layer)
5. [Authentication System](#authentication-system)
6. [Real-time Communication](#real-time-communication)
7. [API Routers](#api-routers)
8. [Main Application Entry Point](#main-application-entry-point)
9. [Data Flow & Architecture](#data-flow--architecture)

---

## Overview

The Remora Backend is a FastAPI-based REST API server designed for a caregiver-patient monitoring system. It provides:
- User authentication and authorization (JWT-based)
- Patient-caregiver relationship management
- Real-time location tracking
- SOS emergency alert system
- Activity and alert monitoring
- Real-time notifications via WebSocket (Socket.IO)

**Technology Stack:**
- **Framework**: FastAPI (Python)
- **Database**: MongoDB (via Motor async driver)
- **Authentication**: JWT (JSON Web Tokens) with bcrypt password hashing
- **Real-time**: Socket.IO (python-socketio)
- **Server**: Uvicorn (ASGI)

---

## Project Structure

```
Remora_app_backend/
├── fastapi_app/
│   ├── main.py              # Application entry point & middleware
│   ├── config.py            # Configuration management
│   ├── db.py                # Database connection & utilities
│   ├── auth.py              # Authentication & authorization
│   ├── realtime.py          # Socket.IO real-time events
│   ├── routers_sos.py       # SOS emergency endpoints
│   ├── routers_users.py     # User management endpoints
│   ├── routers_patients.py  # Patient-specific endpoints
│   ├── routers_locations.py # Location tracking endpoints
│   ├── routers_activities.py # Activity logging endpoints
│   ├── routers_alerts.py    # Alert management endpoints
│   ├── routers_notifications.py # Notification endpoints
│   └── routers_recipients.py # Care recipient endpoints
├── requirements.txt         # Python dependencies
└── env                      # Environment variables template
```

---

## Core Configuration Files

### 1. `config.py` - Configuration Management

**Purpose**: Centralized configuration management using Pydantic settings.

#### Classes & Functions:

**`Settings` (Pydantic BaseModel)**
- **Purpose**: Defines all application settings from environment variables
- **Fields**:
  - `app_name` (str): Application name, default: "Remora Caregiver Backend (FastAPI)"
  - `environment` (str): Environment mode (development/production), from `ENVIRONMENT` env var
  - `database_url` (str | None): MongoDB connection string (hardcoded in code, should use env var)
  - `jwt_secret` (str): Secret key for JWT token signing, from `JWT_SECRET` env var
  - `jwt_algorithm` (str): JWT algorithm, default: "HS256"
  - `jwt_exp_days` (int): JWT token expiration in days, default: 7
  - `client_origin` (str): CORS allowed origin, from `CLIENT_ORIGIN` env var
  - `port` (int): Server port, from `PORT` env var, default: 4000

**`get_settings() -> Settings`**
- **Purpose**: Returns cached Settings instance (singleton pattern using `@lru_cache`)
- **Returns**: Settings object with all configuration values
- **Note**: Uses `@lru_cache` decorator to ensure only one instance is created

---

### 2. `db.py` - Database Connection & Utilities

**Purpose**: MongoDB connection management and document serialization utilities.

#### Functions:

**`get_client() -> AsyncIOMotorClient`**
- **Purpose**: Creates and returns a singleton MongoDB client connection
- **Returns**: `AsyncIOMotorClient` instance
- **Features**:
  - Lazy initialization (created on first call)
  - Connection timeout: 30 seconds
  - Server selection timeout: 30 seconds
  - Retry writes enabled
  - Logs connection info (with masked password)
- **Error Handling**: Raises `ValueError` if `DATABASE_URL` is not set

**`_get_db_name_from_url(url: str) -> str | None`**
- **Purpose**: Extracts database name from MongoDB connection URL
- **Parameters**: `url` - MongoDB connection string
- **Returns**: Database name or None if not found
- **Example**: `mongodb+srv://.../Remora` → returns `"Remora"`

**`get_database() -> AsyncIOMotorDatabase`**
- **Purpose**: Returns the target MongoDB database instance
- **Returns**: `AsyncIOMotorDatabase` object
- **Logic**:
  - Extracts database name from `DATABASE_URL` (case-sensitive)
  - Falls back to "remora" if not specified in URL
  - Logs which database is being used

**`_convert_to_ist(dt: datetime) -> str`**
- **Purpose**: Converts UTC datetime to India Standard Time (IST, UTC+5:30) and returns ISO string
- **Parameters**: `dt` - datetime object (assumed UTC if no timezone)
- **Returns**: ISO format string in IST timezone
- **Error Handling**: Falls back to UTC if conversion fails

**`serialize_mongo_document(doc: Dict[str, Any] | None) -> Dict[str, Any] | None`**
- **Purpose**: Converts MongoDB document to API-friendly format
- **Parameters**: `doc` - Raw MongoDB document (dict) or None
- **Returns**: Serialized document or None
- **Transformations**:
  1. Converts `_id` (ObjectId) to `id` (string)
  2. Converts all datetime objects to IST ISO strings (recursively)
  3. Handles nested dictionaries and lists
- **Use Case**: Used before returning data in API responses

**`_serialize_datetime_in_dict(d: Dict[str, Any]) -> Dict[str, Any]`**
- **Purpose**: Helper function to recursively serialize datetime objects in dictionaries
- **Parameters**: `d` - Dictionary potentially containing datetime objects
- **Returns**: Dictionary with all datetimes converted to IST ISO strings
- **Recursion**: Handles nested dicts and lists

---

## Database Layer

### MongoDB Collections Used:

1. **`User`**: User accounts (patients and caregivers)
   - Fields: `_id`, `email`, `passwordHash`, `name`, `role` (CAREGIVER/PATIENT), `status`, `deviceTokens[]`, `createdAt`, `updatedAt`, `emergencyTriggeredAt`

2. **`PatientProfile`**: Patient-specific profile data
   - Fields: `_id`, `userId`, `createdAt`, `updatedAt`

3. **`PatientLocation`**: Patient location tracking
   - Fields: `_id`, `userId`, `latitude`, `longitude`, `accuracy`, `battery`, `recordedAt`, `updatedAt`, `createdAt`

4. **`PatientCaregiverLink`**: Links patients to caregivers
   - Fields: `_id`, `patientUserId`, `caregiverUserId`, `status` (ACTIVE), `createdAt`, `updatedAt`

5. **`Alert`**: Emergency and system alerts
   - Fields: `_id`, `recipientId`, `title`, `message`, `type`, `severity`, `isAcknowledged`, `createdAt`, `patientUserId`, `caregiverUserIds[]`, `latitude`, `longitude`

6. **`Notification`**: User notifications
   - Fields: `_id`, `userId`, `title`, `message`, `type`, `isRead`, `createdAt`, `relatedPatientId`, `relatedPatientName`, `latitude`, `longitude`

7. **`Location`**: Generic location records (legacy)
   - Fields: `_id`, `recipientId`, `latitude`, `longitude`, `accuracy`, `battery`, `recordedAt`

8. **`Activity`**: Activity logs
   - Fields: `_id`, `recipientId`, `kind`, `value`, `unit`, `metadata`, `recordedAt`

9. **`CareRecipient`**: Care recipient profiles (legacy)
   - Fields: `_id`, `name`, `age`, `relationship`, `avatarUrl`, `createdAt`, `updatedAt`

10. **`CaregiverOnRecipient`**: Caregiver-recipient links (legacy)
    - Fields: `_id`, `caregiverId`, `recipientId`, `assignedAt`

---

## Authentication System

### File: `auth.py`

**Purpose**: Handles user authentication, registration, login, and role-based authorization.

#### Models:

**`UserInDB` (BaseModel)**
- Represents a user stored in the database
- Fields: `id`, `email`, `passwordHash`, `name`, `role`

**`RegisterRequest` (BaseModel)**
- Request body for user registration
- Fields: `email`, `password`, `name`, `role` (optional, defaults to CAREGIVER)

**`RegisterResponse` (BaseModel)**
- Response after successful registration
- Fields: `id`, `email`, `name`, `role`

**`LoginRequest` (BaseModel)**
- Request body for login
- Fields: `email`, `password`

**`LoginUser` (BaseModel)**
- User info returned in login response
- Fields: `id`, `email`, `name`, `role`

**`LoginResponse` (BaseModel)**
- Response after successful login
- Fields: `token` (JWT), `user` (LoginUser)

#### Helper Functions:

**`_hash_password(password: str) -> str`**
- **Purpose**: Hashes a plain text password using bcrypt
- **Parameters**: `password` - Plain text password
- **Returns**: Bcrypt hash string
- **Security**: Uses 10 rounds of bcrypt hashing

**`_verify_password(password: str, hashed: str) -> bool`**
- **Purpose**: Verifies a password against a bcrypt hash
- **Parameters**: 
  - `password` - Plain text password to verify
  - `hashed` - Bcrypt hash to compare against
- **Returns**: True if password matches, False otherwise
- **Error Handling**: Returns False on any exception

**`_create_access_token(data: Dict[str, Any]) -> str`**
- **Purpose**: Creates a JWT access token
- **Parameters**: `data` - Dictionary containing user info (id, role, email)
- **Returns**: JWT token string
- **Expiration**: Token expires in `jwt_exp_days` (default 7 days)
- **Algorithm**: HS256

**`_get_user_by_email(email: str) -> Optional[UserInDB]`**
- **Purpose**: Retrieves a user from database by email
- **Parameters**: `email` - User's email address
- **Returns**: `UserInDB` object or None if not found
- **Logging**: Logs search attempts and results
- **Legacy Support**: Defaults missing role to "CAREGIVER"

#### Dependency Functions (FastAPI Dependencies):

**`get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> Dict[str, Any]`**
- **Purpose**: Validates JWT token and returns current authenticated user
- **Parameters**: `token` - JWT token from Authorization header (via OAuth2PasswordBearer)
- **Returns**: User dictionary from database
- **Errors**: 
  - 401 if token is invalid or expired
  - 401 if user not found in database
- **Usage**: Used as dependency in protected endpoints

**`get_current_patient(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]`**
- **Purpose**: Ensures authenticated user is a PATIENT
- **Parameters**: `current_user` - From `get_current_user` dependency
- **Returns**: User dictionary if role is PATIENT
- **Errors**: 403 if user is not a PATIENT
- **Usage**: Used in patient-only endpoints

**`get_current_caregiver(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]`**
- **Purpose**: Ensures authenticated user is a CAREGIVER
- **Parameters**: `current_user` - From `get_current_user` dependency
- **Returns**: User dictionary if role is CAREGIVER
- **Errors**: 403 if user is not a CAREGIVER
- **Usage**: Used in caregiver-only endpoints

#### Endpoints:

**`POST /auth/register`**
- **Purpose**: Register a new user account
- **Request Body**: `RegisterRequest`
- **Response**: `RegisterResponse` (201 Created)
- **Logic**:
  1. Checks if email already exists
  2. Hashes password
  3. Creates user document in `User` collection
  4. Returns user info (without password)
- **Errors**: 
  - 409 if email already exists
  - 503 on database errors
  - 500 on unexpected errors

**`POST /auth/login`**
- **Purpose**: Authenticate user and return JWT token
- **Request Body**: `LoginRequest`
- **Response**: `LoginResponse` (200 OK)
- **Logic**:
  1. Finds user by email
  2. Verifies password
  3. Creates JWT token
  4. Returns token and user info
- **Errors**: 401 if credentials are invalid

---

## Real-time Communication

### File: `realtime.py`

**Purpose**: Socket.IO server for real-time WebSocket communication.

#### Components:

**`sio: socketio.AsyncServer`**
- **Purpose**: Socket.IO async server instance
- **Mode**: ASGI (async)
- **CORS**: Configured from `CLIENT_ORIGIN` setting

#### Event Handlers:

**`@sio.event async def connect(sid: str, environ: dict, auth: Any)`**
- **Purpose**: Handles new WebSocket connections
- **Parameters**: 
  - `sid` - Session ID
  - `environ` - WSGI environment
  - `auth` - Authentication data
- **Returns**: True to accept connection

**`@sio.event async def joinRecipientRoom(sid: str, recipientId: str)`**
- **Purpose**: Joins a client to a recipient-specific room
- **Parameters**: 
  - `sid` - Session ID
  - `recipientId` - Recipient/Patient ID
- **Room Format**: `"recipient:{recipientId}"`
- **Use Case**: Caregivers join patient rooms to receive real-time updates

#### Emit Functions:

**`emit_alert_new(recipient_id: str, payload: Any)`**
- **Purpose**: Emits a new alert event to all clients in a recipient room
- **Parameters**: 
  - `recipient_id` - Patient/Recipient ID
  - `payload` - Alert data
- **Event Name**: `"alert:new"`
- **Room**: `"recipient:{recipient_id}"`
- **Execution**: Runs in background task (non-blocking)

**`emit_location_new(recipient_id: str, payload: Any)`**
- **Purpose**: Emits a new location update to all clients in a recipient room
- **Parameters**: 
  - `recipient_id` - Patient/Recipient ID
  - `payload` - Location data
- **Event Name**: `"location:new"`
- **Room**: `"recipient:{recipient_id}"`
- **Execution**: Runs in background task (non-blocking)

---

## API Routers

### 1. `routers_sos.py` - SOS Emergency System

**Purpose**: Handles emergency SOS alerts from devices (ESP8266) and patients.

#### Models:

**`SOSRequest` (BaseModel)**
- Request body for SOS endpoint
- Fields: `type` (default: "sos"), `device`, `timestamp` (optional), `userId` (optional), `deviceToken` (optional)

**`DeviceRegisterRequest` (BaseModel)**
- Request body for device registration
- Fields: `deviceName` (default: "ESP8266"), `deviceType` (default: "esp8266")`

#### Endpoints:

**`POST /sos/register-device`**
- **Purpose**: Register a device (ESP8266) for the authenticated user
- **Authentication**: Required (JWT)
- **Request Body**: `DeviceRegisterRequest`
- **Response**: Device token and registration info
- **Logic**:
  1. Generates secure device token (32 bytes, URL-safe)
  2. Stores token in user's `deviceTokens` array
  3. Returns token for ESP8266 to store
- **Use Case**: ESP8266 devices need a token to send SOS requests without user login

**`GET /sos/health`**
- **Purpose**: Health check for SOS service
- **Response**: Status message
- **No Authentication**: Public endpoint

**`POST /sos`**
- **Purpose**: Handle SOS emergency request from device or patient
- **Authentication**: Optional (can use deviceToken instead)
- **Request Body**: `SOSRequest`
- **Query Params**: `userId` (optional), `deviceToken` (optional)
- **Response**: Success confirmation with timestamp
- **Logic**:
  1. Identifies user via `deviceToken` (priority) or `userId`
  2. Updates user status to "emergency"
  3. Sets `emergencyTriggeredAt` timestamp
  4. Finds all connected caregivers via `PatientCaregiverLink`
  5. Creates notifications for each caregiver
  6. Creates alert document
  7. Emits real-time alert via Socket.IO
  8. Includes patient's latest location if available
- **Errors**: 
  - 401 if deviceToken is invalid
  - 404 if userId not found
  - 400 if neither deviceToken nor userId provided

---

### 2. `routers_users.py` - User Management

**Purpose**: User profile and caregiver search endpoints.

#### Endpoints:

**`GET /users/me`**
- **Purpose**: Get current authenticated user's profile
- **Authentication**: Required (JWT)
- **Response**: User info (id, email, name, role)
- **Errors**: 404 if user not found

**`GET /users/caregivers`**
- **Purpose**: Search for caregivers by name or email
- **Authentication**: Required (JWT)
- **Query Params**: `query` (optional) - Search term
- **Response**: List of caregivers matching query
- **Logic**:
  - If query contains "@", searches by email (exact match prioritized)
  - Otherwise searches by name or email (case-insensitive regex)
  - Returns up to 50 results
  - Exact email matches appear first
- **Use Case**: Patients search for caregivers to connect with

**`GET /users/me/patients`**
- **Purpose**: Get all patients connected to current caregiver
- **Authentication**: Required (JWT, CAREGIVER role)
- **Response**: List of patients with latest location
- **Logic**:
  1. Finds all `PatientCaregiverLink` documents for current caregiver
  2. Retrieves patient user info
  3. Includes latest location from `PatientLocation` collection
- **Use Case**: Caregiver dashboard showing all their patients

---

### 3. `routers_patients.py` - Patient-Specific Operations

**Purpose**: Patient location tracking, caregiver connections, and SOS alerts.

#### Models:

**`PatientLocationPing` (BaseModel)**
- Request body for location updates
- Fields: `latitude`, `longitude`, `accuracy` (optional), `battery` (optional), `recordedAt` (optional)

**`ConnectCaregiverRequest` (BaseModel)**
- Request body for connecting to a caregiver
- Fields: `caregiverCode` - Email or user ID

#### Helper Functions:

**`_ensure_patient_profile(user_id: str) -> Dict[str, Any]`**
- **Purpose**: Ensures a `PatientProfile` document exists for a user
- **Parameters**: `user_id` - Patient user ID
- **Returns**: PatientProfile document (created or existing)
- **Logic**: Creates profile if missing, updates `updatedAt` if exists

#### Endpoints:

**`POST /patients/me/location`**
- **Purpose**: Patient sends current location (mobile app)
- **Authentication**: Required (JWT, PATIENT role)
- **Request Body**: `PatientLocationPing`
- **Response**: Saved location document
- **Logic**:
  1. Ensures `PatientProfile` exists
  2. Upserts location in `PatientLocation` collection (one per patient)
  3. Returns latest location
- **Use Case**: Mobile app sends location every ~30 seconds

**`POST /patients/connect-caregiver`**
- **Purpose**: Connect a patient to a caregiver
- **Authentication**: Required (JWT, PATIENT role)
- **Request Body**: `ConnectCaregiverRequest`
- **Response**: Connection status and caregiver info
- **Logic**:
  1. Searches for caregiver by email (case-insensitive) or user ID
  2. Prevents self-connection
  3. Checks if link already exists
  4. Creates `PatientCaregiverLink` document if new
- **Errors**: 
  - 404 if caregiver not found
  - 400 if trying to connect to self
- **Response Codes**: 
  - "CONNECTED" - New connection created
  - "ALREADY_CONNECTED" - Link already exists

**`GET /patients/me/caregivers`**
- **Purpose**: Get all caregivers connected to current patient
- **Authentication**: Required (JWT, PATIENT role)
- **Response**: List of caregivers with connection timestamp
- **Logic**: Finds all active `PatientCaregiverLink` documents for patient

**`POST /patients/sos`**
- **Purpose**: Patient triggers SOS alert via mobile app
- **Authentication**: Required (JWT, PATIENT role)
- **Response**: Alert creation confirmation
- **Logic**:
  1. Finds connected caregivers
  2. Gets patient's latest location
  3. Creates alert in `Alert` collection
  4. Returns alert ID and caregiver count
- **Note**: Does not emit Socket.IO event (unlike device SOS endpoint)

**`GET /patients/caregiver/my-patients`**
- **Purpose**: Get all patients for a caregiver (alternative endpoint)
- **Authentication**: Required (JWT, CAREGIVER role)
- **Response**: List of patients with latest location
- **Logic**: Similar to `/users/me/patients` but different route

---

### 4. `routers_locations.py` - Location Tracking (Legacy)

**Purpose**: Generic location tracking endpoints (legacy system).

#### Models:

**`LocationCreate` (BaseModel)**
- Request body for creating location
- Fields: `recipientId`, `latitude`, `longitude`, `accuracy` (optional), `battery` (optional), `recordedAt` (optional)

#### Endpoints:

**`GET /locations/`**
- **Purpose**: List location records for a recipient
- **Authentication**: Required (JWT)
- **Query Params**: `recipientId` (required), `limit` (default: 50)
- **Response**: List of location documents
- **Collection**: `Location` (legacy, separate from `PatientLocation`)

**`POST /locations/`**
- **Purpose**: Create a new location record
- **Authentication**: Required (JWT)
- **Request Body**: `LocationCreate`
- **Response**: Created location document
- **Real-time**: Emits `location:new` event via Socket.IO

---

### 5. `routers_activities.py` - Activity Logging

**Purpose**: Log and retrieve activity data.

#### Models:

**`ActivityCreate` (BaseModel)**
- Request body for creating activity
- Fields: `recipientId`, `kind`, `value` (optional), `unit` (optional), `metadata` (optional), `recordedAt` (optional)

#### Endpoints:

**`GET /activities/`**
- **Purpose**: List activity records
- **Authentication**: Required (JWT)
- **Query Params**: 
  - `recipientId` (optional)
  - `kind` (optional) - Activity type filter
  - `from` (optional) - Start date (ISO format)
  - `to` (optional) - End date (ISO format)
- **Response**: List of activity documents (up to 200)
- **Sorting**: By `recordedAt` descending (newest first)

**`POST /activities/`**
- **Purpose**: Create a new activity record
- **Authentication**: Required (JWT)
- **Request Body**: `ActivityCreate`
- **Response**: Created activity document
- **Collection**: `Activity`

---

### 6. `routers_alerts.py` - Alert Management

**Purpose**: Create and manage alerts.

#### Models:

**`AlertCreate` (BaseModel)**
- Request body for creating alert
- Fields: `recipientId`, `title`, `message`, `type`, `severity` (optional, default: "INFO")

#### Endpoints:

**`GET /alerts/`**
- **Purpose**: List alerts for a recipient
- **Authentication**: Required (JWT)
- **Query Params**: `recipientId` (optional)
- **Response**: List of alert documents
- **Sorting**: By `createdAt` descending

**`POST /alerts/`**
- **Purpose**: Create a new alert
- **Authentication**: Required (JWT)
- **Request Body**: `AlertCreate`
- **Response**: Created alert document
- **Real-time**: Emits `alert:new` event via Socket.IO
- **Default**: `isAcknowledged` = False, `severity` = "INFO"

**`POST /alerts/{alert_id}/ack`**
- **Purpose**: Acknowledge an alert
- **Authentication**: Required (JWT)
- **Path Params**: `alert_id` - Alert document ID
- **Response**: Updated alert document
- **Logic**: Sets `isAcknowledged` to True
- **Errors**: 404 if alert not found

---

### 7. `routers_notifications.py` - User Notifications

**Purpose**: Manage user-specific notifications.

#### Models:

**`NotificationCreate` (BaseModel)**
- Request body for creating notification
- Fields: `title`, `message`, `type`

#### Endpoints:

**`GET /notifications/`**
- **Purpose**: Get all notifications for current user
- **Authentication**: Required (JWT)
- **Response**: List of notification documents
- **Sorting**: By `createdAt` descending
- **Collection**: `Notification`

**`POST /notifications/`**
- **Purpose**: Create a notification for current user
- **Authentication**: Required (JWT)
- **Request Body**: `NotificationCreate`
- **Response**: Created notification document
- **Default**: `isRead` = False

**`POST /notifications/{notification_id}/read`**
- **Purpose**: Mark notification as read
- **Authentication**: Required (JWT)
- **Path Params**: `notification_id` - Notification document ID
- **Response**: Updated notification document
- **Logic**: Sets `isRead` to True
- **Errors**: 404 if notification not found

---

### 8. `routers_recipients.py` - Care Recipients (Legacy)

**Purpose**: Manage care recipients (legacy system, separate from patient-caregiver model).

#### Models:

**`RecipientCreate` (BaseModel)**
- Request body for creating recipient
- Fields: `name`, `age` (optional), `relationship` (optional), `avatarUrl` (optional)

**`RecipientUpdate` (BaseModel)**
- Request body for updating recipient
- Fields: All optional (name, age, relationship, avatarUrl)

#### Endpoints:

**`GET /recipients/`**
- **Purpose**: List all recipients for current caregiver
- **Authentication**: Required (JWT)
- **Response**: List of recipient documents
- **Logic**: Finds recipients via `CaregiverOnRecipient` links

**`POST /recipients/`**
- **Purpose**: Create a new care recipient
- **Authentication**: Required (JWT)
- **Request Body**: `RecipientCreate`
- **Response**: Created recipient document
- **Logic**: 
  1. Creates `CareRecipient` document
  2. Creates `CaregiverOnRecipient` link

**`GET /recipients/{recipient_id}`**
- **Purpose**: Get a specific recipient
- **Path Params**: `recipient_id` - Recipient document ID
- **Response**: Recipient document
- **Errors**: 404 if not found

**`PUT /recipients/{recipient_id}`**
- **Purpose**: Update a recipient
- **Path Params**: `recipient_id` - Recipient document ID
- **Request Body**: `RecipientUpdate`
- **Response**: Updated recipient document
- **Logic**: Updates only provided fields, sets `updatedAt`
- **Errors**: 404 if not found

**`DELETE /recipients/{recipient_id}`**
- **Purpose**: Delete a recipient
- **Path Params**: `recipient_id` - Recipient document ID
- **Response**: 204 No Content
- **Logic**: Deletes recipient and all caregiver links

---

## Main Application Entry Point

### File: `main.py`

**Purpose**: FastAPI application setup, middleware configuration, and router registration.

#### Components:

**Logging Configuration**
- **Level**: INFO
- **Format**: Timestamp, logger name, level, message
- **Output**: Console

**Environment Setup**
- Loads `.env` file via `python-dotenv`
- Validates `DATABASE_URL` on startup (warns if missing)

**`RequestLoggingMiddleware` (BaseHTTPMiddleware)**
- **Purpose**: Logs all HTTP requests and responses
- **Logs**:
  - Incoming request: method, path, client IP, query params
  - Response: status code, processing time
- **Placement**: Outermost middleware (first to execute)

**FastAPI Application Setup**

**Main App (`app`)**
- **Title**: From settings
- **Middleware Stack** (order matters):
  1. `RequestLoggingMiddleware` - Request/response logging
  2. `CORSMiddleware` - Cross-origin resource sharing
  3. `TrustedHostMiddleware` - Host validation (allows all)
- **CORS Configuration**:
  - Origins: From `CLIENT_ORIGIN` setting (or "*" for all)
  - Credentials: Allowed
  - Methods: GET, POST, PUT, DELETE, OPTIONS
  - Headers: All allowed

**API Sub-Application (`api`)**
- **Root Path**: `/api`
- **Purpose**: Organized API endpoints under `/api` prefix
- **Routers Included**:
  - `auth_router` → `/api/auth/*`
  - `users_router` → `/api/users/*`
  - `recipients_router` → `/api/recipients/*`
  - `sos_router` → `/api/sos/*`
  - `alerts_router` → `/api/alerts/*`
  - `notifications_router` → `/api/notifications/*`
  - `locations_router` → `/api/locations/*`
  - `activities_router` → `/api/activities/*`
  - `patients_router` → `/api/patients/*`

**Backward Compatibility**
- Main app also includes some routers directly (without `/api` prefix):
  - `auth_router` → `/auth/*`
  - `users_router` → `/users/*`
  - `patients_router` → `/patients/*`
- **Reason**: Supports old clients using non-prefixed paths

**Socket.IO Integration**
- **`socket_app`**: ASGI app combining Socket.IO server and FastAPI app
- **Order**: Socket.IO handles WebSocket, FastAPI handles HTTP

**Entry Points**

**`get_app() -> callable`**
- **Purpose**: Returns ASGI app for uvicorn
- **Usage**: `uvicorn fastapi_app.main:get_app`

**`async def app_scope(scope: Scope, receive, send)`**
- **Purpose**: ASGI entry point
- **Usage**: `uvicorn fastapi_app.main:app_scope`

**Health Check Endpoint**

**`GET /health`**
- **Purpose**: Health check endpoint
- **Response**: `{"status": "ok"}`
- **No Authentication**: Public endpoint

---

## Data Flow & Architecture

### Authentication Flow

1. **Registration**:
   - Client → `POST /auth/register` → Server validates email uniqueness → Hashes password → Creates user → Returns user info

2. **Login**:
   - Client → `POST /auth/login` → Server verifies credentials → Creates JWT → Returns token + user info
   - Client stores JWT token

3. **Authenticated Requests**:
   - Client includes JWT in `Authorization: Bearer <token>` header
   - `get_current_user` dependency validates token → Returns user from database
   - Endpoint uses user info

### Patient-Caregiver Connection Flow

1. **Patient Connects to Caregiver**:
   - Patient → `POST /patients/connect-caregiver` (with caregiver email/ID)
   - Server finds caregiver → Creates `PatientCaregiverLink` document
   - Returns connection confirmation

2. **Caregiver Views Patients**:
   - Caregiver → `GET /users/me/patients`
   - Server finds all `PatientCaregiverLink` documents → Returns patient list with locations

### Location Tracking Flow

1. **Patient Sends Location**:
   - Mobile app → `POST /patients/me/location` (every ~30 seconds)
   - Server upserts location in `PatientLocation` collection
   - Returns saved location

2. **Caregiver Views Location**:
   - Caregiver → `GET /users/me/patients`
   - Server includes latest location from `PatientLocation` for each patient

### SOS Emergency Flow

1. **Device Registration** (ESP8266):
   - User → `POST /sos/register-device` (authenticated)
   - Server generates device token → Stores in user's `deviceTokens` array
   - Returns token for ESP8266 to store

2. **SOS Trigger** (from ESP8266):
   - ESP8266 → `POST /sos` (with `deviceToken`)
   - Server identifies user from token → Updates user status to "emergency"
   - Finds connected caregivers → Creates notifications and alerts
   - Emits real-time alert via Socket.IO
   - Returns success confirmation

3. **SOS Trigger** (from Mobile App):
   - Patient → `POST /patients/sos` (authenticated)
   - Server creates alert → Notifies caregivers
   - Returns alert confirmation

### Real-time Communication Flow

1. **Client Connection**:
   - Client connects to Socket.IO server
   - Client calls `joinRecipientRoom` with patient ID
   - Server adds client to room `"recipient:{patientId}"`

2. **Event Emission**:
   - Server calls `emit_alert_new(patientId, alertData)`
   - Socket.IO emits `"alert:new"` event to all clients in room
   - Caregivers receive real-time updates

### Error Handling

- **HTTP Exceptions**: FastAPI automatically converts to JSON responses
- **Database Errors**: Caught and returned as 503 Service Unavailable
- **Validation Errors**: Pydantic automatically validates request bodies
- **Authentication Errors**: 401 Unauthorized for invalid tokens
- **Authorization Errors**: 403 Forbidden for role mismatches

### Timezone Handling

- **Storage**: All datetimes stored in UTC
- **API Responses**: Converted to IST (UTC+5:30) before returning
- **Conversion**: Handled in `serialize_mongo_document()` function

---

## Dependencies

### `requirements.txt`

- **fastapi==0.115.5**: Web framework
- **uvicorn[standard]==0.32.1**: ASGI server
- **python-dotenv==1.0.1**: Environment variable management
- **motor==3.6.0**: Async MongoDB driver
- **PyJWT==2.10.0**: JWT token handling
- **bcrypt==4.2.0**: Password hashing
- **python-multipart==0.0.17**: Form data parsing
- **python-socketio[asgi]==5.11.4**: Socket.IO server

---

## Environment Variables

### `env` file template:

- **DATABASE_URL**: MongoDB connection string
- **JWT_SECRET**: Secret key for JWT signing
- **CLIENT_ORIGIN**: CORS allowed origin (or "*" for all)
- **PORT**: Server port (default: 4000)
- **ENVIRONMENT**: Environment mode (development/production)

---

## Summary

The Remora Backend is a comprehensive FastAPI application providing:

1. **User Management**: Registration, login, role-based access (CAREGIVER/PATIENT)
2. **Relationship Management**: Patient-caregiver connections via `PatientCaregiverLink`
3. **Location Tracking**: Real-time patient location updates
4. **Emergency System**: SOS alerts from devices (ESP8266) and mobile apps
5. **Real-time Updates**: WebSocket notifications via Socket.IO
6. **Activity Logging**: Activity tracking and history
7. **Alert System**: Alert creation, acknowledgment, and real-time distribution
8. **Notifications**: User-specific notification management

The architecture follows REST principles with JWT authentication, MongoDB for data persistence, and Socket.IO for real-time communication. All datetime values are stored in UTC and converted to IST for API responses.

