import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_USE_LEGACY_KERAS"] = "1"
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp" # Zero Lag UDP
os.environ["TF_GPU_THREAD_MODE"] = "gpu_private"
os.environ["CUDA_VISIBLE_DEVICES"] = "0"  # Use single GPU
os.environ["TF_FORCE_GPU_ALLOW_GROWTH"] = "true"  # Avoid memory bloat

import sqlite3
import cv2
import time
import numpy as np
from datetime import date
from deepface import DeepFace
import threading
import warnings
warnings.filterwarnings('ignore')

# --- OPTIMIZATION SETTINGS FOR 8GB RAM SYSTEMS ---
USE_GPU = True  # Set to False to use CPU only
USE_LOWER_PRECISION = True  # Use float16 for faster inference

# Threaded Camera Class for zero-lag RTSP
class CameraStream:
    def __init__(self, url):
        self.cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.status, self.frame = False, None
        self.stopped = False
        self.lock = threading.Lock()

    def start(self):
        threading.Thread(target=self.update, args=(), daemon=True).start()
        return self

    def update(self):
        while not self.stopped:
            # Aggressive grab to flush buffer
            if not self.cap.grab():
                time.sleep(0.1)
                continue
            status, frame = self.cap.retrieve()
            if status:
                with self.lock:
                    self.frame = frame
                self.status = True

    def read(self):
        with self.lock:
            return self.status, self.frame.copy() if self.frame is not None else None

    def stop(self):
        self.stopped = True
        self.cap.release()

# --- CONFIGURATION (OPTIMIZED FOR 8GB RAM) ---
DB_PATH = "attendance.db"
MODEL_NAME = "Facenet512"  # Lighter than VGG-Face, faster processing
PROCESS_FRAME_INTERVAL = 90  # Skip 90 frames - heavier load, skip more
DETECTOR_BACKEND = 'retinaface'  # Fastest detector, good accuracy
FRAME_WIDTH = 960  # Reduced from 1280 - 25% less computation
FRAME_HEIGHT = 720  # Fixed height for consistency

# Recognition thresholds
DISTANCE_THRESHOLD = 0.5  # Cosine distance threshold (lower = stricter)
TIMEOUT_SECONDS = 600  # 10 minutes - session timeout

# GPU Memory optimization
MAX_BATCH_SIZE = 2  # Process max 2 faces at a time
FACE_DETECTION_THRESHOLD = 0.8  # Filter low-confidence detections

# Calculate cosine distance between two vectors
def find_cosine_distance(source_rep, test_rep):
    a = np.matmul(np.transpose(source_rep), test_rep)
    b = np.sum(np.multiply(source_rep, source_rep))
    c = np.sum(np.multiply(test_rep, test_rep))
    return 1 - (a / (np.sqrt(b) * np.sqrt(c)))

