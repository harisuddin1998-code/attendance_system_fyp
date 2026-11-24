import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp"  # Force UDP for low-latency RTSP

import re
import cv2
import sqlite3
import numpy as np 
import base64
import time
import threading
from datetime import datetime
from flask import Flask, request, Response, jsonify, send_from_directory
from deepface import DeepFace

# --- PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "attendance.db")
FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")
FACES_DIR = os.path.join(BASE_DIR, "static", "faces")
os.makedirs(FACES_DIR, exist_ok=True)

# --- RECOGNITION CONFIG ---
MODEL_NAME = "Facenet512"         # 512-d embeddings
DETECTOR_BACKEND = "retinaface"   # accurate on small / distant faces; falls back to opencv
MATCH_THRESHOLD = 0.45            # cosine distance below this = same person
MIN_FACE_PX = 15                  # ignore tiny detections
MIN_FACE_CONFIDENCE = 0.90        # ignore low-confidence detections
PROCESS_FRAME_INTERVAL = 30       # start recognition every N streamed frames (~1 s at 30 fps) if idle
STREAM_WIDTH = 960                # width of the MJPEG stream sent to the browser
STREAM_JPEG_QUALITY = 70

# --- ATTENDANCE RULES ---
PRESENT_WINDOW_SECONDS = 10       # "in view now" if seen within this window
LATE_AFTER_MINUTES = 25           # first seen after this many minutes = Late
EARLY_LEAVE_SECONDS = 5 * 60      # last seen this long before the end = Early Leave


class CameraStream:
    """Reads frames on a background thread so the stream never lags behind.

    Supports webcam indexes ("0"), network streams (RTSP / HTTP) and local video
    files. Video files are played at their native frame rate and loop forever,
    so a recorded classroom video behaves like a live camera.
    """

    def __init__(self, url):
        self.url = url
        self.is_file = isinstance(url, str) and os.path.isfile(url)
        if isinstance(url, int) or (isinstance(url, str) and url.isdigit()):
            self.cap = cv2.VideoCapture(int(url))
        elif self.is_file:
            self.cap = cv2.VideoCapture(url)
        else:
            self.cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        fps = self.cap.get(cv2.CAP_PROP_FPS) if self.is_file else 0
        self.frame_delay = 1.0 / fps if fps and fps > 0 else 1.0 / 30
        self.status, self.frame = False, None
        self.stopped = False
        self.lock = threading.Lock()

    def start(self):
        threading.Thread(target=self.update, daemon=True).start()
        return self

    def update(self):
        while not self.stopped:
            if not self.cap.grab():
                if self.is_file:  # loop recorded videos
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                time.sleep(0.1)
                continue
            status, frame = self.cap.retrieve()
            if status:
                with self.lock:
                    self.frame = frame
                self.status = True
            if self.is_file:
                time.sleep(self.frame_delay)

    def read(self):
        with self.lock:
            if self.frame is None:
                return False, None
            return self.status, self.frame.copy()

    def stop(self):
        self.stopped = True
        self.cap.release()


app = Flask(__name__, static_folder="static")

# Global runtime state
camera_streams = {}     # camera_id -> CameraStream
last_faces = {}         # camera_id -> list of face dicts from the latest detection
detecting = {}          # camera_id -> bool, detection thread running
active_sessions = {}    # session_id -> {'people': {...}, 'counts': {...}}
state_lock = threading.RLock()


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

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

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            embedding BLOB NOT NULL
        )
    ''')
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS classrooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            embedding BLOB
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_subjects (
            student_id TEXT NOT NULL,
            subject_id INTEGER NOT NULL,
            PRIMARY KEY (student_id, subject_id),
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )
    ''')
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

    # Migrations for older databases
    ensure_column_exists(cursor, 'class_sessions', 'subject_id', 'INTEGER REFERENCES subjects(id)')
    ensure_column_exists(cursor, 'class_sessions', 'teacher_id', 'INTEGER REFERENCES teachers(id)')
    ensure_column_exists(cursor, 'students', 'photo', 'TEXT')
    ensure_column_exists(cursor, 'teachers', 'photo', 'TEXT')

    # Seed data for a fresh database
    cursor.execute("SELECT COUNT(*) FROM cameras")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO cameras (name, type, location, url) VALUES (?, ?, ?, ?)",
                       ("Mobile Camera 1", "tracking", "Classroom", "http://192.168.1.100:4747/video"))
        cursor.execute("INSERT INTO cameras (name, type, location, url) VALUES (?, ?, ?, ?)",
                       ("Mobile Camera 2", "attendance", "Gate", "http://192.168.1.101:4747/video"))
    cursor.execute("SELECT COUNT(*) FROM classrooms")
    if cursor.fetchone()[0] == 0:
        for i in range(1, 6):
            cursor.execute("INSERT INTO classrooms (name) VALUES (?)", (f"Classroom {i}",))
    cursor.execute("SELECT COUNT(*) FROM subjects")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO subjects (name) VALUES (?)",
                           [("Mathematics",), ("Physics",), ("Computer Science",)])
    cursor.execute("SELECT COUNT(*) FROM teachers")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO teachers (name) VALUES (?)",
                           [("Prof. Ahmed",), ("Ms. Fatima",), ("Mr. Bilal",)])

    conn.commit()
    conn.close()


