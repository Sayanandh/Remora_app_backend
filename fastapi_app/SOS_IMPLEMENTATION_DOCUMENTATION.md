# SOS Emergency System - Implementation Documentation

## Overview

This documentation covers the SOS emergency system that allows patients to trigger emergency alerts via ESP8266 hardware buttons, which then notify their registered caregivers in real-time.

---

## 📋 Table of Contents

1. [System Architecture](#system-architecture)
2. [Database Schema Changes](#database-schema-changes)
3. [Backend API Endpoints](#backend-api-endpoints)
4. [Patient App Implementation](#patient-app-implementation)
5. [Caregiver Notifications](#caregiver-notifications)
6. [Complete Flow Diagram](#complete-flow-diagram)
7. [Testing Guide](#testing-guide)

---

## 🏗️ System Architecture

```
ESP8266 Button → POST /api/sos → Backend Updates DB → Creates Notifications → Caregiver App Receives Alert
```

**Key Components:**
- **ESP8266 Hardware**: Physical SOS button device
- **Backend API**: FastAPI endpoints for device registration and SOS handling
- **Database**: MongoDB stores user status, device tokens, and notifications
- **Real-time Communication**: Socket.IO for instant caregiver notifications
- **Patient App**: Flutter app for device registration
- **Caregiver App**: Flutter app for receiving emergency alerts

---

## 🗄️ Database Schema Changes

### 1. User Collection Updates

The `User` collection now includes additional fields:

```javascript
{
  "_id": ObjectId("..."),
  "email": "patient@example.com",
  "name": "John Doe",
  "role": "PATIENT",
  "passwordHash": "...",
  "status": "emergency",  // ✅ NEW: Status field
  "emergencyTriggeredAt": ISODate("2024-01-15T10:30:00Z"),  // ✅ NEW: Emergency timestamp
  "deviceTokens": [  // ✅ NEW: Array of registered devices
    {
      "token": "secure_token_string_here",
      "deviceName": "ESP8266 Button",
      "deviceType": "esp8266",
      "registeredAt": ISODate("2024-01-15T09:00:00Z")
    }
  ],
  "createdAt": ISODate("..."),
  "updatedAt": ISODate("...")
}
```

**Status Values:**
- `null` or not set: Normal status
- `"emergency"`: Patient has triggered SOS alert

### 2. Notification Collection

When SOS is triggered, notifications are created for caregivers:

```javascript
{
  "_id": ObjectId("..."),
  "userId": "caregiver_user_id",  // Caregiver who receives notification
  "title": "🚨 SOS Alert from John Doe",
  "message": "John Doe has triggered an emergency SOS alert. Immediate attention required!",
  "type": "SOS",
  "isRead": false,
  "createdAt": ISODate("2024-01-15T10:30:00Z"),
  "relatedPatientId": "patient_user_id",  // ✅ NEW: Link to patient
  "relatedPatientName": "John Doe",  // ✅ NEW: Patient name
  "latitude": 12.9716,  // ✅ NEW: Patient location (if available)
  "longitude": 77.5946  // ✅ NEW: Patient location (if available)
}
```

### 3. Alert Collection

Alerts are also created for real-time Socket.IO notifications:

```javascript
{
  "_id": ObjectId("..."),
  "recipientId": "patient_user_id",
  "title": "SOS Alert from John Doe",
  "message": "John Doe (patient@example.com) has triggered an emergency SOS alert.",
  "type": "SOS",
  "severity": "CRITICAL",
  "isAcknowledged": false,
  "createdAt": ISODate("2024-01-15T10:30:00Z"),
  "patientUserId": "patient_user_id",
  "caregiverUserIds": ["caregiver1_id", "caregiver2_id"],
  "latitude": 12.9716,
  "longitude": 77.5946
}
```

### 4. PatientCaregiverLink Collection

Links patients to their caregivers (existing collection, used for notifications):

```javascript
{
  "_id": ObjectId("..."),
  "patientUserId": "patient_user_id",
  "caregiverUserId": "caregiver_user_id",
  "status": "ACTIVE",
  "createdAt": ISODate("..."),
  "updatedAt": ISODate("...")
}
```

---

## 🔌 Backend API Endpoints

### 1. Register Device

**Endpoint:** `POST /api/sos/register-device`

**Authentication:** Required (JWT token)

**Request Body:**
```json
{
  "deviceName": "ESP8266 Button",
  "deviceType": "esp8266"
}
```

**Response:**
```json
{
  "success": true,
  "deviceToken": "secure_token_string_here",
  "deviceName": "ESP8266 Button",
  "deviceType": "esp8266",
  "message": "Device registered successfully. Store this token on your ESP8266."
}
```

**Purpose:** Patients register their ESP8266 device and receive a unique token to identify them in SOS requests.

---

### 2. Handle SOS Request

**Endpoint:** `POST /api/sos`

**Authentication:** None (device token based)

**Request Body:**
```json
{
  "type": "sos",
  "device": "esp8266",
  "deviceToken": "secure_token_string_here",
  "timestamp": 1705312200000
}
```

**Alternative (Query Parameter):**
```
POST /api/sos?deviceToken=secure_token_string_here
Body: {"type": "sos", "device": "esp8266"}
```

**Response:**
```json
{
  "success": true,
  "message": "SOS received and user status updated to emergency",
  "userId": "patient_user_id",
  "status": "emergency",
  "device": "esp8266",
  "timestamp": 1705312200000,
  "caregiversNotified": 2,
  "alertId": "alert_id_here"
}
```

**What Happens:**
1. Identifies patient from device token
2. Updates user `status` to `"emergency"`
3. Sets `emergencyTriggeredAt` timestamp
4. Finds all connected caregivers via `PatientCaregiverLink`
5. Creates notifications for each caregiver
6. Creates alert for real-time Socket.IO notifications
7. Emits real-time alert to caregivers

---

## 📱 Patient App Implementation

### Step 1: Add API Method

In your patient app's API client (`lib/utils/api_client.dart`):

```dart
// Add to ApiClient class
Future<Map<String, dynamic>> registerSOSDevice({
  String deviceName = 'ESP8266',
  String deviceType = 'esp8266',
}) async {
  return post('/api/sos/register-device', body: {
    'deviceName': deviceName,
    'deviceType': deviceType,
  });
}
```

### Step 2: Create Device Registration Screen

Create `lib/screens/sos_device_screen.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../utils/api_client.dart';

class SOSDeviceScreen extends StatelessWidget {
  const SOSDeviceScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('SOS Device Setup'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Icon(Icons.emergency_outlined, size: 80, color: Colors.red),
            const SizedBox(height: 24),
            const Text(
              'Register Your SOS Button',
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            const Text(
              'Register your ESP8266 emergency button to enable SOS functionality.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey),
            ),
            const SizedBox(height: 32),
            ElevatedButton.icon(
              onPressed: () => _registerDevice(context),
              icon: const Icon(Icons.add_circle_outline),
              label: const Text('Register New Device'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 16),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _registerDevice(BuildContext context) async {
    final deviceNameController = TextEditingController(text: 'ESP8266 Button');
    
    final shouldRegister = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Register SOS Device'),
        content: TextField(
          controller: deviceNameController,
          decoration: const InputDecoration(
            labelText: 'Device Name',
            hintText: 'e.g., ESP8266 Button',
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Register'),
          ),
        ],
      ),
    );

    if (shouldRegister != true) return;

    try {
      final authProvider = Provider.of<AuthProvider>(context, listen: false);
      final api = ApiClient();
      api.setToken(authProvider.token);

      // Show loading
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (context) => const Center(child: CircularProgressIndicator()),
      );

      final response = await api.registerSOSDevice(
        deviceName: deviceNameController.text.trim(),
        deviceType: 'esp8266',
      );

      if (!context.mounted) return;
      Navigator.pop(context); // Close loading

      // Show device token
      await _showDeviceTokenDialog(context, response);
    } catch (e) {
      if (!context.mounted) return;
      Navigator.pop(context); // Close loading
      
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error: ${e.toString()}'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  Future<void> _showDeviceTokenDialog(
    BuildContext context,
    Map<String, dynamic> response,
  ) async {
    final deviceToken = response['deviceToken'] as String;
    final deviceName = response['deviceName'] as String? ?? 'Device';

    await showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.check_circle, color: Colors.green, size: 28),
            SizedBox(width: 8),
            Expanded(child: Text('Device Registered!')),
          ],
        ),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('$deviceName has been registered successfully.'),
              const SizedBox(height: 16),
              const Text(
                'Device Token:',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.grey.shade100,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.grey.shade300),
                ),
                child: SelectableText(
                  deviceToken,
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                '⚠️ Copy this token and paste it in your ESP8266 code.',
                style: TextStyle(
                  fontSize: 12,
                  fontStyle: FontStyle.italic,
                  color: Colors.orange,
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
          ElevatedButton.icon(
            onPressed: () {
              Clipboard.setData(ClipboardData(text: deviceToken));
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Token copied to clipboard!'),
                  duration: Duration(seconds: 2),
                ),
              );
              Navigator.pop(context);
            },
            icon: const Icon(Icons.copy, size: 18),
            label: const Text('Copy Token'),
          ),
        ],
      ),
    );
  }
}
```

### Step 3: Update ESP8266 Code

Use the device token in your ESP8266 code:

```cpp
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClientSecure.h>

#define SOS_BUTTON D5
const char* WIFI_SSID = "YourWiFi";
const char* WIFI_PASS = "YourPassword";
const char* DEVICE_TOKEN = "PASTE_TOKEN_HERE";  // From patient app
const char* SOS_URL = "https://your-api.com/api/sos";

void sendSOS() {
  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.begin(client, SOS_URL);
  http.addHeader("Content-Type", "application/json");
  
  String payload = "{"
    "\"type\":\"sos\","
    "\"device\":\"esp8266\","
    "\"deviceToken\":\"" + String(DEVICE_TOKEN) + "\","
    "\"timestamp\":" + String(millis()) +
  "}";
  
  int httpCode = http.POST(payload);
  http.end();
}
```

---

## 🔔 Caregiver Notifications

### How Caregivers Receive Notifications

When a patient triggers SOS:

1. **Database Notification**: A notification document is created in the `Notification` collection for each connected caregiver
2. **Real-time Alert**: An alert is created and emitted via Socket.IO
3. **User Status**: Patient's `status` field in `User` collection is set to `"emergency"`

### Caregiver App Implementation

#### 1. Fetch Notifications

```dart
// In caregiver app
Future<List<Map<String, dynamic>>> fetchNotifications() async {
  final response = await api.get('/api/notifications');
  return List<Map<String, dynamic>>.from(response);
}
```

#### 2. Listen to Socket.IO Alerts

```dart
import 'package:socket_io_client/socket_io_client.dart' as IO;

IO.Socket socket = IO.io(
  'https://your-api.com',
  OptionBuilder()
    .setTransports(['websocket'])
    .setExtraHeaders({'Authorization': 'Bearer $token'})
    .build(),
);

socket.on('alert:new', (data) {
  // Handle incoming alert
  if (data['type'] == 'SOS') {
    showEmergencyAlert(data);
  }
});

// Join patient's room to receive their alerts
socket.emit('joinRecipientRoom', patientId);
```

#### 3. Display Emergency Alert

```dart
void showEmergencyAlert(Map<String, dynamic> alert) {
  showDialog(
    context: context,
    barrierDismissible: false,
    builder: (context) => AlertDialog(
      title: const Row(
        children: [
          Icon(Icons.warning, color: Colors.red, size: 32),
          SizedBox(width: 8),
          Text('🚨 EMERGENCY SOS'),
        ],
      ),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Patient: ${alert['patientName']}'),
          Text('Location: ${alert['latitude']}, ${alert['longitude']}'),
          Text('Time: ${alert['createdAt']}'),
        ],
      ),
      actions: [
        ElevatedButton(
          onPressed: () {
            // Navigate to patient location on map
          },
          child: const Text('View Location'),
        ),
        ElevatedButton(
          onPressed: () {
            // Acknowledge alert
            api.post('/api/alerts/${alert['id']}/ack');
            Navigator.pop(context);
          },
          child: const Text('Acknowledge'),
        ),
      ],
    ),
  );
}
```

#### 4. Check Patient Status

Caregivers can check if their patients are in emergency:

```dart
Future<List<Map<String, dynamic>>> getMyPatients() async {
  final response = await api.get('/api/patients/caregiver/my-patients');
  // Response includes patient info, check their status field
  return List<Map<String, dynamic>>.from(response);
}
```

---

## 📊 Complete Flow Diagram

```
┌─────────────┐
│  ESP8266    │
│   Button    │
└──────┬──────┘
       │ Pressed
       ▼
┌──────────────────────────┐
│  POST /api/sos           │
│  Body: {                 │
│    deviceToken: "..."    │
│  }                       │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│  1. Identify Patient     │
│     (via deviceToken)    │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│  2. Update User Status   │
│     status = "emergency" │
│     emergencyTriggeredAt │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│  3. Find Caregivers      │
│     (PatientCaregiverLink│
│      collection)         │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│  4. Create Notifications │
│     (for each caregiver) │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│  5. Create Alert         │
│     (for Socket.IO)      │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│  6. Emit Real-time Alert │
│     (Socket.IO)          │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│  Caregiver App           │
│  Receives Notification   │
│  & Real-time Alert       │
└──────────────────────────┘
```

---

## 🧪 Testing Guide

### 1. Test Device Registration

```bash
# Login as patient first
curl -X POST https://your-api.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"patient@example.com","password":"password"}'

# Use token from response
curl -X POST https://your-api.com/api/sos/register-device \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"deviceName":"Test Button","deviceType":"esp8266"}'
```

### 2. Test SOS Trigger

```bash
curl -X POST https://your-api.com/api/sos \
  -H "Content-Type: application/json" \
  -d '{
    "type":"sos",
    "device":"esp8266",
    "deviceToken":"YOUR_DEVICE_TOKEN",
    "timestamp":1705312200000
  }'
```

### 3. Verify Database Changes

```javascript
// Check user status
db.User.findOne({email: "patient@example.com"})
// Should show: status: "emergency"

// Check notifications
db.Notification.find({type: "SOS"})
// Should show notifications for all connected caregivers

// Check alerts
db.Alert.find({type: "SOS"})
// Should show the created alert
```

### 4. Test Caregiver Notification

1. Login as caregiver in the app
2. Ensure patient is connected (PatientCaregiverLink exists)
3. Trigger SOS from ESP8266
4. Caregiver app should receive notification immediately

---

## 🔐 Security Considerations

1. **Device Tokens**: Tokens are securely generated using `secrets.token_urlsafe(32)` (43-44 characters)
2. **Authentication**: Device registration requires JWT authentication
3. **Token Storage**: Store device tokens securely on ESP8266 (consider EEPROM for persistence)
4. **HTTPS**: Always use HTTPS in production (ngrok supports HTTPS)

---

## 📝 Summary

### When Patient is in Danger:

**Database Changes:**
1. ✅ `User.status` → `"emergency"`
2. ✅ `User.emergencyTriggeredAt` → Current timestamp
3. ✅ `Notification` documents created for each caregiver
4. ✅ `Alert` document created for real-time notification

**Caregiver Receives:**
1. ✅ Push notification in app (from Notification collection)
2. ✅ Real-time Socket.IO alert
3. ✅ Can check patient status via `/api/patients/caregiver/my-patients`
4. ✅ Patient location (if available) included in notification

---

## 🚀 Next Steps

1. Implement device registration screen in patient app
2. Update ESP8266 code with device token
3. Implement notification handling in caregiver app
4. Set up Socket.IO listeners in caregiver app
5. Test complete flow end-to-end
6. Add ability to clear emergency status after resolution

---

**Last Updated:** January 2024

