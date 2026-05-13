# White Paper: AI-Powered Autonomous Attendance System

## 1. Abstract
Traditional attendance systems rely on manual input or physical tokens (RFID/Biometrics), which are prone to "buddy punching" and time inefficiencies. This project presents an autonomous solution using Deep Learning and Computer Vision to track attendance in real-time using IP camera streams.

## 2. Introduction
The system leverages state-of-the-art face recognition models and multi-object tracking algorithms to identify individuals and log their presence duration automatically. By integrating RTSP-based IP cameras, the system can monitor large environments such as classrooms or office entrances without human intervention.

## 3. Technology Stack
*   **Deep Learning Framework**: TensorFlow/Keras (via DeepFace)
*   **Face Recognition Model**: VGG-Face (97.27% accuracy on LFW)
*   **Object Tracking**: DeepSORT (Simple Online and Realtime Tracking with a Deep Association Metric)
*   **Backend**: Flask (Python)
*   **Database**: SQLite (Relational storage for logs and metadata)
*   **Frontend**: HTML5, CSS3, JavaScript (Real-time dashboarding)

## 4. System Architecture
The system follows a modular architecture:
1.  **Ingestion Layer**: Captures video frames from multiple RTSP streams (CCTV, Mobile Cameras).
2.  **Processing Layer**:
    *   **Detection**: YOLO (You Only Look Once) face detector identifies face regions.
    *   **Recognition**: DeepFace generates embeddings and compares them against the enrolled database using Cosine Similarity.
    *   **Tracking**: DeepSORT maintains identity consistency across frames even if the face is temporarily occluded.
3.  **Persistence Layer**: Logs "First Seen", "Last Seen", and "Total Duration" into the SQLite database.
4.  **Presentation Layer**: A web dashboard for administrators (HOD/Teachers) to monitor live sessions and view generated reports.

## 5. Methodology
### 5.1 Face Enrollment
Face images are processed once to generate a high-dimensional embedding (128-d or 4096-d depending on the model). These embeddings are stored as BLOBs in the database, ensuring fast comparison during live tracking.

### 5.2 Live Recognition & Tracking
To balance accuracy and performance, the system processes every $n$-th frame (default $n=10$). The recognition engine uses a distance threshold (default $0.50$) to classify faces. DeepSORT uses a Kalman Filter to predict the next position of a detected face, reducing the need for constant re-recognition.

### 5.3 Attendance Logic
Attendance is finalized when a session ends. The system classifies attendance based on:
*   **Present**: Seen within the first 25 minutes and present until the end.
*   **Late**: First seen after 25 minutes.
*   **Early Leave**: Last seen significantly before the session ended.

## 6. Results & Conclusion
The system successfully demonstrates the ability to track multiple individuals simultaneously. The use of VGG-Face provides robust recognition even under varying lighting conditions. Future work involves scaling the system to handle 100+ concurrent streams using edge computing devices.

---
**Author**: Antigravity AI
**Date**: April 23, 2026