init_db()


# ---------------------------------------------------------------------------
# Face recognition helpers
# ---------------------------------------------------------------------------

def find_cosine_distance(source_rep, test_rep):
    a = np.matmul(np.transpose(source_rep), test_rep)
    b = np.sum(np.multiply(source_rep, source_rep))
    c = np.sum(np.multiply(test_rep, test_rep))
    return 1 - (a / (np.sqrt(b) * np.sqrt(c)))


def load_enrolled_faces():
    conn = get_db()
    rows = conn.execute("SELECT student_id, name, embedding, photo FROM students").fetchall()
    conn.close()
    return [{
        'student_id': r['student_id'], 'name': r['name'], 'photo': r['photo'],
        'embedding': np.frombuffer(r['embedding'], dtype='float32'),
    } for r in rows]


def load_enrolled_teachers():
    conn = get_db()
    rows = conn.execute("SELECT id, name, embedding, photo FROM teachers WHERE embedding IS NOT NULL").fetchall()
    conn.close()
    return [{
        'teacher_id': r['id'], 'name': r['name'], 'photo': r['photo'],
        'embedding': np.frombuffer(r['embedding'], dtype='float32'),
    } for r in rows]


enrolled_faces = load_enrolled_faces()
enrolled_teachers = load_enrolled_teachers()


_enrolled_db_mtime = os.path.getmtime(DB_PATH)


def reload_enrolled():
    global enrolled_faces, enrolled_teachers, _enrolled_db_mtime
    _enrolled_db_mtime = os.path.getmtime(DB_PATH)
    enrolled_faces = load_enrolled_faces()
    enrolled_teachers = load_enrolled_teachers()


def refresh_enrolled_if_changed():
    """Pick up names/faces changed outside the app (scripts, DB edits) without a restart."""
    try:
        if os.path.getmtime(DB_PATH) != _enrolled_db_mtime:
            reload_enrolled()
    except OSError:
        pass


def detect_faces(frame):
    """Detect faces and return [(x, y, w, h, confidence)] in frame coordinates."""
    fh, fw = frame.shape[:2]
    for backend in (DETECTOR_BACKEND, 'opencv'):
        try:
            faces = DeepFace.extract_faces(img_path=frame, detector_backend=backend,
                                           enforce_detection=False, align=False)
        except Exception as e:
            print(f"[detect] {backend} failed: {e}")
            continue
        boxes = []
        for f in faces:
            a = f['facial_area']
            conf = f.get('confidence') or 0
            if a['w'] < MIN_FACE_PX or a['h'] < MIN_FACE_PX:
                continue
            if a['w'] >= fw - 1 and a['h'] >= fh - 1:  # "no face" placeholder = whole image
                continue
            if backend != 'opencv' and conf < MIN_FACE_CONFIDENCE:
                continue
            boxes.append((a['x'], a['y'], a['w'], a['h'], conf))
        return boxes
    return []


def embed_face(face_img):
    rep = DeepFace.represent(img_path=face_img, model_name=MODEL_NAME,
                             enforce_detection=False, detector_backend='skip')
    return np.array(rep[0]['embedding'], dtype='float32')


def padded_crop(img, box, pad=0.35):
    """Crop a face with some margin around it - nicer for profile photos."""
    x, y, w, h = box[:4]
    ih, iw = img.shape[:2]
    px, py = int(w * pad), int(h * pad)
    return img[max(y - py, 0):min(y + h + py, ih), max(x - px, 0):min(x + w + px, iw)].copy()


def embed_largest_face(img):
    """Detect the largest face in an image; return (embedding, photo_crop)."""
    boxes = detect_faces(img)
    if not boxes:
        raise ValueError("No face detected. Face the camera directly in good light and try again.")
    x, y, w, h, _ = max(boxes, key=lambda b: b[2] * b[3])
    crop = img[max(y, 0):y + h, max(x, 0):x + w]
    return embed_face(crop), padded_crop(img, (x, y, w, h))


def match_identity(embedding):
    """Return (kind, record, distance) for the closest enrolled person, or (None, None, d)."""
    best, best_kind, best_d = None, None, float('inf')
    for person in enrolled_faces:
        d = find_cosine_distance(embedding, person['embedding'])
        if d < best_d:
            best, best_kind, best_d = person, 'student', d
    for person in enrolled_teachers:
        d = find_cosine_distance(embedding, person['embedding'])
        if d < best_d:
            best, best_kind, best_d = person, 'teacher', d
    if best is not None and best_d < MATCH_THRESHOLD:
        return best_kind, best, best_d
    return None, None, best_d


