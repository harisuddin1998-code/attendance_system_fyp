import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp" # Force UDP for Zero Lag

import cv2
import sqlite3
import numpy as np
import base64
import time
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, Response, jsonify
from deepface import DeepFace
import threading

# Global storage for camera streams to prevent lag
camera_streams = {}

class CameraStream:
    def __init__(self, url):
        # Optimized capture for RTSP or Webcams
        if isinstance(url, int) or (isinstance(url, str) and url.isdigit()):
            self.cap = cv2.VideoCapture(int(url))
        else:
            self.cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.status, self.frame = False, None
        self.stopped = False
        self.lock = threading.Lock()

    def start(self):
        t = threading.Thread(target=self.update, args=(), daemon=True)
        t.start()
        return self

    def update(self):
        while not self.stopped:
            # Grab frame as fast as possible to keep buffer empty
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
            if self.frame is None: return False, None
            return self.status, self.frame.copy()

    def stop(self):
        self.stopped = True
        self.cap.release()

app = Flask(__name__)

# --- CONFIGURATION ---
DB_PATH = "attendance.db"
MODEL_NAME = "Facenet512"       # Faster than VGG-Face, similar accuracy
TIMEOUT_SECONDS = 10           # 10 second baad banda UI se remove ho jayega
PROCESS_FRAME_INTERVAL = 120   # Har 120 frames pe detection (CPU load kam)
FRAME_WIDTH = 640              # 640p enough for recognition, saves CPU

# Global state to hold tracking data per session
active_sessions = {}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column_exists(cursor, table_name, column_name, column_def):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    if column_name not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")


def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Students table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            embedding BLOB NOT NULL
        )
    ''')
    
    # Cameras table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cameras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,  -- 'tracking' or 'attendance'
            location TEXT NOT NULL,
            url TEXT,
            camera_source TEXT DEFAULT "0",
            status TEXT DEFAULT 'inactive',
            classroom_id INTEGER REFERENCES classrooms(id),
            position TEXT
        )
    ''')
    
    # Classrooms table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS classrooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    ''')
    
    # Subjects table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')
    
    # Teachers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            embedding BLOB
        )
    ''')
    
    # Student-Subject mapping for course enrollment
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_subjects (
            student_id TEXT NOT NULL,
            subject_id INTEGER NOT NULL,
            PRIMARY KEY (student_id, subject_id),
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )
    ''')
    
    # Class sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS class_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            classroom_id INTEGER,
            camera_id INTEGER,
            subject_id INTEGER,
            teacher_id INTEGER,
            start_time TEXT,
            end_time TEXT,
            status TEXT DEFAULT 'Ongoing',
            FOREIGN KEY (classroom_id) REFERENCES classrooms (id),
            FOREIGN KEY (camera_id) REFERENCES cameras (id),
            FOREIGN KEY (subject_id) REFERENCES subjects(id),
            FOREIGN KEY (teacher_id) REFERENCES teachers(id)
        )
    ''')
    
    # Attendance logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            student_id TEXT,
            first_seen TEXT,
            last_seen TEXT,
            total_duration_seconds INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY (session_id) REFERENCES class_sessions (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
    ''')
    
    # Teacher attendance logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teacher_attendance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            teacher_id INTEGER,
            first_seen TEXT,
            last_seen TEXT,
            total_duration_seconds INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY (session_id) REFERENCES class_sessions (id),
            FOREIGN KEY (teacher_id) REFERENCES teachers (id)
        )
    ''')
    
    # Ensure class_sessions has the new subject and teacher fields for existing DBs
    ensure_column_exists(cursor, 'class_sessions', 'subject_id', 'INTEGER REFERENCES subjects(id)')
    ensure_column_exists(cursor, 'class_sessions', 'teacher_id', 'INTEGER REFERENCES teachers(id)')
    
    # Ensure student_subjects exists even for older DBs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_subjects (
            student_id TEXT NOT NULL,
            subject_id INTEGER NOT NULL,
            PRIMARY KEY (student_id, subject_id),
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )
    ''')
    
    # Insert default cameras if not exist
    cursor.execute("SELECT COUNT(*) FROM cameras")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO cameras (name, type, location, url) VALUES (?, ?, ?, ?)", 
                      ("Mobile Camera 1", "tracking", "Classroom", "http://192.168.1.100:4747/video"))
        cursor.execute("INSERT INTO cameras (name, type, location, url) VALUES (?, ?, ?, ?)", 
                      ("Mobile Camera 2", "attendance", "Gate", "http://192.168.1.101:4747/video"))
    else:
        cursor.execute("UPDATE cameras SET url = 'http://192.168.1.100:4747/video' WHERE name = 'Classroom CCTV' AND (url IS NULL OR url = '')")
        cursor.execute("UPDATE cameras SET url = 'http://192.168.1.101:4747/video' WHERE name = 'Gate HD Camera' AND (url IS NULL OR url = '')")
    
    # Insert default classrooms if not exist
    cursor.execute("SELECT COUNT(*) FROM classrooms")
    if cursor.fetchone()[0] == 0:
        for i in range(1, 6):
            cursor.execute("INSERT INTO classrooms (name) VALUES (?)", (f"Classroom {i}",))
    
    # Insert default subjects and teachers if none exist
    cursor.execute("SELECT COUNT(*) FROM subjects")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO subjects (name) VALUES (?)", [("Mathematics",), ("Physics",), ("Computer Science",)])
    cursor.execute("SELECT COUNT(*) FROM teachers")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO teachers (name) VALUES (?)", [("Prof. Ahmed",), ("Ms. Fatima",), ("Mr. Bilal",)])
    
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

