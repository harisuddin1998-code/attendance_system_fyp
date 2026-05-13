# AI Face Recognition Attendance System - Implementation Plan

This document outlines the architecture, current implementation, and roadmap for the AI-based attendance tracking project.

## Current Project Status
The project is a functional Flask-based web application that uses deep learning for face recognition and object tracking to automate attendance in a classroom environment.

### Core Components
1.  **Backend**: Flask (Python)
2.  **Database**: SQLite (`attendance.db`)
3.  **Face Recognition**: DeepFace (VGG-Face model)
4.  **Tracking**: DeepSORT
5.  **Computer Vision**: OpenCV
6.  **Frontend**: HTML/CSS (Vanilla)

## User Review Required

> [!IMPORTANT]
> The current system relies on synchronous processing of frames within the Flask `generate_frames` generator. For multiple high-resolution streams, this may lead to latency.

> [!TIP]
> Consider moving face recognition logic to a background thread or a separate processing service (e.g., Celery/Redis) to keep the video stream fluid.

## Proposed Changes & Enhancements

### 1. Performance Optimization
*   **[MODIFY] [app.py](file:///c:/fyp1%20py3.11/app.py)**
    *   Implement asynchronous frame processing.
    *   Optimize `PROCESS_FRAME_INTERVAL` based on hardware capabilities.
    *   Integrate hardware acceleration (CUDA) for TensorFlow/Keras if available.

### 2. Multi-Camera Synchronization
*   **[MODIFY] [app.py](file:///c:/fyp1%20py3.11/app.py)**
    *   Improve logic for combining logs from 'Gate' and 'CCTV' cameras.
    *   Implement a "Confidence Scoring" system to merge overlapping detections.

### 3. Reporting & Analytics
*   **[NEW] analytics.py**
    *   Create a module to generate weekly/monthly attendance reports.
    *   Export data to CSV/Excel formats.

### 4. Real-time Dashboard Updates
*   **[MODIFY] [templates/live.html](file:///c:/fyp1%20py3.11/templates/live.html)**
    *   Use WebSockets (Flask-SocketIO) instead of polling `/api/live_status` for lower latency.

## Verification Plan

### Automated Tests
*   Run `test_cameras.py` to verify RTSP stream connectivity.
*   Run `test_flask_app.py` to ensure all routes are accessible.

### Manual Verification
*   Enroll a new student via `enroll_faces.py` and verify recognition in `live_class`.
*   Start a session, stay in front of the camera, and verify the log entry in `report`.