def save_face_photo(prefix, ident, face_img):
    """Save a face thumbnail under static/faces and return its URL path."""
    safe = re.sub(r'[^A-Za-z0-9_-]', '_', str(ident))
    filename = f"{prefix}_{safe}.jpg"
    thumb = face_img
    if thumb.shape[0] < 160:
        scale = 160 / thumb.shape[0]
        thumb = cv2.resize(thumb, (int(thumb.shape[1] * scale), 160), interpolation=cv2.INTER_CUBIC)
    cv2.imwrite(os.path.join(FACES_DIR, filename), thumb)
    return f"/static/faces/{filename}?v={int(time.time())}"


def delete_face_photo(photo_url):
    """Remove a stored face thumbnail (biometric data) from disk."""
    if not photo_url:
        return
    path = os.path.join(FACES_DIR, os.path.basename(photo_url.split('?')[0]))
    if os.path.isfile(path):
        os.remove(path)


def decode_image(image_b64):
    img_data = base64.b64decode(image_b64.split(',')[-1])
    img = cv2.imdecode(np.frombuffer(img_data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not read the image.")
    return img


# ---------------------------------------------------------------------------
# Live sessions
# ---------------------------------------------------------------------------

def initialize_session_state(session_id):
    with state_lock:
        if session_id not in active_sessions:
            active_sessions[session_id] = {
                'people': {},
                'counts': {'faces_in_view': 0, 'camera_counts': {}},
            }
        return active_sessions[session_id]


def background_detection(camera_id, full_frame, session_id):
    """Detect + recognise faces in one frame, update the session's presence data."""
    try:
        refresh_enrolled_if_changed()
        boxes = detect_faces(full_frame)
        results = []
        now = datetime.now()
        state = initialize_session_state(session_id)
        for (x, y, w, h, _conf) in boxes:
            face_img = full_frame[max(y, 0):y + h, max(x, 0):x + w]
            if face_img.size == 0:
                continue
            face = {'box': (x, y, w, h), 'label': 'Unknown', 'kind': 'unknown'}
            try:
                kind, person, _dist = match_identity(embed_face(face_img))
            except Exception as e:
                print(f"[recognise] {e}")
                kind, person = None, None
            if person is not None:
                key = f"teacher_{person['teacher_id']}" if kind == 'teacher' else person['student_id']
                with state_lock:
                    people = state['people']
                    if key not in people:
                        ok, buf = cv2.imencode('.jpg', face_img)
                        people[key] = {
                            'name': person['name'],
                            'type': kind,
                            'photo': person.get('photo'),
                            'first_seen': now,
                            'last_seen': now,
                            'face_image': ("data:image/jpeg;base64," + base64.b64encode(buf).decode()) if ok else "",
                        }
                    people[key]['last_seen'] = now
                    people[key]['name'] = person['name']  # follow renames mid-session
                face['label'] = person['name'] + (" (Teacher)" if kind == 'teacher' else "")
                face['kind'] = kind
            results.append(face)
        last_faces[camera_id] = results
        with state_lock:
            state['counts']['camera_counts'][camera_id] = len(results)
            state['counts']['faces_in_view'] = sum(state['counts']['camera_counts'].values())
    except Exception as e:
        print(f"[detection] camera {camera_id}: {e}")
    finally:
        detecting[camera_id] = False


BOX_COLORS = {  # BGR
    'student': (94, 197, 34),
    'teacher': (11, 158, 245),
    'unknown': (68, 68, 239),
}


def draw_face(frame, face, scale):
    x, y, w, h = [int(v * scale) for v in face['box']]
    color = BOX_COLORS.get(face['kind'], (200, 200, 200))
    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2, cv2.LINE_AA)
    label = face['label']
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    ty = max(y - 8, th + 8)
    cv2.rectangle(frame, (x - 1, ty - th - 7), (x + tw + 9, ty + 3), color, -1)
    cv2.putText(frame, label, (x + 4, ty - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)


def get_stream(camera_id, url):
    stream = camera_streams.get(camera_id)
    if stream is None or stream.stopped or stream.url != url:
        if stream is not None:
            stream.stop()
        stream = CameraStream(url).start()
        camera_streams[camera_id] = stream
    return stream


def generate_frames(session_id, camera_id):
    conn = get_db()
    session_info = conn.execute("SELECT * FROM class_sessions WHERE id=?", (session_id,)).fetchone()
    camera = conn.execute("SELECT * FROM cameras WHERE id=?", (camera_id,)).fetchone()
    conn.close()

    if not session_info or not camera:
        print(f"No session or camera info found for session {session_id}, camera {camera_id}")
        return
    if camera['classroom_id'] != session_info['classroom_id']:
        print(f"Camera {camera_id} does not belong to session {session_id} classroom")
        return
    camera_url = camera['url'] or camera['camera_source']
    if not camera_url:
        print(f"No camera URL for camera {camera_id}")
        return

    stream = get_stream(camera_id, camera_url)
    initialize_session_state(session_id)
    frame_count = 0

    try:
        while not stream.stopped:
            ret, full_frame = stream.read()
            if not ret or full_frame is None:
                time.sleep(0.03)
                continue

            frame_count += 1
            if frame_count % PROCESS_FRAME_INTERVAL == 1 and not detecting.get(camera_id):
                detecting[camera_id] = True
                threading.Thread(target=background_detection,
                                 args=(camera_id, full_frame.copy(), session_id), daemon=True).start()

            h, w = full_frame.shape[:2]
            scale = STREAM_WIDTH / w
            frame = cv2.resize(full_frame, (STREAM_WIDTH, int(h * scale)))
            for face in last_faces.get(camera_id, []):
                draw_face(frame, face, scale)

            ok, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), STREAM_JPEG_QUALITY])
            if not ok:
                continue
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.033)
    except GeneratorExit:
        pass
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error in generate_frames for session {session_id}, camera {camera_id}: {e}")


