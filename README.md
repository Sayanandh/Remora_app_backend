# Remora Patient App - Backend Architecture Documentation

## Table of Contents
1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Technology Stack](#technology-stack)
4. [Project Structure](#project-structure)
5. [Core Components](#core-components)
6. [Database Schema](#database-schema)
7. [API Endpoints](#api-endpoints)
8. [Authentication & Security](#authentication--security)
9. [Real-time Communication](#real-time-communication)
10. [File Descriptions](#file-descriptions)

---

## Overview

The Remora Patient App backend is a FastAPI-based REST API server designed to manage patient care, location tracking, alerts, and real-time notifications. It facilitates communication between patients and their caregivers through a microservice architecture with WebSocket support for real-time updates.

### Key Features
- **User Authentication**: JWT-based authentication with role-based access control (RBAC)
- **Patient-Caregiver Linking**: Secure connection between patients and their caregivers
- **Location Tracking**: Real-time GPS location sharing from patient devices
- **Alert System**: Create and acknowledge critical alerts with severity levels
- **Activity Monitoring**: Track patient activities and health metrics
- **Real-time Notifications**: WebSocket-based real-time updates via Socket.IO
- **Recipient Management**: Caregivers can manage multiple care recipients

---

## System Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI Application Server                  │
│                    (main.py - Port 4000)                     │
└─────────────────────────────────────────────────────────────┘
          │                                           │
          ▼                                           ▼
┌──────────────────────┐               ┌──────────────────────┐
│   REST API Routes    │               │   Socket.IO Server   │
│   (/api prefix)      │               │  (Real-time Events)  │
│                      │               │                      │
│ • Auth Routes        │               │ • joinRecipientRoom  │
│ • Users Routes       │               │ • alert:new          │
│ • Patients Routes    │               │ • location:new       │
│ • Alerts Routes      │               │ • Custom Events      │
│ • Locations Routes   │               │                      │
│ • Activities Routes  │               │                      │
│ • Recipients Routes  │               │                      │
│ • Notifications      │               │                      │
└──────────────────────┘               └──────────────────────┘
          │                                           │
          └──────────────────┬──────────────────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │   MongoDB Database   │
                  │  (Atlas Cloud)       │
                  │                      │
                  │ Collections:         │
                  │ • User               │
                  │ • PatientProfile     │
                  │ • PatientLocation    │
                  │ • PatientCaregiverLink
                  │ • Alert              │
                  │ • Location           │
                  │ • Activity           │
                  │ • CareRecipient      │
                  │ • CaregiverOnRecipient
                  │ • Notification       │
                  └──────────────────────┘
```

### Architecture Layers

1. **Presentation Layer**: FastAPI with CORS middleware
2. **Authentication Layer**: JWT token validation, role-based access control
3. **Business Logic Layer**: Router handlers with Pydantic models
4. **Data Access Layer**: Motor (Async MongoDB driver)
5. **Database Layer**: MongoDB Atlas

---

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **Framework** | FastAPI | Latest |
| **Web Server** | Uvicorn | ASGI |
| **Database** | MongoDB Atlas | Cloud |
| **Async Driver** | Motor | AsyncIO |
| **Authentication** | JWT + OAuth2 | HS256 |
| **Password Hashing** | bcrypt | rounds=10 |
| **Real-time** | Socket.IO | AsyncServer |
| **Environment** | Python | 3.8+ |
| **Config Management** | Pydantic | BaseModel |
| **CORS** | FastAPI Middleware | CORSMiddleware |

### Dependencies
```
fastapi          - Web framework
uvicorn          - ASGI server
motor            - Async MongoDB driver
pydantic         - Data validation
pyjwt            - JWT token handling
bcrypt           - Password hashing
python-socketio  - Real-time communication
python-dotenv    - Environment variables
email-validator  - Email validation
```

---

## Project Structure

```
fastapi_app/
├── main.py                      # Application entry point, server setup
├── config.py                    # Configuration and settings
├── db.py                        # Database connection and utilities
├── auth.py                      # Authentication logic and JWT
├── realtime.py                  # Socket.IO server setup
├── routers_users.py             # User endpoints
├── routers_patients.py          # Patient-specific endpoints
├── routers_alerts.py            # Alert management endpoints
├── routers_locations.py         # Location tracking endpoints
├── routers_activities.py        # Activity tracking endpoints
├── routers_recipients.py        # Care recipient management endpoints
├── routers_notifications.py     # Notification endpoints
├── __pycache__/                 # Python cache
└── requirements.txt             # Python dependencies
```

---

## Core Components

### 1. **main.py** - Application Entry Point

**Purpose**: Initializes the FastAPI application, configures middleware, and mounts routers.

**Key Features**:
- FastAPI app initialization with title and configuration
- CORS middleware setup for cross-origin requests
- TrustedHost middleware for security
- Health check endpoint (`GET /health`)
- Dual routing system:
  - Direct routes for backward compatibility
  - `/api` prefixed routes for organized structure
- Socket.IO integration for real-time communication
- Environment variable validation on startup

**Middleware Configuration**:
```python
- CORSMiddleware: Allows specified origins with credentials
- TrustedHostMiddleware: Validates trusted hosts
```

**Mounted Routers**:
- Auth Router (Authentication endpoints)
- Users Router (User profile endpoints)
- Patients Router (Patient management)
- Recipients Router (Care recipient management)
- Alerts Router (Alert management)
- Locations Router (Location tracking)
- Activities Router (Activity logging)
- Notifications Router (Notification management)

---

### 2. **config.py** - Configuration Management

**Purpose**: Centralized configuration using Pydantic settings.

**Configuration Parameters**:
```python
app_name: str = "Remora Caregiver Backend (FastAPI)"
environment: str = "development" (from env)
database_url: str = MongoDB Atlas connection string
jwt_secret: str = JWT signing secret (from env)
jwt_algorithm: str = "HS256"
jwt_exp_days: int = 7
client_origin: str = CORS origin (from env, default "*")
port: int = 4000 (from env)
```

**Usage**: `get_settings()` returns a cached Settings instance via `@lru_cache`.

---

### 3. **db.py** - Database Management

**Purpose**: Manages MongoDB connections and database operations.

**Key Functions**:

#### `get_client() -> AsyncIOMotorClient`
- Creates and returns a persistent MongoDB client
- Singleton pattern with global `_client` variable
- Connection parameters:
  - `serverSelectionTimeoutMS: 30000`
  - `connectTimeoutMS: 30000`
  - `retryWrites: True`
- Logs connection info with masked password
- Raises ValueError if DATABASE_URL is not set

#### `get_database() -> AsyncIOMotorDatabase`
- Returns the target database from MongoDB
- Extracts database name from URL (case-sensitive)
- Falls back to "remora" if not specified
- Uses exact case from DATABASE_URL

#### `serialize_mongo_document(doc) -> Dict | None`
- Converts MongoDB documents to JSON-serializable format
- Maps MongoDB's `_id` field to `id` for Prisma-like schema
- Removes and converts ObjectId to string
- Returns None if document is None

---

### 4. **auth.py** - Authentication & Authorization

**Purpose**: Handles user registration, login, and JWT token management.

**Data Models**:
```python
UserInDB: Database user representation
RegisterRequest: Email, password, name, role (CAREGIVER/PATIENT)
RegisterResponse: Created user details
LoginRequest: Email and password
LoginUser: User info in login response
LoginResponse: JWT token and user details
```

**Key Functions**:

#### `_hash_password(password: str) -> str`
- Uses bcrypt with 10 rounds for password hashing
- Returns UTF-8 encoded hash string

#### `_verify_password(password: str, hashed: str) -> bool`
- Verifies password against bcrypt hash
- Returns True if valid, False otherwise

#### `_create_access_token(data: Dict) -> str`
- Creates JWT token with 7-day expiration
- Signs with HS256 algorithm
- Includes user id, role, and email in payload

#### `_get_user_by_email(email: str) -> Optional[UserInDB]`
- Queries User collection by email
- Returns deserialized UserInDB object
- Logs search operations for debugging

#### `get_current_user(token: str) -> Dict[str, Any]`
- OAuth2 dependency for JWT validation
- Decodes token and validates signature
- Retrieves user from database
- Raises HTTP 401 if token invalid

#### `get_current_patient(current_user) -> Dict[str, Any]`
- Role-based dependency
- Ensures user has PATIENT role
- Raises HTTP 403 if not a patient

#### `get_current_caregiver(current_user) -> Dict[str, Any]`
- Role-based dependency
- Ensures user has CAREGIVER role
- Raises HTTP 403 if not a caregiver

**Endpoints**:

##### `POST /auth/register`
- Registers new user (CAREGIVER or PATIENT)
- Validates email uniqueness
- Hashes password with bcrypt
- Returns user details with ID

##### `POST /auth/login`
- Authenticates user with email and password
- Verifies credentials against database
- Returns JWT token valid for 7 days

---

### 5. **realtime.py** - Socket.IO Real-time Server

**Purpose**: Manages WebSocket connections for real-time event broadcasting.

**Socket.IO Events**:

#### `connect(sid, environ, auth)`
- Called when client connects
- Returns True to accept connection

#### `joinRecipientRoom(sid, recipientId)`
- Client joins a room named `recipient:{recipientId}`
- Used for targeted message broadcasting

#### `emit_alert_new(recipient_id, payload)`
- Emits alert event to specific recipient room
- Broadcasts to room: `recipient:{recipient_id}`
- Event name: `alert:new`
- Runs as background task

#### `emit_location_new(recipient_id, payload)`
- Emits location update to specific recipient room
- Broadcasts to room: `recipient:{recipient_id}`
- Event name: `location:new`
- Runs as background task

**Configuration**:
```python
async_mode: "asgi"
cors_allowed_origins: Dynamic based on CLIENT_ORIGIN setting
```

---

### 6. **routers_users.py** - User Management

**Purpose**: User profile and search functionality.

**Endpoints**:

#### `GET /users/me`
- Returns current authenticated user's profile
- Requires valid JWT token
- Returns: id, email, name, role

#### `GET /users/caregivers?query=...`
- Searches for caregivers by name or email
- Query parameter: search term (optional)
- Supports Gmail and partial email matching
- Prioritizes exact email matches
- Returns: List of caregivers with id, name, email
- Limited to 50 results

---

### 7. **routers_patients.py** - Patient Management

**Purpose**: Patient-specific operations including location tracking, caregiver connection, and SOS alerts.

**Data Models**:
```python
PatientLocationPing: {
    latitude: float,
    longitude: float,
    accuracy: float,
    battery: int,
    recordedAt: datetime
}
ConnectCaregiverRequest: {
    caregiverCode: str (email or ID)
}
```

**Key Functions**:

#### `_ensure_patient_profile(user_id) -> Dict`
- Creates PatientProfile document if not exists
- Updates `updatedAt` timestamp
- Schema:
  ```
  {
    userId: string,
    createdAt: datetime,
    updatedAt: datetime
  }
  ```

**Endpoints**:

#### `POST /patients/me/location`
- **Role**: PATIENT
- Sends device location ping
- Creates/updates PatientProfile
- Stores location in PatientLocation collection
- Returns: Location document

#### `POST /patients/connect-caregiver`
- **Role**: PATIENT
- Connects patient to caregiver via email or ID
- Validates caregiver exists
- Prevents self-connection
- Checks for existing link
- Creates PatientCaregiverLink document
- Returns: Connection status and details

#### `GET /patients/me/caregivers`
- **Role**: PATIENT
- Returns list of connected caregivers
- Includes: id, name, email, connectedAt timestamp

#### `POST /patients/sos`
- **Role**: PATIENT
- Sends SOS alert to all connected caregivers
- Includes latest patient location
- Creates Alert document with CRITICAL severity
- Returns: Alert ID and caregiver count notified

#### `GET /patients/caregiver/my-patients`
- **Role**: CAREGIVER
- Returns all linked patients
- Includes latest location for each patient
- Returns: List with patient info and location data

---

### 8. **routers_alerts.py** - Alert Management

**Purpose**: Create, retrieve, and acknowledge alerts.

**Data Models**:
```python
AlertCreate: {
    recipientId: string,
    title: string,
    message: string,
    type: string,
    severity: string (default: "INFO")
}
```

**Alert Document Schema**:
```
{
    recipientId: string,
    title: string,
    message: string,
    type: string,
    severity: string,
    isAcknowledged: boolean,
    createdAt: datetime
}
```

**Endpoints**:

#### `GET /alerts?recipientId=...`
- Lists alerts, optionally filtered by recipientId
- Sorted by createdAt (newest first)
- Returns: Array of alert documents

#### `POST /alerts`
- Creates new alert
- Validates required fields
- Sets isAcknowledged to false by default
- Emits real-time event via Socket.IO
- Returns: Created alert document

#### `POST /alerts/{alert_id}/ack`
- Acknowledges alert by ID
- Sets isAcknowledged to true
- Returns: Updated alert document

---

### 9. **routers_locations.py** - Location Tracking

**Purpose**: Store and retrieve location data.

**Data Models**:
```python
LocationCreate: {
    recipientId: string,
    latitude: float,
    longitude: float,
    accuracy: float,
    battery: int,
    recordedAt: datetime
}
```

**Location Document Schema**:
```
{
    recipientId: string,
    latitude: float,
    longitude: float,
    accuracy: float,
    battery: int,
    recordedAt: datetime
}
```

**Endpoints**:

#### `GET /locations?recipientId=...&limit=...`
- Lists locations for a recipient
- Requires recipientId query parameter
- Default limit: 50, max determined by parameter
- Sorted by recordedAt (newest first)
- Returns: Array of location documents

#### `POST /locations`
- Creates new location record
- Validates recipientId and coordinates
- Emits real-time event via Socket.IO
- Returns: Created location document

---

### 10. **routers_activities.py** - Activity Tracking

**Purpose**: Log and retrieve patient activities and health metrics.

**Data Models**:
```python
ActivityCreate: {
    recipientId: string,
    kind: string (e.g., "steps", "heart_rate"),
    value: float,
    unit: string,
    metadata: dict,
    recordedAt: datetime
}
```

**Activity Document Schema**:
```
{
    recipientId: string,
    kind: string,
    value: float,
    unit: string,
    metadata: dict,
    recordedAt: datetime
}
```

**Endpoints**:

#### `GET /activities?recipientId=...&kind=...&from=...&to=...`
- Lists activities with multiple filters
- Filter by: recipientId, kind, date range
- Date range: ISO format strings
- Limit: 200 results
- Sorted by recordedAt (newest first)
- Returns: Array of activity documents

#### `POST /activities`
- Creates new activity record
- Validates required fields (recipientId, kind)
- Returns: Created activity document

---

### 11. **routers_recipients.py** - Care Recipient Management

**Purpose**: Caregivers manage care recipients (people they care for).

**Data Models**:
```python
RecipientCreate: {
    name: string,
    age: int,
    relationship: string,
    avatarUrl: string
}
RecipientUpdate: {
    name: string (optional),
    age: int (optional),
    relationship: string (optional),
    avatarUrl: string (optional)
}
```

**CareRecipient Document Schema**:
```
{
    name: string,
    age: int,
    relationship: string,
    avatarUrl: string,
    createdAt: datetime,
    updatedAt: datetime
}
```

**CaregiverOnRecipient Link Schema**:
```
{
    caregiverId: string,
    recipientId: string,
    assignedAt: datetime
}
```

**Endpoints**:

#### `GET /recipients`
- Lists all recipients for current caregiver
- Returns recipients via CaregiverOnRecipient links
- Returns: Array of recipient documents

#### `POST /recipients`
- Creates new care recipient
- Links to current caregiver
- Returns: Created recipient document

#### `GET /recipients/{recipient_id}`
- Gets specific recipient by ID
- Returns: Recipient document

#### `PUT /recipients/{recipient_id}`
- Updates recipient information
- Updates `updatedAt` timestamp
- Returns: Updated recipient document

#### `DELETE /recipients/{recipient_id}`
- Deletes recipient
- Removes all caregiver links
- Returns: 204 No Content

---

### 12. **routers_notifications.py** - Notifications

**Purpose**: User notifications system.

**Data Models**:
```python
NotificationCreate: {
    title: string,
    message: string,
    type: string
}
```

**Notification Document Schema**:
```
{
    userId: string,
    title: string,
    message: string,
    type: string,
    isRead: boolean,
    createdAt: datetime
}
```

**Endpoints**:

#### `GET /notifications`
- Lists notifications for current user
- Sorted by createdAt (newest first)
- Returns: Array of notification documents

#### `POST /notifications`
- Creates new notification
- Links to current user
- Sets isRead to false by default
- Returns: Created notification document

#### `POST /notifications/{notification_id}/read`
- Marks notification as read
- Sets isRead to true
- Returns: Updated notification document

---

## Database Schema

### Collections Overview

#### **User** Collection
Primary user authentication and profile storage.
```javascript
{
    _id: ObjectId,
    email: String (unique),
    passwordHash: String,
    name: String,
    role: String ("CAREGIVER" | "PATIENT"),
    createdAt: DateTime,
    updatedAt: DateTime
}
```

#### **PatientProfile** Collection
Patient-specific profile information.
```javascript
{
    _id: ObjectId,
    userId: String (references User._id),
    createdAt: DateTime,
    updatedAt: DateTime
}
```

#### **PatientLocation** Collection
Latest location ping from patient device (upserted per patient).
```javascript
{
    _id: ObjectId,
    userId: String (references User._id),
    latitude: Double,
    longitude: Double,
    accuracy: Double,
    battery: Integer,
    recordedAt: DateTime,
    updatedAt: DateTime,
    createdAt: DateTime
}
```

#### **PatientCaregiverLink** Collection
Junction table linking patients to caregivers.
```javascript
{
    _id: ObjectId,
    patientUserId: String (references User._id),
    caregiverUserId: String (references User._id),
    status: String ("ACTIVE" | "INACTIVE"),
    createdAt: DateTime,
    updatedAt: DateTime
}
```

#### **Alert** Collection
Alerts and critical notifications.
```javascript
{
    _id: ObjectId,
    recipientId: String,
    title: String,
    message: String,
    type: String,
    severity: String ("INFO" | "WARNING" | "CRITICAL"),
    isAcknowledged: Boolean,
    createdAt: DateTime,
    
    // For SOS alerts:
    patientUserId: String (optional),
    caregiverUserIds: Array<String> (optional),
    latitude: Double (optional),
    longitude: Double (optional)
}
```

#### **Location** Collection
Location history records.
```javascript
{
    _id: ObjectId,
    recipientId: String,
    latitude: Double,
    longitude: Double,
    accuracy: Double,
    battery: Integer,
    recordedAt: DateTime
}
```

#### **Activity** Collection
Health and activity metrics.
```javascript
{
    _id: ObjectId,
    recipientId: String,
    kind: String (e.g., "steps", "heart_rate", "sleep"),
    value: Double,
    unit: String,
    metadata: Object (flexible),
    recordedAt: DateTime
}
```

#### **CareRecipient** Collection
Care recipients managed by caregivers.
```javascript
{
    _id: ObjectId,
    name: String,
    age: Integer,
    relationship: String,
    avatarUrl: String,
    createdAt: DateTime,
    updatedAt: DateTime
}
```

#### **CaregiverOnRecipient** Collection
Junction table linking caregivers to care recipients.
```javascript
{
    _id: ObjectId,
    caregiverId: String (references User._id),
    recipientId: String (references CareRecipient._id),
    assignedAt: DateTime
}
```

#### **Notification** Collection
User notifications.
```javascript
{
    _id: ObjectId,
    userId: String (references User._id),
    title: String,
    message: String,
    type: String,
    isRead: Boolean,
    createdAt: DateTime
}
```

---

## API Endpoints

### Authentication Routes
| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| POST | `/auth/register` | Public | Register new user |
| POST | `/auth/login` | Public | Authenticate user |

### User Routes
| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| GET | `/users/me` | Authenticated | Get current user profile |
| GET | `/users/caregivers?query=...` | Authenticated | Search caregivers |

### Patient Routes
| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| POST | `/patients/me/location` | PATIENT | Send location ping |
| POST | `/patients/connect-caregiver` | PATIENT | Connect to caregiver |
| GET | `/patients/me/caregivers` | PATIENT | List connected caregivers |
| POST | `/patients/sos` | PATIENT | Send SOS alert |
| GET | `/patients/caregiver/my-patients` | CAREGIVER | List assigned patients |

### Alert Routes
| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| GET | `/alerts?recipientId=...` | Authenticated | List alerts |
| POST | `/alerts` | Authenticated | Create alert |
| POST | `/alerts/{alert_id}/ack` | Authenticated | Acknowledge alert |

### Location Routes
| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| GET | `/locations?recipientId=...&limit=50` | Authenticated | List locations |
| POST | `/locations` | Authenticated | Create location |

### Activity Routes
| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| GET | `/activities?recipientId=...&kind=...&from=...&to=...` | Authenticated | List activities |
| POST | `/activities` | Authenticated | Create activity |

### Recipient Routes
| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| GET | `/recipients` | CAREGIVER | List recipients |
| POST | `/recipients` | CAREGIVER | Create recipient |
| GET | `/recipients/{recipient_id}` | Authenticated | Get recipient |
| PUT | `/recipients/{recipient_id}` | Authenticated | Update recipient |
| DELETE | `/recipients/{recipient_id}` | Authenticated | Delete recipient |

### Notification Routes
| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| GET | `/notifications` | Authenticated | List notifications |
| POST | `/notifications` | Authenticated | Create notification |
| POST | `/notifications/{notification_id}/read` | Authenticated | Mark as read |

### System Routes
| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| GET | `/health` | Public | Health check |

---

## Authentication & Security

### JWT Implementation

**Token Structure**:
```python
{
    "id": "user_id",
    "role": "CAREGIVER" or "PATIENT",
    "email": "user@example.com",
    "exp": datetime (7 days from creation)
}
```

**Configuration**:
- Algorithm: HS256
- Secret: From `JWT_SECRET` environment variable
- Expiration: 7 days
- Encoding: UTF-8

### Password Security

- **Hashing**: bcrypt with 10 rounds
- **Verification**: bcrypt checkpw comparison
- **Storage**: Passwords never stored in plaintext

### Role-Based Access Control (RBAC)

**Two User Roles**:
1. **CAREGIVER**: Can manage recipients, view alerts, track locations
2. **PATIENT**: Can send location, connect to caregivers, trigger SOS

**Dependency Injection**:
```python
Depends(get_current_user)      # Any authenticated user
Depends(get_current_patient)   # Must be PATIENT role
Depends(get_current_caregiver) # Must be CAREGIVER role
```

### CORS & Middleware

**CORSMiddleware Configuration**:
- Dynamic origin: From `CLIENT_ORIGIN` env variable (or "*" for all)
- Credentials: Allowed
- Methods: GET, POST, PUT, DELETE, OPTIONS
- Headers: All allowed

**TrustedHostMiddleware**:
- Allowed hosts: All ("*")
- Prevents Host header attacks

---

## Real-time Communication

### Socket.IO Implementation

**Connection Flow**:
1. Client connects to WebSocket
2. Client emits `joinRecipientRoom` with recipientId
3. Client joins room: `recipient:{recipientId}`
4. Server emits events to specific room

**Real-time Events**:

#### Alert Event
- **Event Name**: `alert:new`
- **Room**: `recipient:{recipientId}`
- **Payload**: Full alert document
- **Trigger**: POST /alerts endpoint

#### Location Event
- **Event Name**: `location:new`
- **Room**: `recipient:{recipientId}`
- **Payload**: Full location document
- **Trigger**: POST /locations endpoint

**Emission Functions**:
```python
emit_alert_new(recipient_id, payload)      # Broadcast alert
emit_location_new(recipient_id, payload)   # Broadcast location
```

---

## File Descriptions

### **main.py** (103 lines)
Entry point for FastAPI application. Initializes app, mounts routers, sets up middleware, and Socket.IO server.

### **config.py** (27 lines)
Configuration management using Pydantic. Loads environment variables and provides cached settings instance.

### **db.py** (98 lines)
Database connection and utilities. Manages MongoDB client, database selection, and document serialization.

### **auth.py** (216 lines)
Authentication and authorization. Implements JWT tokens, password hashing, user registration/login, and role-based access control.

### **realtime.py** (26 lines)
Socket.IO server setup. Manages WebSocket connections and real-time event broadcasting.

### **routers_users.py** (67 lines)
User profile and caregiver search endpoints. Allows users to view their profile and search for caregivers.

### **routers_patients.py** (334 lines)
Patient management endpoints. Handles location tracking, caregiver connection, SOS alerts, and caregiver-patient relationships.

### **routers_alerts.py** (70 lines)
Alert management endpoints. Create, list, and acknowledge alerts with real-time broadcasting.

### **routers_locations.py** (64 lines)
Location tracking endpoints. Store and retrieve location history with real-time updates.

### **routers_activities.py** (70 lines)
Activity tracking endpoints. Log and query health/activity metrics with filtering and date range support.

### **routers_recipients.py** (95 lines)
Care recipient management. CRUD operations for recipients managed by caregivers.

### **routers_notifications.py** (65 lines)
Notification system. Create, retrieve, and mark notifications as read.

---

## Environment Variables

Required environment variables in `.env`:

```env
# Database
DATABASE_URL=mongodb+srv://user:password@cluster.mongodb.net/Remora?appName=Remora

# Authentication
JWT_SECRET=your_secret_key_here

# Environment
ENVIRONMENT=development|production

# CORS
CLIENT_ORIGIN=http://localhost:3000|*

# Server
PORT=4000
```

---

## Running the Application

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run with uvicorn
uvicorn fastapi_app.main:get_app --reload --host 0.0.0.0 --port 4000
```

### Production
```bash
# Run with uvicorn
uvicorn fastapi_app.main:get_app --host 0.0.0.0 --port 4000 --workers 4
```

---

## Error Handling

### HTTP Status Codes
- **200**: Success
- **201**: Created
- **204**: No Content
- **400**: Bad Request (validation error)
- **401**: Unauthorized (invalid token)
- **403**: Forbidden (insufficient permissions)
- **404**: Not Found
- **409**: Conflict (duplicate email)
- **500**: Internal Server Error
- **503**: Service Unavailable (database error)

### Exception Types
- `HTTPException`: Standard HTTP errors with status codes
- `ValueError`: Critical configuration errors
- `jwt.PyJWTError`: Token validation errors

---

## Data Flow Diagrams

### User Registration Flow
```
Client
  │
  ├─→ POST /auth/register
  │   {email, password, name, role}
  │
Server
  │
  ├─→ Check email uniqueness
  ├─→ Hash password with bcrypt
  ├─→ Create User document
  │
  └─→ Return {id, email, name, role}
```

### Login & Token Generation
```
Client
  │
  ├─→ POST /auth/login
  │   {email, password}
  │
Server
  │
  ├─→ Find user by email
  ├─→ Verify password
  ├─→ Create JWT token (7 days exp)
  │
  └─→ Return {token, user{id, email, name, role}}
```

### Patient Location Tracking
```
Patient App
  │
  ├─→ POST /patients/me/location
  │   {latitude, longitude, accuracy, battery}
  │
Server
  │
  ├─→ Ensure PatientProfile exists
  ├─→ Upsert PatientLocation
  ├─→ Emit socket.io event "location:new"
  │
  ├─→ Caregiver App (listening)
  │   └─→ Receives real-time location update
  │
  └─→ Return {location document}
```

### Caregiver-Patient Connection
```
Patient App
  │
  ├─→ POST /patients/connect-caregiver
  │   {caregiverCode: email or ID}
  │
Server
  │
  ├─→ Search User by email/ID
  ├─→ Validate caregiver exists
  ├─→ Validate not self-connection
  ├─→ Check existing link
  ├─→ Create PatientCaregiverLink
  │
  └─→ Return {status, caregiverId, caregiverName}
```

### SOS Alert System
```
Patient App
  │
  ├─→ POST /patients/sos
  │
Server
  │
  ├─→ Get connected caregivers
  ├─→ Get patient's latest location
  ├─→ Create Alert (CRITICAL severity)
  ├─→ Emit socket.io "alert:new" to all caregivers
  │
  ├─→ Caregiver Apps (listening)
  │   └─→ Receive critical alert notification
  │
  └─→ Return {alertId, caregiversNotified}
```

---

## Summary

The Remora Patient App backend is a comprehensive, asynchronous FastAPI application designed to facilitate secure patient-caregiver communication with real-time capabilities. It implements industry-standard practices for authentication, data validation, and error handling while maintaining a modular, scalable architecture. The system supports both REST API and WebSocket communication, enabling real-time location tracking, alerts, and notifications essential for remote patient monitoring.