def init_tracker_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Create logs table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            log_date TEXT NOT NULL,
            total_duration_seconds INTEGER DEFAULT 0,
            UNIQUE(student_id, log_date)
        )
    ''')
    conn.commit()
    return conn

def load_enrolled_faces(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT student_id, name, embedding FROM students")
    records = cursor.fetchall()
    
    enrolled_data = []
    for record in records:
        student_id, name, embedding_blob = record
        # Convert blob back to numpy array
        embedding_arr = np.frombuffer(embedding_blob, dtype='float32')
        enrolled_data.append({
            'student_id': student_id,
            'name': name,
            'embedding': embedding_arr
        })
    print(f"Loaded {len(enrolled_data)} enrolled faces from database.")
    return enrolled_data

def log_duration(conn, student_id, duration_seconds):
    """Updates the total presence duration for a student for the current day."""
    if duration_seconds <= 0:
        return
        
    today = str(date.today())
    cursor = conn.cursor()
    
    # Try inserting. If the record for today already exists, the UNIQUE constraint will throw an error
    try:
        cursor.execute('''
            INSERT INTO attendance_logs (student_id, log_date, total_duration_seconds)
            VALUES (?, ?, ?)
        ''', (student_id, today, int(duration_seconds)))
    except sqlite3.IntegrityError:
        # If exists, update by adding new duration to existing duration
        cursor.execute('''
            UPDATE attendance_logs
            SET total_duration_seconds = total_duration_seconds + ?
            WHERE student_id = ? AND log_date = ?
        ''', (int(duration_seconds), student_id, today))
    
    conn.commit()
    print(f"Logged {int(duration_seconds)} seconds for Student {student_id}.")

def run_tracking():
    conn = init_tracker_db()
    enrolled_faces = load_enrolled_faces(conn)
    
    if not enrolled_faces:
        print("No faces are enrolled! Please enroll faces first.")
        return

    print(f"\n🚀 OPTIMIZED MODE - 8GB RAM System")
    print(f"   Model: {MODEL_NAME} | Detector: {DETECTOR_BACKEND}")
    print(f"   Resolution: {FRAME_WIDTH}x{FRAME_HEIGHT} | Skip Interval: {PROCESS_FRAME_INTERVAL}")
    print(f"   GPU Growth: Enabled | Batch Size: {MAX_BATCH_SIZE}\n")

    # Dictionary to track active sessions
    # Format: student_id : {'start': timestamp, 'last_seen': timestamp, 'name': string, 'bbox': (x,y,w,h)}
    active_sessions = {}

    CAMERA_URL = "rtsp://admin:YCSNFJ@192.168.0.100:554/Streaming/Channels/101"
    stream = CameraStream(CAMERA_URL).start()
    print("Camera Stream started (Threaded). Press 'q' to quit.")
    
    frame_count = 0
    draw_cache = []
    memory_cleanup_counter = 0

    while True:
        ret, frame = stream.read()
        if not ret or frame is None:
            continue
            
        frame_count += 1
        current_time = time.time()
        memory_cleanup_counter += 1
        
        # Periodic memory cleanup (every 500 frames)
        if memory_cleanup_counter % 500 == 0:
            if USE_GPU:
                import tensorflow as tf
                tf.keras.backend.clear_session()  # Clear GPU memory

        
        # Only run heavy DeepFace detection every nth frame
        if frame_count % PROCESS_FRAME_INTERVAL == 0:
            draw_cache = []  # Clear old drawing boxes
            
            # Resize frame for faster processing
            h, w = frame.shape[:2]
            scale = FRAME_WIDTH / w
            small_frame = cv2.resize(frame, (FRAME_WIDTH, int(h * scale)))
            
            # Try different backends in order of performance
            extracted_faces = []
            backends_to_try = ['retinaface', 'mediapipe', 'opencv']  # Optimized order
            
            for backend in backends_to_try:
                try:
                    extracted_faces = DeepFace.represent(
                        img_path=small_frame,  # Use resized frame
                        model_name=MODEL_NAME,
                        enforce_detection=True,
                        detector_backend=backend
                    )
                    if len(extracted_faces) > 0:
                        break # Success!
                except Exception:
                    continue
            
            # Limit batch size for memory efficiency
            if len(extracted_faces) > MAX_BATCH_SIZE:
                extracted_faces = extracted_faces[:MAX_BATCH_SIZE]
                print(f"Limited detections to {MAX_BATCH_SIZE} faces (memory optimization)")
            
            try:
                for face_obj in extracted_faces:
                    face_embedding = face_obj['embedding']
                    facial_area = face_obj['facial_area']
                    # Scale bbox back to original frame size
                    inv = 1.0 / scale
                    x = int(facial_area['x'] * inv)
                    y = int(facial_area['y'] * inv)
                    w = int(facial_area['w'] * inv)
                    h = int(facial_area['h'] * inv)
                    
                    # Find closest match from database
                    best_match = None
                    min_distance = float('inf')
                    
                    for person in enrolled_faces:
                        dist = find_cosine_distance(person['embedding'], face_embedding)
                        if dist < min_distance:
                            min_distance = dist
                            best_match = person
                    
                    if min_distance < DISTANCE_THRESHOLD and best_match is not None:
                        # Match Found!
                        s_id = best_match['student_id']
                        s_name = best_match['name']
                        
                        # Session tracking logic
                        if s_id not in active_sessions:
                            print(f"{s_name} ({s_id}) arrived.")
                            active_sessions[s_id] = {
                                'start': current_time,
                                'last_seen': current_time,
                                'name': s_name,
                            }
                        else:
                            active_sessions[s_id]['last_seen'] = current_time
                            
                        # Save to draw cache for smoother UI
                        session_duration = current_time - active_sessions[s_id]['start']
                        draw_cache.append((x, y, w, h, s_name, session_duration, min_distance))
                        
                    else:
                        # Unknown face
                        draw_cache.append((x, y, w, h, "Unknown", 0, min_distance))

            except ValueError:
                # DeepFace throws ValueError if no face is detected in the frame. We just ignore it.
                pass
            except Exception as e:
                print(f"Error processing frame: {e}")

        # Draw bounding boxes from cache
        for bbox in draw_cache:
            x, y, w, h, s_name, session_duration, min_distance = bbox
            color = (0, 255, 0) if s_name != "Unknown" else (0, 0, 255)
            
            # Box
            cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
            
            # Name and distance
            text = f"{s_name} ({min_distance:.2f})"
            cv2.putText(frame, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            # Time spent (if known)
            if s_name != "Unknown":
                mins = int(session_duration // 60)
                secs = int(session_duration % 60)
                time_text = f"{mins}m {secs}s"
                cv2.putText(frame, time_text, (x, y + h + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

        # Timeout Logic: Check if anyone has left for more than 5 minutes
        students_to_remove = []
        for s_id, data in active_sessions.items():
            if current_time - data['last_seen'] > TIMEOUT_SECONDS:
                # Calculate valid duration (time between first seen and last seen)
                duration = data['last_seen'] - data['start']
                log_duration(conn, s_id, duration)
                print(f"{data['name']} ({s_id}) left. Logged session of {int(duration)} seconds.")
                students_to_remove.append(s_id)
                
        # Remove ended sessions
        for s_id in students_to_remove:
            del active_sessions[s_id]

        cv2.imshow("Face Attendance Tracker", frame)
        
        # Quit on 'q' — waitKey(1) keeps UI responsive
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("Quitting tracker...")
            break

    # Once loop is exited, save all lingering active sessions
    for s_id, data in active_sessions.items():
        duration = data['last_seen'] - data['start']
        log_duration(conn, s_id, duration)
        print(f"Final save: {data['name']} ({s_id}) session of {int(duration)} seconds saved.")

    stream.stop()
    cv2.destroyAllWindows()
    conn.close()

if __name__ == "__main__":
    run_tracking()