def classify_attendance(start_dt, end_dt, first_seen, last_seen):
    if (first_seen - start_dt).total_seconds() > LATE_AFTER_MINUTES * 60:
        return "Late"
    if (end_dt - last_seen).total_seconds() > EARLY_LEAVE_SECONDS:
        return "Early Leave"
    return "Present"


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

SESSION_SELECT = '''
    SELECT cs.*, cl.name AS classroom_name, sub.name AS subject_name, t.name AS teacher_name,
           c.name AS camera_name,
           (SELECT COUNT(*) FROM attendance_logs a WHERE a.session_id = cs.id) AS attendees,
           (SELECT COUNT(*) FROM attendance_logs a WHERE a.session_id = cs.id AND a.status = 'Present') AS present_count,
           (SELECT COUNT(*) FROM attendance_logs a WHERE a.session_id = cs.id AND a.status = 'Late') AS late_count,
           (SELECT COUNT(*) FROM attendance_logs a WHERE a.session_id = cs.id AND a.status = 'Early Leave') AS early_count
    FROM class_sessions cs
    LEFT JOIN classrooms cl ON cs.classroom_id = cl.id
    LEFT JOIN subjects sub ON cs.subject_id = sub.id
    LEFT JOIN teachers t ON cs.teacher_id = t.id
    LEFT JOIN cameras c ON cs.camera_id = c.id
'''


def rows(result):
    return [dict(r) for r in result]


def camera_dict(c):
    return {
        'id': c['id'], 'name': c['name'], 'position': c['position'], 'url': c['url'],
        'status': c['status'], 'type': c['type'],
    }


def classrooms_with_cameras(conn):
    classrooms = conn.execute("SELECT * FROM classrooms ORDER BY id").fetchall()
    cams = conn.execute(
        "SELECT * FROM cameras WHERE classroom_id IS NOT NULL ORDER BY "
        "CASE position WHEN 'door' THEN 1 WHEN 'cctv1' THEN 2 WHEN 'cctv2' THEN 3 ELSE 4 END"
    ).fetchall()
    sessions = conn.execute("SELECT classroom_id, COUNT(*) n FROM class_sessions GROUP BY classroom_id").fetchall()
    session_counts = {s['classroom_id']: s['n'] for s in sessions}
    out = []
    for cl in classrooms:
        out.append({
            'id': cl['id'], 'name': cl['name'],
            'cameras': [camera_dict(c) for c in cams if c['classroom_id'] == cl['id']],
            'total_sessions': session_counts.get(cl['id'], 0),
        })
    return out


def resolve_camera_url(value):
    """Accept a webcam index, a full URL, a local video file, or a bare IP[:port]."""
    value = (value or '').strip()
    if not value:
        return None
    if value.isdigit() or '://' in value or os.path.isfile(value):
        return value
    return f"http://{value}/video"


def json_error(message, status=400):
    return jsonify({'error': message}), status


# ---------------------------------------------------------------------------
# API: overview + sessions
# ---------------------------------------------------------------------------