def find_cosine_distance(source_rep, test_rep):
    a = np.matmul(np.transpose(source_rep), test_rep)
    b = np.sum(np.multiply(source_rep, source_rep))
    c = np.sum(np.multiply(test_rep, test_rep))
    return 1 - (a / (np.sqrt(b) * np.sqrt(c)))

def load_enrolled_faces():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT student_id, name, embedding FROM students")
    rows = cursor.fetchall()
    conn.close()
    
    enrolled = []
    for row in rows:
        embedding_blob = row['embedding']
        embedding_arr = np.frombuffer(embedding_blob, dtype='float32')
        enrolled.append({
            'student_id': row['student_id'],
            'name': row['name'],
            'embedding': embedding_arr
        })
    return enrolled

def load_enrolled_teachers():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, embedding FROM teachers WHERE embedding IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()
    
    enrolled = []
    for row in rows:
        embedding_blob = row['embedding']
        embedding_arr = np.frombuffer(embedding_blob, dtype='float32')
        enrolled.append({
            'teacher_id': row['id'],
            'name': row['name'],
            'embedding': embedding_arr
        })
    return enrolled

enrolled_faces = load_enrolled_faces()
enrolled_teachers = load_enrolled_teachers()

# Helper functions for multi-camera live sessions
def initialize_session_state(session_id):
    if session_id not in active_sessions:
        active_sessions[session_id] = {
            'students': {},
            'counts': {
                'yolo_face_count': 0,
                'tracking_count': 0,
                'camera_counts': {}
            }
        }


def get_camera_info(camera_id):
    conn = get_db()
    camera = conn.execute("SELECT * FROM cameras WHERE id=?", (camera_id,)).fetchone()
    conn.close()
    return camera




def detect_faces_fast(frame):
    # Sirf opencv use karo — fastest backend, loop ki zaroorat nahi
    try:
        faces = DeepFace.extract_faces(img_path=frame, enforce_detection=False, detector_backend='opencv')
        return faces
    except Exception:
        return []


# Background detection state
last_faces = []
is_detecting = False

def background_detection(frame, full_frame_copy=None, session_data=None, w_orig=None):
    global last_faces, is_detecting
    is_detecting = True
    
    # Using Raw Frame (No enhancement, no resize)
    print("[DEBUG] Detection started...")
    faces = detect_faces_fast(frame)
    
    if full_frame_copy is not None and session_data is not None and w_orig is not None:
        for face in faces:
            face['recognized_name'] = 'Detecting...'
            face['color'] = (255, 255, 0) # Cyan
            face['student_id'] = None
            
            facial_area = face['facial_area']
            scale_back = w_orig / FRAME_WIDTH
            fx, fy, fw, fh = [int(v * scale_back) for v in [facial_area['x'], facial_area['y'], facial_area['w'], facial_area['h']]]
            
            face_img = full_frame_copy[fy:fy+fh, fx:fx+fw]
            if face_img.size == 0: continue
            
            try:
                rep = DeepFace.represent(img_path=face_img, model_name=MODEL_NAME, enforce_detection=False, detector_backend='skip')
                embedding_arr = np.array(rep[0]['embedding'])
                
                best_match = None
                best_distance = float('inf')
                is_teacher = False
                
                for enrolled in enrolled_faces:
                    distance = find_cosine_distance(embedding_arr, enrolled['embedding'])
                    if distance < 0.55 and distance < best_distance:
                        best_match = enrolled
                        best_distance = distance
                        is_teacher = False
                
                if best_match is None:
                    for enrolled in enrolled_teachers:
                        distance = find_cosine_distance(embedding_arr, enrolled['embedding'])
                        if distance < 0.55 and distance < best_distance:
                            best_match = enrolled
                            best_distance = distance
                            is_teacher = True

                current_time = datetime.now()
                if best_match:
                    if is_teacher:
                        teacher_id = best_match['teacher_id']
                        name = best_match['name']
                        teacher_key = f"teacher_{teacher_id}"
                        if teacher_key not in session_data:
                            ret_enc, buf_enc = cv2.imencode('.jpg', face_img)
                            face_b64 = "data:image/jpeg;base64," + base64.b64encode(buf_enc).decode('utf-8') if ret_enc else ""
                            session_data[teacher_key] = {
                                'name': name,
                                'type': 'teacher',
                                'first_seen': current_time,
                                'last_seen': current_time,
                                'total_duration': 0,
                                'face_image': face_b64
                            }
                        session_data[teacher_key]['last_seen'] = current_time
                        session_data[teacher_key]['total_duration'] = (current_time - session_data[teacher_key]['first_seen']).total_seconds()
                        face['recognized_name'] = name + " (Teacher)"
                        face['color'] = (255, 165, 0)
                        face['student_id'] = f"T{teacher_id}"
                    else:
                        student_id = best_match['student_id']
                        name = best_match['name']
                        if student_id not in session_data:
                            ret_enc, buf_enc = cv2.imencode('.jpg', face_img)
                            face_b64 = "data:image/jpeg;base64," + base64.b64encode(buf_enc).decode('utf-8') if ret_enc else ""
                            session_data[student_id] = {
                                'name': name,
                                'type': 'student',
                                'first_seen': current_time,
                                'last_seen': current_time,
                                'total_duration': 0,
                                'face_image': face_b64
                            }
                        session_data[student_id]['last_seen'] = current_time
                        session_data[student_id]['total_duration'] = (current_time - session_data[student_id]['first_seen']).total_seconds()
                        face['recognized_name'] = name
                        face['color'] = (0, 255, 0)
                        face['student_id'] = student_id
                else:
                    face['recognized_name'] = 'UNKNOWN'
                    face['color'] = (0, 0, 255)
            except Exception as e:
                pass

    last_faces = faces
    print(f"[DEBUG] Detection finished. Found {len(last_faces)} faces.")
    is_detecting = False