@app.route('/api/overview')
def api_overview():
    conn = get_db()
    q = lambda sql: conn.execute(sql).fetchone()[0]
    stats = {
        'students': q("SELECT COUNT(*) FROM students"),
        'teachers': q("SELECT COUNT(*) FROM teachers"),
        'subjects': q("SELECT COUNT(*) FROM subjects"),
        'classrooms': q("SELECT COUNT(*) FROM classrooms"),
        'cameras': q("SELECT COUNT(*) FROM cameras WHERE classroom_id IS NOT NULL"),
        'live_sessions': q("SELECT COUNT(*) FROM class_sessions WHERE status='Ongoing'"),
        'total_sessions': q("SELECT COUNT(*) FROM class_sessions"),
        'attendance_records': q("SELECT COUNT(*) FROM attendance_logs"),
    }
    status_rows = conn.execute("SELECT status, COUNT(*) n FROM attendance_logs GROUP BY status").fetchall()
    stats['status_breakdown'] = {r['status']: r['n'] for r in status_rows}
    recent = rows(conn.execute(SESSION_SELECT + " ORDER BY cs.id DESC LIMIT 8").fetchall())
    payload = {
        'stats': stats,
        'recent_sessions': recent,
        'classrooms': classrooms_with_cameras(conn),
        'subjects': rows(conn.execute("SELECT * FROM subjects ORDER BY name").fetchall()),
        'teachers': rows(conn.execute("SELECT id, name, photo, embedding IS NOT NULL AS has_face FROM teachers ORDER BY name").fetchall()),
    }
    conn.close()
    return jsonify(payload)


@app.route('/api/sessions', methods=['GET'])
def api_sessions():
    status = request.args.get('status')
    conn = get_db()
    if status:
        data = conn.execute(SESSION_SELECT + " WHERE cs.status=? ORDER BY cs.id DESC", (status,)).fetchall()
    else:
        data = conn.execute(SESSION_SELECT + " ORDER BY cs.id DESC").fetchall()
    conn.close()
    return jsonify(rows(data))


@app.route('/api/sessions', methods=['POST'])
def api_start_session():
    data = request.get_json(silent=True) or {}
    classroom_id = data.get('classroom_id')
    if not classroom_id:
        return json_error("Choose a classroom.")
    conn = get_db()
    camera_id = data.get('camera_id')
    if not camera_id:
        cam = conn.execute(
            "SELECT id FROM cameras WHERE classroom_id=? AND status='active' ORDER BY "
            "CASE position WHEN 'cctv1' THEN 1 WHEN 'cctv2' THEN 2 WHEN 'door' THEN 3 ELSE 4 END LIMIT 1",
            (classroom_id,)).fetchone()
        if not cam:
            conn.close()
            return json_error("This classroom has no active camera. Add a camera to it first.")
        camera_id = cam['id']
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO class_sessions (classroom_id, camera_id, subject_id, teacher_id, start_time, status) "
        "VALUES (?, ?, ?, ?, ?, 'Ongoing')",
        (classroom_id, camera_id, data.get('subject_id') or None, data.get('teacher_id') or None,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    session_id = cur.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'id': session_id}), 201


@app.route('/api/sessions/<int:session_id>')
def api_session(session_id):
    conn = get_db()
    sess = conn.execute(SESSION_SELECT + " WHERE cs.id=?", (session_id,)).fetchone()
    if not sess:
        conn.close()
        return json_error("Session not found.", 404)
    cams = conn.execute(
        "SELECT * FROM cameras WHERE classroom_id=? ORDER BY "
        "CASE position WHEN 'door' THEN 1 WHEN 'cctv1' THEN 2 WHEN 'cctv2' THEN 3 ELSE 4 END",
        (sess['classroom_id'],)).fetchall()
    conn.close()
    return jsonify({'session': dict(sess), 'cameras': [camera_dict(c) for c in cams]})