# Generate Camera Frames for Flask Video Stream
def generate_frames(session_id, camera_id):
    global last_faces, is_detecting
    import urllib.request
    import numpy as np

    # Get session and camera info
    conn = get_db()
    session_info = conn.execute(
        "SELECT cs.*, cl.name as classroom_name FROM class_sessions cs JOIN classrooms cl ON cs.classroom_id = cl.id WHERE cs.id=?",
        (session_id,)
    ).fetchone()
    camera = conn.execute("SELECT * FROM cameras WHERE id=?", (camera_id,)).fetchone()
    conn.close()

    if not session_info or not camera:
        print(f"No session or camera info found for session {session_id}, camera {camera_id}")
        return

    if camera['classroom_id'] != session_info['classroom_id']:
        print(f"Camera {camera_id} does not belong to session {session_id} classroom")
        return

    camera_type = 'attendance' # Changed from camera['type'] to globally force Face Recognition
    camera_url = camera['url']
    camera_name = camera['name']
    camera_position = camera['position'] or 'unknown'

    print(f"Session {session_id}, Camera {camera_id}: type={camera_type}, position={camera_position}, url={camera_url}")

    if not camera_url:
        print(f"No camera URL for camera {camera_id}")
        return

    try:
        global camera_streams
        if camera_id not in camera_streams or not camera_streams[camera_id].status:
            camera_streams[camera_id] = CameraStream(camera_url).start()
        
        stream = camera_streams[camera_id]
        print(f"Using threaded stream for session {session_id}, camera {camera_id}")

        frame_count = 0
        tracker = None
        if camera_type == 'tracking':
            try:
                tracker = DeepSort(max_age=30, n_init=3, nms_max_overlap=1.0, max_cosine_distance=0.3, nn_budget=100)
                print(f"DeepSORT tracker initialized for session {session_id}, camera {camera_id}")
            except Exception as e:
                print(f"Failed to initialize DeepSORT: {e}")
                tracker = None

        initialize_session_state(session_id)
        session_state = active_sessions[session_id]
        session_data = session_state['students']
        counts = session_state['counts']

        while not stream.stopped:
            ret, full_frame = stream.read()
            if not ret or full_frame is None:
                time.sleep(0.01)
                continue

            frame_count += 1
            # Dual Resolution: Use 640px for streaming (Zero Lag)
            frame = cv2.resize(full_frame, (640, int(full_frame.shape[0] * (640 / full_frame.shape[1]))))
            
            # 960p is the sweet spot for distance vs speed
            h, w = full_frame.shape[:2]
            proc_frame = cv2.resize(full_frame, (FRAME_WIDTH, int(h * (FRAME_WIDTH / w))))
            
            header_text = f"Live 960p | {datetime.now().strftime('%H:%M:%S')}"
            cv2.putText(frame, header_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            # Start detection in background if not already running
            if frame_count % PROCESS_FRAME_INTERVAL == 0 and not is_detecting:
                threading.Thread(target=background_detection, args=(proc_frame.copy(), full_frame.copy(), session_data, w), daemon=True).start()

            # Use last known faces to update counts and recognized students
            faces = last_faces
            counts['camera_counts'][camera_id] = len(faces)
            counts['yolo_face_count'] = sum(counts['camera_counts'].values())

            if camera_type == 'attendance':
                scale_draw = 640 / FRAME_WIDTH
                for face in faces:
                    facial_area = face['facial_area']
                    dx, dy, dw, dh = [int(v * scale_draw) for v in [facial_area['x'], facial_area['y'], facial_area['w'], facial_area['h']]]
                    
                    name = face.get('recognized_name', 'Detecting...')
                    color = face.get('color', (0, 255, 255))
                    student_id = face.get('student_id')
                    
                    cv2.rectangle(frame, (dx, dy), (dx + dw, dy + dh), color, 2)
                    timestamp_str = datetime.now().strftime('%H:%M:%S')
                    cv2.putText(frame, name, (dx, dy - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                    cv2.putText(frame, timestamp_str, (dx, dy - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                    if student_id:
                        cv2.putText(frame, f"ID: {student_id}", (dx, dy + dh + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            elif camera_type == 'tracking':
                if frame_count % PROCESS_FRAME_INTERVAL == 0 and tracker:
                    try:
                        face_detections = detect_faces_yolo(frame)
                        detections = []
                        for face in face_detections:
                            facial_area = face['facial_area']
                            x, y, w, h = facial_area['x'], facial_area['y'], facial_area['w'], facial_area['h']
                            detections.append([x, y, x + w, y + h, 0.9])

                        tracks = tracker.update_tracks(detections, frame=frame)
                        track_count = 0
                        for track in tracks:
                            if not track.is_confirmed():
                                continue
                            track_count += 1
                            track_id = track.track_id
                            bbox = track.to_tlbr()
                            x1, y1, x2, y2 = map(int, bbox)
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            cv2.putText(frame, f"Track ID: {track_id}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                            track_key = f"track_{track_id}"
                            if track_key not in session_data:
                                session_data[track_key] = {
                                    'name': f'Track {track_id}',
                                    'first_seen': datetime.now(),
                                    'last_seen': datetime.now(),
                                    'total_duration': 0
                                }
                            session_data[track_key]['last_seen'] = datetime.now()
                            session_data[track_key]['total_duration'] = (datetime.now() - session_data[track_key]['first_seen']).total_seconds()
                        counts['tracking_count'] = track_count
                    except Exception as e:
                        print(f"Tracking error: {e}")
                        pass

            recognized_count = len([sid for sid in session_data if not str(sid).startswith('track_')])
            cv2.putText(frame, f"Recognized: {recognized_count}", (10, frame.shape[0] - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"YOLO Faces: {counts.get('yolo_face_count', 0)}", (10, frame.shape[0] - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"Tracking: {counts.get('tracking_count', 0)}", (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # Lower quality encoding (30%) for lag-free streaming
            ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 30])
            if not ret:
                continue
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            # 30fps cap to prevent overwhelming the browser
            time.sleep(0.033)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error in generate_frames for session {session_id}, camera {camera_id}: {e}")
        return
@app.route('/')
def index():
    conn = get_db()
    total_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    sessions = conn.execute(
        "SELECT cs.*, c.name as camera_name, cl.name as classroom_name, sub.name as subject_name, t.name as teacher_name "
        "FROM class_sessions cs "
        "LEFT JOIN cameras c ON cs.camera_id = c.id "
        "LEFT JOIN classrooms cl ON cs.classroom_id = cl.id "
        "LEFT JOIN subjects sub ON cs.subject_id = sub.id "
        "LEFT JOIN teachers t ON cs.teacher_id = t.id "
        "ORDER BY cs.id DESC LIMIT 10"
    ).fetchall()
    cameras = conn.execute("SELECT * FROM cameras").fetchall()
    classrooms = conn.execute("SELECT * FROM classrooms").fetchall()
    subjects = conn.execute("SELECT * FROM subjects ORDER BY name").fetchall()
    teachers = conn.execute("SELECT * FROM teachers ORDER BY name").fetchall()
    conn.close()
    return render_template('dashboard.html', total_students=total_students, sessions=sessions, cameras=cameras, classrooms=classrooms, subjects=subjects, teachers=teachers)

@app.route('/start_session', methods=['POST'])
def start_session():
    camera_id = request.form.get('camera_id')
    classroom_id = request.form.get('classroom_id')
    subject_id = request.form.get('subject_id')
    teacher_id = request.form.get('teacher_id')
    
    if not camera_id or not classroom_id:
        return "Camera and Classroom must be selected", 400
    
    conn = get_db()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO class_sessions (classroom_id, camera_id, subject_id, teacher_id, start_time, status) VALUES (?, ?, ?, ?, ?, 'Ongoing')",
        (classroom_id, camera_id, subject_id if subject_id else None, teacher_id if teacher_id else None, now_str)
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return redirect(url_for('live_class', session_id=session_id))

@app.route('/start-gate', methods=['POST'])
def start_gate_session():
    """Start a gate detection session using the door camera of selected class"""
    classroom_id = request.form.get('classroom_id')
    
    if not classroom_id:
        return "Classroom must be selected", 400
    
    conn = get_db()
    
    # Find the door camera for this classroom
    camera_row = conn.execute("SELECT id FROM cameras WHERE classroom_id=? AND position='door' AND status='active'", 
                             (classroom_id,)).fetchone()
    
    if not camera_row:
        conn.close()
        return f"No active door camera found for classroom {classroom_id}", 400
    
    camera_id = camera_row['id']
    
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO class_sessions (classroom_id, camera_id, start_time, status) VALUES (?, ?, ?, 'Ongoing')", 
                   (classroom_id, camera_id, now_str))
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return redirect(url_for('live_class', session_id=session_id))

@app.route('/start-class', methods=['POST'])
def start_class_session():
    """Start a class tracking session using CCTV camera of selected class"""
    classroom_id = request.form.get('classroom_id')
    subject_id = request.form.get('subject_id')
    teacher_id = request.form.get('teacher_id')
    
    if not classroom_id:
        return "Classroom must be selected", 400
    
    conn = get_db()
    
    camera_row = conn.execute("SELECT id FROM cameras WHERE classroom_id=? AND position LIKE 'cctv%' AND status='active' ORDER BY position LIMIT 1", 
                             (classroom_id,)).fetchone()
    
    if not camera_row:
        conn.close()
        return f"No active CCTV camera found for classroom {classroom_id}", 400
    
    camera_id = camera_row['id']
    
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO class_sessions (classroom_id, camera_id, subject_id, teacher_id, start_time, status) VALUES (?, ?, ?, ?, ?, 'Ongoing')",
        (classroom_id, camera_id, subject_id if subject_id else None, teacher_id if teacher_id else None, now_str)
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return redirect(url_for('live_class', session_id=session_id))

@app.route('/live_class/<int:session_id>')
def live_class(session_id):
    conn = get_db()
    sess = conn.execute(
        "SELECT cs.*, cl.name as classroom_name, sub.name as subject_name, t.name as teacher_name "
        "FROM class_sessions cs "
        "JOIN classrooms cl ON cs.classroom_id = cl.id "
        "LEFT JOIN subjects sub ON cs.subject_id = sub.id "
        "LEFT JOIN teachers t ON cs.teacher_id = t.id "
        "WHERE cs.id=?",
        (session_id,)
    ).fetchone()
    if not sess or sess['status'] != 'Ongoing':
        conn.close()
        return redirect(url_for('report', session_id=session_id))

    cameras = conn.execute(
        "SELECT * FROM cameras WHERE classroom_id=? ORDER BY CASE position WHEN 'door' THEN 1 WHEN 'cctv1' THEN 2 WHEN 'cctv2' THEN 3 ELSE 4 END",
        (sess['classroom_id'],)
    ).fetchall()
    conn.close()
    return render_template('live.html', session_id=session_id, cameras=cameras, classroom_name=sess['classroom_name'], subject_name=sess['subject_name'], teacher_name=sess['teacher_name'])

@app.route('/video_feed/<int:session_id>')
def video_feed(session_id):
    conn = get_db()
    row = conn.execute("SELECT c.id FROM class_sessions cs JOIN cameras c ON cs.camera_id=c.id WHERE cs.id=?", (session_id,)).fetchone()
    conn.close()
    if not row:
        return "Camera not found", 404
    return Response(generate_frames(session_id, row['id']), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed/<int:session_id>/<int:camera_id>')
def video_feed_camera(session_id, camera_id):
    return Response(generate_frames(session_id, camera_id), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/live_status/<int:session_id>')
def live_status(session_id):
    if session_id in active_sessions:
        session_state = active_sessions[session_id]
        students = []
        current_time = datetime.now()
        to_remove = []
        
        for sid, info in session_state['students'].items():
            # Check if student is still in camera (10 sec timeout)
            if (current_time - info['last_seen']).total_seconds() > TIMEOUT_SECONDS:
                to_remove.append(sid)
                continue
                
            students.append({
                'student_id': sid,
                'name': info['name'],
                'first_seen': info['first_seen'].strftime("%H:%M:%S"),
                'last_seen': info['last_seen'].strftime("%H:%M:%S"),
                'total_duration': int(info['total_duration']),
                'face_image': info.get('face_image', '')
            })
        
        # Cleanup inactive students from memory
        for sid in to_remove:
            del session_state['students'][sid]
            
        counts = session_state['counts']
        unique_students = len([sid for sid in session_state['students'] if not str(sid).startswith('track_')])
        return jsonify({
            'students': students,
            'recognized_students': unique_students,
            'yolo_face_count': counts.get('yolo_face_count', 0),
            'tracking_count': counts.get('tracking_count', 0),
            'camera_counts': counts.get('camera_counts', {})
        })
    
    return jsonify({
        'students': [],
        'recognized_students': 0,
        'yolo_face_count': 0,
        'tracking_count': 0,
        'camera_counts': {}
    })

@app.route('/end_session/<int:session_id>', methods=['POST'])
def end_session(session_id):
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Update session end time
    now_dt = datetime.now()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE class_sessions SET end_time=?, status='Ended' WHERE id=?", (now_str, session_id))
    
    # Get session start time to calculate 25m boundary
    sess = cursor.execute("SELECT start_time FROM class_sessions WHERE id=?", (session_id,)).fetchone()
    try:
        start_dt = datetime.strptime(sess['start_time'], "%Y-%m-%d %H:%M:%S")
    except:
        start_dt = now_dt
        
    start_time_limit = start_dt.timestamp() + (25 * 60) # 25 minutes after start
    
    # 2. Iterate memory state and finalize to DB
    if session_id in active_sessions:
        for sid, info in active_sessions[session_id]['students'].items():
            # Skip tracking entries (they start with 'track_')
            if str(sid).startswith('track_'):
                continue
                
            # Check if this is a teacher entry
            if str(sid).startswith('teacher_'):
                teacher_id = int(str(sid).replace('teacher_', ''))
                cursor.execute('''
                    INSERT INTO teacher_attendance_logs (session_id, teacher_id, first_seen, last_seen, total_duration_seconds, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (session_id, teacher_id, info['first_seen'].strftime("%H:%M:%S"), info['last_seen'].strftime("%H:%M:%S"), int(info['total_duration']), "Present"))
            else:
                # Student attendance
                first_seen_ts = info['first_seen'].timestamp()
                last_seen_ts = info['last_seen'].timestamp()
                duration = int(info['total_duration'])
                
                if first_seen_ts > start_time_limit:
                    final_status = "Late"
                elif (now_dt.timestamp() - last_seen_ts) > TIMEOUT_SECONDS:
                    final_status = "Early Leave"
                else:
                    final_status = "Present"
                    
                cursor.execute('''
                    INSERT INTO attendance_logs (session_id, student_id, first_seen, last_seen, total_duration_seconds, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (session_id, sid, info['first_seen'].strftime("%H:%M:%S"), info['last_seen'].strftime("%H:%M:%S"), duration, final_status))
            
        del active_sessions[session_id]
        
    conn.commit()
    conn.close()
    return redirect(url_for('report', session_id=session_id))

@app.route('/report/<int:session_id>')
def report(session_id):
    conn = get_db()
    session = conn.execute("SELECT * FROM class_sessions WHERE id=?", (session_id,)).fetchone()
    student_logs = conn.execute('''
        SELECT a.*, COALESCE(s.name, a.student_id) as name, 'student' as type
        FROM attendance_logs a 
        LEFT JOIN students s ON a.student_id = s.student_id 
        WHERE a.session_id=?
    ''', (session_id,)).fetchall()
    
    teacher_logs = conn.execute('''
        SELECT a.*, COALESCE(t.name, 'Teacher ' || a.teacher_id) as name, 'teacher' as type
        FROM teacher_attendance_logs a 
        LEFT JOIN teachers t ON a.teacher_id = t.id 
        WHERE a.session_id=?
    ''', (session_id,)).fetchall()
    
    # Combine and sort logs
    all_logs = list(student_logs) + list(teacher_logs)
    conn.close()
    return render_template('report.html', session=session, logs=all_logs)

@app.route('/teacher')
def teacher_dashboard():
    conn = get_db()
    sessions = conn.execute(
        "SELECT cs.*, c.name as camera_name, cl.name as classroom_name, sub.name as subject_name, t.name as teacher_name "
        "FROM class_sessions cs "
        "LEFT JOIN cameras c ON cs.camera_id = c.id "
        "LEFT JOIN classrooms cl ON cs.classroom_id = cl.id "
        "LEFT JOIN subjects sub ON cs.subject_id = sub.id "
        "LEFT JOIN teachers t ON cs.teacher_id = t.id "
        "WHERE cs.status='Ongoing'"
    ).fetchall()
    conn.close()
    return render_template('teacher_dashboard.html', sessions=sessions)

@app.route('/students')
def manage_students():
    conn = get_db()
    students = conn.execute(
        "SELECT s.student_id, s.name, GROUP_CONCAT(sub.name, ', ') as courses "
        "FROM students s "
        "LEFT JOIN student_subjects ss ON s.student_id = ss.student_id "
        "LEFT JOIN subjects sub ON ss.subject_id = sub.id "
        "GROUP BY s.student_id, s.name"
    ).fetchall()
    subjects = conn.execute("SELECT * FROM subjects ORDER BY name").fetchall()
    conn.close()
    return render_template('students.html', students=students, subjects=subjects)

@app.route('/delete_student/<student_id>', methods=['POST'])
def delete_student(student_id):
    global enrolled_faces
    conn = get_db()
    conn.execute("DELETE FROM student_subjects WHERE student_id=?", (student_id,))
    conn.execute("DELETE FROM students WHERE student_id=?", (student_id,))
    conn.commit()
    conn.close()
    enrolled_faces = load_enrolled_faces() # refresh cache
    return redirect(url_for('manage_students'))

LATEST_ENROLL_FRAME = None

def generate_enroll_frames():
    global LATEST_ENROLL_FRAME
    camera_url = 0  # 0 represents the default laptop webcam
    
    # Use the optimized CameraStream class to prevent buffer lag
    stream = CameraStream(camera_url).start()
    
    try:
        while not stream.stopped:
            ret, frame = stream.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue
                
            LATEST_ENROLL_FRAME = frame.copy()
            
            # Use 30 quality for smoother lag-free streaming
            ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 30])
            if not ret:
                continue
                
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            # Small sleep to yield CPU
            time.sleep(0.01)
    finally:
        stream.stop()

@app.route('/enroll_video_feed')
def enroll_video_feed():
    return Response(generate_enroll_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/enroll', methods=['POST'])
def enroll_api():
    global enrolled_faces
    global LATEST_ENROLL_FRAME
    
    data = request.json
    student_id = data.get('student_id')
    name = data.get('name')
    image_b64 = data.get('image')
    subject_ids = data.get('subject_ids', [])
    
    if not student_id or not name:
        return jsonify({"error": "Missing fields"}), 400
        
    try:
        if image_b64:
            img_data = base64.b64decode(image_b64.split(',')[1])
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        else:
            if LATEST_ENROLL_FRAME is None:
                return jsonify({"error": "No camera frame available"}), 400
            img = LATEST_ENROLL_FRAME.copy()
        
        results = DeepFace.represent(img_path=img, model_name=MODEL_NAME, enforce_detection=True)
        embedding = results[0]["embedding"]
        embedding_blob = np.array(embedding, dtype='float32').tobytes()
        
        conn = get_db()
        try:
            conn.execute("INSERT INTO students (student_id, name, embedding) VALUES (?, ?, ?)", 
                         (student_id, name, embedding_blob))
        except sqlite3.IntegrityError:
            conn.execute("UPDATE students SET name=?, embedding=? WHERE student_id=?", 
                         (name, embedding_blob, student_id))
        
        conn.execute("DELETE FROM student_subjects WHERE student_id=?", (student_id,))
        for subject_id in subject_ids:
            conn.execute("INSERT INTO student_subjects (student_id, subject_id) VALUES (?, ?)", (student_id, subject_id))

        conn.commit()
        conn.close()
        
        enrolled_faces = load_enrolled_faces() # refresh memory
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/enroll_teacher', methods=['POST'])
def enroll_teacher_api():
    global enrolled_teachers
    data = request.json
    teacher_id = data.get('teacher_id')
    name = data.get('name')
    image_b64 = data.get('image')
    
    if not teacher_id or not name or not image_b64:
        return jsonify({"error": "Missing fields"}), 400
        
    try:
        img_data = base64.b64decode(image_b64.split(',')[1])
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        results = DeepFace.represent(img_path=img, model_name=MODEL_NAME, enforce_detection=True)
        embedding = results[0]["embedding"]
        embedding_blob = np.array(embedding, dtype='float32').tobytes()
        
        conn = get_db()
        try:
            conn.execute("INSERT INTO teachers (id, name, embedding) VALUES (?, ?, ?)", 
                         (teacher_id, name, embedding_blob))
        except sqlite3.IntegrityError:
            conn.execute("UPDATE teachers SET name=?, embedding=? WHERE id=?", 
                         (name, embedding_blob, teacher_id))
        
        conn.commit()
        conn.close()
        
        enrolled_teachers = load_enrolled_teachers() # refresh memory
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/next_teacher_id')
def next_teacher_id():
    conn = get_db()
    result = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 as next_id FROM teachers").fetchone()
    conn.close()
    return jsonify({"next_id": result['next_id']})

# --- NEW CLASS MANAGEMENT ROUTES ---

# --- NEW CLASS MANAGEMENT ROUTES ---

@app.route('/create_class', methods=['POST'])
def create_class():
    """Create a new class with multiple cameras"""
    class_name = request.form.get('class_name')
    door_camera_ip = request.form.get('door_camera_ip')
    cctv1_ip = request.form.get('cctv1_ip')
    cctv2_ip = request.form.get('cctv2_ip')
    
    if not class_name:
        return "Class name is required", 400
    
    if not door_camera_ip and not cctv1_ip and not cctv2_ip:
        return "At least one camera IP is required", 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Create classroom entry
    cursor.execute("INSERT INTO classrooms (name) VALUES (?)", (class_name,))
    classroom_id = cursor.lastrowid
    
    # Create camera entries
    cameras_created = []
    
    if door_camera_ip:
        cursor.execute("INSERT INTO cameras (name, type, location, url, status, classroom_id, position) VALUES (?, ?, ?, ?, 'active', ?, ?)",
                       (f"{class_name} - Door", "attendance", class_name, f"http://{door_camera_ip}/video", classroom_id, "door"))
        cameras_created.append("Door Camera")
    
    if cctv1_ip:
        cursor.execute("INSERT INTO cameras (name, type, location, url, status, classroom_id, position) VALUES (?, ?, ?, ?, 'active', ?, ?)",
                       (f"{class_name} - CCTV 1", "tracking", class_name, f"http://{cctv1_ip}/video", classroom_id, "cctv1"))
        cameras_created.append("CCTV Camera 1")
    
    if cctv2_ip:
        cursor.execute("INSERT INTO cameras (name, type, location, url, status, classroom_id, position) VALUES (?, ?, ?, ?, 'active', ?, ?)",
                       (f"{class_name} - CCTV 2", "tracking", class_name, f"http://{cctv2_ip}/video", classroom_id, "cctv2"))
        cameras_created.append("CCTV Camera 2")
    
    conn.commit()
    conn.close()
    
    print(f"Created class '{class_name}' with cameras: {', '.join(cameras_created)}")
    return redirect(url_for('index'))

@app.route('/delete_class/<int:classroom_id>', methods=['POST'])
def delete_class(classroom_id):
    """Delete a class and its associated cameras"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get class name for confirmation
    class_row = conn.execute("SELECT name FROM classrooms WHERE id=?", (classroom_id,)).fetchone()
    if not class_row:
        return "Class not found", 404
    
    class_name = class_row['name']
    
    # Delete associated cameras first
    cursor.execute("DELETE FROM cameras WHERE classroom_id=?", (classroom_id,))
    
    # Delete classroom
    cursor.execute("DELETE FROM classrooms WHERE id=?", (classroom_id,))
    
    conn.commit()
    conn.close()
    
    print(f"Deleted class '{class_name}' and all its cameras")
    return redirect(url_for('index'))

@app.route('/subjects', endpoint='manage_subjects')
def manage_subjects():
    conn = get_db()
    subjects = conn.execute("SELECT * FROM subjects ORDER BY name").fetchall()
    conn.close()
    return render_template('subjects.html', subjects=subjects)

@app.route('/create_subject', methods=['POST'])
def create_subject():
    name = request.form.get('subject_name')
    if not name:
        return "Subject name is required", 400
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO subjects (name) VALUES (?)", (name.strip(),))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()
    return redirect(url_for('manage_subjects'))

@app.route('/delete_subject/<int:subject_id>', methods=['POST'])
def delete_subject(subject_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM student_subjects WHERE subject_id=?", (subject_id,))
    cursor.execute("DELETE FROM class_sessions WHERE subject_id=?", (subject_id,))
    cursor.execute("DELETE FROM subjects WHERE id=?", (subject_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('manage_subjects'))

@app.route('/teachers')
def manage_teachers():
    conn = get_db()
    teachers = conn.execute("SELECT * FROM teachers ORDER BY name").fetchall()
    conn.close()
    return render_template('teachers.html', teachers=teachers)

@app.route('/create_teacher', methods=['POST'])
def create_teacher():
    name = request.form.get('teacher_name')
    if not name:
        return "Teacher name is required", 400
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO teachers (name) VALUES (?)", (name.strip(),))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()
    return redirect(url_for('manage_teachers'))

@app.route('/delete_teacher/<int:teacher_id>', methods=['POST'])
def delete_teacher(teacher_id):
    global enrolled_teachers
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE class_sessions SET teacher_id=NULL WHERE teacher_id=?", (teacher_id,))
    cursor.execute("DELETE FROM teachers WHERE id=?", (teacher_id,))
    conn.commit()
    conn.close()
    enrolled_teachers = load_enrolled_teachers() # refresh cache
    return redirect(url_for('manage_teachers'))

@app.route('/api/class_stats')
def class_stats():
    """API endpoint for class statistics"""
    conn = get_db()
    
    total_classes = conn.execute("SELECT COUNT(*) FROM classrooms").fetchone()[0]
    total_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    total_cameras = conn.execute("SELECT COUNT(*) FROM cameras WHERE classroom_id IS NOT NULL").fetchone()[0]
    active_sessions = conn.execute("SELECT COUNT(*) FROM class_sessions WHERE status='Ongoing'").fetchone()[0]
    
    classes = conn.execute("""
        SELECT cl.id, cl.name,
               (SELECT COUNT(*) FROM cameras WHERE classroom_id = cl.id) as camera_count,
               (SELECT GROUP_CONCAT(position || ': ' || REPLACE(url, 'http://', '')) FROM cameras WHERE classroom_id = cl.id) as camera_details,
               COUNT(DISTINCT cs.id) as total_sessions
        FROM classrooms cl
        LEFT JOIN class_sessions cs ON cl.id = cs.classroom_id
        GROUP BY cl.id, cl.name
    """).fetchall()
    
    conn.close()
    
    return jsonify({
        'total_classes': total_classes,
        'total_students': total_students,
        'total_cameras': total_cameras,
        'active_sessions': active_sessions,
        'classes': [dict(cls) for cls in classes]
    })

if __name__ == '__main__':
    # Print all registered routes
    print("\n" + "="*80)
    print("REGISTERED FLASK ROUTES:")
    print("="*80)
    for rule in app.url_map.iter_rules():
        methods = ','.join(sorted(rule.methods - {'OPTIONS', 'HEAD'}))
        print(f"{rule.rule:40} {methods:20} {rule.endpoint}")
    print("="*80 + "\n")
    app.run(host='0.0.0.0', debug=True, port=5000, use_reloader=False, threaded=True)