@app.route('/api/sessions/<int:session_id>/end', methods=['POST'])
def api_end_session(session_id):
    conn = get_db()
    sess = conn.execute("SELECT * FROM class_sessions WHERE id=?", (session_id,)).fetchone()
    if not sess:
        conn.close()
        return json_error("Session not found.", 404)
    if sess['status'] != 'Ongoing':
        conn.close()
        return jsonify({'id': session_id, 'status': sess['status']})

    end_dt = datetime.now()
    try:
        start_dt = datetime.strptime(sess['start_time'], "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        start_dt = end_dt
    cur = conn.cursor()
    cur.execute("UPDATE class_sessions SET end_time=?, status='Ended' WHERE id=?",
                (end_dt.strftime("%Y-%m-%d %H:%M:%S"), session_id))

    with state_lock:
        state = active_sessions.pop(session_id, None)
    if state:
        for key, info in state['people'].items():
            duration = int((info['last_seen'] - info['first_seen']).total_seconds())
            first, last = info['first_seen'].strftime("%H:%M:%S"), info['last_seen'].strftime("%H:%M:%S")
            if info['type'] == 'teacher':
                cur.execute(
                    "INSERT INTO teacher_attendance_logs (session_id, teacher_id, first_seen, last_seen, total_duration_seconds, status) "
                    "VALUES (?, ?, ?, ?, ?, 'Present')",
                    (session_id, int(key.replace('teacher_', '')), first, last, duration))
            else:
                status = classify_attendance(start_dt, end_dt, info['first_seen'], info['last_seen'])
                cur.execute(
                    "INSERT INTO attendance_logs (session_id, student_id, first_seen, last_seen, total_duration_seconds, status) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (session_id, key, first, last, duration, status))
    conn.commit()
    conn.close()
    return jsonify({'id': session_id, 'status': 'Ended'})


@app.route('/api/sessions/<int:session_id>/report')
def api_report(session_id):
    conn = get_db()
    sess = conn.execute(SESSION_SELECT + " WHERE cs.id=?", (session_id,)).fetchone()
    if not sess:
        conn.close()
        return json_error("Session not found.", 404)
    students = rows(conn.execute('''
        SELECT a.student_id AS id, COALESCE(s.name, a.student_id) AS name, s.photo, 'student' AS type,
               a.first_seen, a.last_seen, a.total_duration_seconds AS duration, a.status
        FROM attendance_logs a LEFT JOIN students s ON a.student_id = s.student_id
        WHERE a.session_id=? ORDER BY a.first_seen
    ''', (session_id,)).fetchall())
    teachers = rows(conn.execute('''
        SELECT CAST(a.teacher_id AS TEXT) AS id, COALESCE(t.name, 'Teacher ' || a.teacher_id) AS name, t.photo,
               'teacher' AS type, a.first_seen, a.last_seen, a.total_duration_seconds AS duration, a.status
        FROM teacher_attendance_logs a LEFT JOIN teachers t ON a.teacher_id = t.id
        WHERE a.session_id=? ORDER BY a.first_seen
    ''', (session_id,)).fetchall())

    # Students enrolled in this subject but never seen are absent
    absent = []
    if sess['subject_id'] and sess['status'] == 'Ended':
        seen = {s['id'] for s in students}
        roster = conn.execute('''
            SELECT s.student_id AS id, s.name, s.photo FROM student_subjects ss
            JOIN students s ON s.student_id = ss.student_id WHERE ss.subject_id=?
        ''', (sess['subject_id'],)).fetchall()
        absent = [{**dict(r), 'type': 'student', 'first_seen': None, 'last_seen': None,
                   'duration': 0, 'status': 'Absent'} for r in roster if r['id'] not in seen]
    conn.close()
    return jsonify({'session': dict(sess), 'logs': teachers + students + absent})


@app.route('/api/live_status/<int:session_id>')
def api_live_status(session_id):
    with state_lock:
        state = active_sessions.get(session_id)
        if not state:
            return jsonify({'people': [], 'present_count': 0, 'seen_count': 0, 'faces_in_view': 0})
        now = datetime.now()
        people = []
        for key, info in state['people'].items():
            people.append({
                'id': key,
                'name': info['name'],
                'type': info['type'],
                'photo': info.get('photo'),
                'face_image': info.get('face_image', ''),
                'first_seen': info['first_seen'].strftime("%H:%M:%S"),
                'last_seen': info['last_seen'].strftime("%H:%M:%S"),
                'duration': int((info['last_seen'] - info['first_seen']).total_seconds()),
                'present': (now - info['last_seen']).total_seconds() <= PRESENT_WINDOW_SECONDS,
            })
        counts = state['counts']
    people.sort(key=lambda p: (not p['present'], p['first_seen']))
    return jsonify({
        'people': people,
        'present_count': sum(1 for p in people if p['present']),
        'seen_count': len(people),
        'faces_in_view': counts.get('faces_in_view', 0),
    })


@app.route('/video_feed/<int:session_id>/<int:camera_id>')
def video_feed_camera(session_id, camera_id):
    return Response(generate_frames(session_id, camera_id), mimetype='multipart/x-mixed-replace; boundary=frame')


# ---------------------------------------------------------------------------
# API: classrooms
# ---------------------------------------------------------------------------

@app.route('/api/classrooms', methods=['GET'])
def api_classrooms():
    conn = get_db()
    data = classrooms_with_cameras(conn)
    conn.close()
    return jsonify(data)


@app.route('/api/classrooms', methods=['POST'])
def api_create_classroom():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return json_error("Classroom name is required.")
    cameras = [
        ('door', 'Door', 'attendance', resolve_camera_url(data.get('door'))),
        ('cctv1', 'CCTV 1', 'tracking', resolve_camera_url(data.get('cctv1'))),
        ('cctv2', 'CCTV 2', 'tracking', resolve_camera_url(data.get('cctv2'))),
    ]
    if not any(url for *_, url in cameras):
        return json_error("Add at least one camera.")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO classrooms (name) VALUES (?)", (name,))
    classroom_id = cur.lastrowid
    for position, label, ctype, url in cameras:
        if url:
            cur.execute(
                "INSERT INTO cameras (name, type, location, url, status, classroom_id, position) "
                "VALUES (?, ?, ?, ?, 'active', ?, ?)",
                (f"{name} - {label}", ctype, name, url, classroom_id, position))
    conn.commit()
    conn.close()
    return jsonify({'id': classroom_id}), 201


@app.route('/api/classrooms/<int:classroom_id>', methods=['DELETE'])
def api_delete_classroom(classroom_id):
    conn = get_db()
    if not conn.execute("SELECT 1 FROM classrooms WHERE id=?", (classroom_id,)).fetchone():
        conn.close()
        return json_error("Classroom not found.", 404)
    conn.execute("DELETE FROM cameras WHERE classroom_id=?", (classroom_id,))
    conn.execute("DELETE FROM classrooms WHERE id=?", (classroom_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


# ---------------------------------------------------------------------------
# API: students
# ---------------------------------------------------------------------------

@app.route('/api/students', methods=['GET'])
def api_students():
    conn = get_db()
    data = rows(conn.execute('''
        SELECT s.student_id, s.name, s.photo,
               GROUP_CONCAT(sub.name, '||') AS courses,
               GROUP_CONCAT(sub.id, '||') AS course_ids,
               (SELECT COUNT(*) FROM attendance_logs a WHERE a.student_id = s.student_id) AS sessions_attended,
               (SELECT MAX(cs.start_time) FROM attendance_logs a JOIN class_sessions cs ON cs.id = a.session_id
                 WHERE a.student_id = s.student_id) AS last_seen
        FROM students s
        LEFT JOIN student_subjects ss ON s.student_id = ss.student_id
        LEFT JOIN subjects sub ON ss.subject_id = sub.id
        GROUP BY s.student_id, s.name, s.photo
        ORDER BY s.name
    ''').fetchall())
    conn.close()
    for s in data:
        s['courses'] = s['courses'].split('||') if s['courses'] else []
        s['course_ids'] = [int(i) for i in s['course_ids'].split('||')] if s['course_ids'] else []
    return jsonify(data)


@app.route('/api/students', methods=['POST'])
def api_enroll_student():
    data = request.get_json(silent=True) or {}
    student_id = (data.get('student_id') or '').strip()
    name = (data.get('name') or '').strip()
    image_b64 = data.get('image')
    subject_ids = data.get('subject_ids') or []
    if not student_id or not name:
        return json_error("Student ID and name are required.")
    if not image_b64:
        return json_error("Capture or upload a photo first.")
    try:
        embedding, crop = embed_largest_face(decode_image(image_b64))
    except ValueError as e:
        return json_error(str(e), 422)
    except Exception as e:
        return json_error(f"Face processing failed: {e}", 500)

    photo = save_face_photo('s', student_id, crop)
    conn = get_db()
    exists = conn.execute("SELECT 1 FROM students WHERE student_id=?", (student_id,)).fetchone()
    if exists:
        conn.execute("UPDATE students SET name=?, embedding=?, photo=? WHERE student_id=?",
                     (name, embedding.tobytes(), photo, student_id))
    else:
        conn.execute("INSERT INTO students (student_id, name, embedding, photo) VALUES (?, ?, ?, ?)",
                     (student_id, name, embedding.tobytes(), photo))
    conn.execute("DELETE FROM student_subjects WHERE student_id=?", (student_id,))
    for subject_id in subject_ids:
        conn.execute("INSERT OR IGNORE INTO student_subjects (student_id, subject_id) VALUES (?, ?)",
                     (student_id, int(subject_id)))
    conn.commit()
    conn.close()
    reload_enrolled()
    return jsonify({'ok': True, 'updated': bool(exists), 'photo': photo}), 201


@app.route('/api/students/<student_id>', methods=['PATCH'])
def api_update_student(student_id):
    data = request.get_json(silent=True) or {}
    conn = get_db()
    if not conn.execute("SELECT 1 FROM students WHERE student_id=?", (student_id,)).fetchone():
        conn.close()
        return json_error("Student not found.", 404)
    if data.get('name'):
        conn.execute("UPDATE students SET name=? WHERE student_id=?", (data['name'].strip(), student_id))
    if 'subject_ids' in data:
        conn.execute("DELETE FROM student_subjects WHERE student_id=?", (student_id,))
        for subject_id in data['subject_ids'] or []:
            conn.execute("INSERT OR IGNORE INTO student_subjects (student_id, subject_id) VALUES (?, ?)",
                         (student_id, int(subject_id)))
    conn.commit()
    conn.close()
    reload_enrolled()
    return jsonify({'ok': True})


@app.route('/api/students/<student_id>', methods=['DELETE'])
def api_delete_student(student_id):
    conn = get_db()
    row = conn.execute("SELECT photo FROM students WHERE student_id=?", (student_id,)).fetchone()
    if row:
        delete_face_photo(row['photo'])
    conn.execute("DELETE FROM student_subjects WHERE student_id=?", (student_id,))
    conn.execute("DELETE FROM students WHERE student_id=?", (student_id,))
    conn.commit()
    conn.close()
    reload_enrolled()
    return jsonify({'ok': True})


# ---------------------------------------------------------------------------
# API: teachers
# ---------------------------------------------------------------------------

@app.route('/api/teachers', methods=['GET'])
def api_teachers():
    conn = get_db()
    data = rows(conn.execute('''
        SELECT t.id, t.name, t.photo, t.embedding IS NOT NULL AS has_face,
               (SELECT COUNT(*) FROM class_sessions cs WHERE cs.teacher_id = t.id) AS sessions
        FROM teachers t ORDER BY t.name
    ''').fetchall())
    conn.close()
    return jsonify(data)


@app.route('/api/teachers', methods=['POST'])
def api_create_teacher():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return json_error("Teacher name is required.")
    embedding = crop = None
    if data.get('image'):
        try:
            embedding, crop = embed_largest_face(decode_image(data['image']))
        except ValueError as e:
            return json_error(str(e), 422)
    conn = get_db()
    try:
        cur = conn.execute("INSERT INTO teachers (name, embedding) VALUES (?, ?)",
                           (name, embedding.tobytes() if embedding is not None else None))
    except sqlite3.IntegrityError:
        conn.close()
        return json_error("A teacher with this name already exists.", 409)
    teacher_id = cur.lastrowid
    if crop is not None:
        conn.execute("UPDATE teachers SET photo=? WHERE id=?", (save_face_photo('t', teacher_id, crop), teacher_id))
    conn.commit()
    conn.close()
    reload_enrolled()
    return jsonify({'id': teacher_id}), 201


@app.route('/api/teachers/<int:teacher_id>/face', methods=['POST'])
def api_teacher_face(teacher_id):
    data = request.get_json(silent=True) or {}
    if not data.get('image'):
        return json_error("Capture or upload a photo first.")
    try:
        embedding, crop = embed_largest_face(decode_image(data['image']))
    except ValueError as e:
        return json_error(str(e), 422)
    conn = get_db()
    if not conn.execute("SELECT 1 FROM teachers WHERE id=?", (teacher_id,)).fetchone():
        conn.close()
        return json_error("Teacher not found.", 404)
    conn.execute("UPDATE teachers SET embedding=?, photo=? WHERE id=?",
                 (embedding.tobytes(), save_face_photo('t', teacher_id, crop), teacher_id))
    conn.commit()
    conn.close()
    reload_enrolled()
    return jsonify({'ok': True})


@app.route('/api/teachers/<int:teacher_id>', methods=['DELETE'])
def api_delete_teacher(teacher_id):
    conn = get_db()
    row = conn.execute("SELECT photo FROM teachers WHERE id=?", (teacher_id,)).fetchone()
    if row:
        delete_face_photo(row['photo'])
    conn.execute("UPDATE class_sessions SET teacher_id=NULL WHERE teacher_id=?", (teacher_id,))
    conn.execute("DELETE FROM teachers WHERE id=?", (teacher_id,))
    conn.commit()
    conn.close()
    reload_enrolled()
    return jsonify({'ok': True})


# ---------------------------------------------------------------------------
# API: subjects
# ---------------------------------------------------------------------------

@app.route('/api/subjects', methods=['GET'])
def api_subjects():
    conn = get_db()
    data = rows(conn.execute('''
        SELECT sub.id, sub.name,
               (SELECT COUNT(*) FROM student_subjects ss WHERE ss.subject_id = sub.id) AS students,
               (SELECT COUNT(*) FROM class_sessions cs WHERE cs.subject_id = sub.id) AS sessions
        FROM subjects sub ORDER BY sub.name
    ''').fetchall())
    conn.close()
    return jsonify(data)


@app.route('/api/subjects', methods=['POST'])
def api_create_subject():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return json_error("Subject name is required.")
    conn = get_db()
    try:
        cur = conn.execute("INSERT INTO subjects (name) VALUES (?)", (name,))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return json_error("This subject already exists.", 409)
    conn.close()
    return jsonify({'id': cur.lastrowid}), 201


@app.route('/api/subjects/<int:subject_id>', methods=['DELETE'])
def api_delete_subject(subject_id):
    conn = get_db()
    conn.execute("DELETE FROM student_subjects WHERE subject_id=?", (subject_id,))
    conn.execute("UPDATE class_sessions SET subject_id=NULL WHERE subject_id=?", (subject_id,))  # keep history
    conn.execute("DELETE FROM subjects WHERE id=?", (subject_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


# ---------------------------------------------------------------------------
# Frontend (React build in frontend/dist)
# ---------------------------------------------------------------------------

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def spa(path):
    if path.startswith('api/'):
        return json_error("Not found.", 404)
    if path and os.path.isfile(os.path.join(FRONTEND_DIST, path)):
        return send_from_directory(FRONTEND_DIST, path)
    if os.path.isfile(os.path.join(FRONTEND_DIST, 'index.html')):
        return send_from_directory(FRONTEND_DIST, 'index.html')
    return ("Frontend is not built yet. Run:  cd frontend  &&  npm install  &&  npm run build", 503)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"\nVision Sentinal running at http://127.0.0.1:{port}\n")
    app.run(host='127.0.0.1', debug=False, port=port, use_reloader=False, threaded=True)
