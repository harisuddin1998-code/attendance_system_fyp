# Vision Sentinal

AI-powered classroom attendance system.

Real-time, face-recognition attendance for classrooms. Cameras watch the room, recognise enrolled students and teachers, and record when each person arrived and left.

- **Backend:** Python · Flask · DeepFace (RetinaFace detector + Facenet512 embeddings) · OpenCV · SQLite
- **Frontend:** React · TypeScript · Vite · Tailwind CSS · [shadcn/ui](https://ui.shadcn.com)

---

## Quick start (Windows)

You need **Python 3.11** (TensorFlow 2.13 does not support newer versions) and **Node.js 20+**.

```powershell
# 1. Python environment
python -m venv venv                # must be Python 3.11 (or: py -3.11 -m venv venv / uv venv --python 3.11 venv)
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Build the web interface (once, and again after changing frontend code)
cd frontend
npm install
npm run build
cd ..

# 3. Run
python app.py
```

Open **http://127.0.0.1:5000**. Flask serves both the API and the built interface. The database (`attendance.db`) is created automatically on first run. The face models (~200 MB) download into `~/.deepface` the first time they're used.

Use a different port with `$env:PORT=5055; python app.py`.

### Frontend development (hot reload)

Run the backend (`python app.py`) and, in a second terminal:

```powershell
cd frontend
npm run dev
```

Open the URL Vite prints (http://localhost:5173). API, video and photo requests are proxied to Flask on port 5000.

---

## Importing a recorded classroom video

```powershell
python import_video_attendance.py path\to\video.mp4 --classroom "Innovation Lab" --subject "Computer Science" --teacher "Prof. Ahmed"
```

The script:
1. Detects faces with RetinaFace throughout the video.
2. Groups them into people (by position and face similarity).
3. Enrolls each person under a random name with a face photo.
4. Creates the classroom, using the video as its camera, plus a completed session with everyone's attendance.

The video is copied to `data/videos/` and plays on a loop as a "live camera". Start a session in that classroom to watch live recognition. People whose faces never turn towards the camera can't be identified.

---

## How it works

| Step | What happens |
|---|---|
| Enrol | A photo (webcam or upload) → RetinaFace finds the face → Facenet512 turns it into a 512-number signature stored in SQLite. |
| Start session | Pick a classroom (+ subject and teacher). Each of its cameras streams to the browser. |
| Recognise | About once per second, faces in the current frame are detected and compared (cosine distance < 0.45) with every enrolled student and teacher. |
| Live view | The page polls `/api/live_status` every 2 s and shows who is in view. |
| End session | Each recognised person is saved as **Present**, **Late** (first seen more than 25 min after start) or **Left early** (last seen more than 5 min before the end). Students enrolled in the subject who were never seen show as **Absent** in the report. |

### Camera sources
When adding a classroom, each camera can be:
- `0` for this computer's webcam
- `IP:port` for a phone camera app (DroidCam / IP Webcam)
- a full `rtsp://` or `http://` URL
- a path to a video file

### Project layout
```
app.py                       Flask API, recognition pipeline, serves frontend/dist
import_video_attendance.py   Enrol people + record attendance from a recorded video
attendance_tracker.py        Stand-alone OpenCV-window tracker (no web UI)
frontend/                    React + shadcn/ui app (src/pages = one file per page)
static/faces/                Face thumbnails (git-ignored: biometric data)
data/videos/                 Imported videos (git-ignored)
```

### API (JSON)
`GET /api/overview` · `GET|POST /api/sessions` · `GET /api/sessions/<id>` · `POST /api/sessions/<id>/end` · `GET /api/sessions/<id>/report` · `GET /api/live_status/<id>` · `GET /video_feed/<session>/<camera>` (MJPEG) · `GET|POST /api/students` · `PATCH|DELETE /api/students/<id>` · `GET|POST /api/teachers` · `POST /api/teachers/<id>/face` · `DELETE /api/teachers/<id>` · `GET|POST /api/subjects` · `DELETE /api/subjects/<id>` · `GET|POST /api/classrooms` · `DELETE /api/classrooms/<id>`

---

## Privacy

Face photos and signatures are biometric data. They stay on this machine: `attendance.db`, `static/faces/` and `data/` are git-ignored. Deleting a student or teacher removes their face photo as well.

---

## Author

**Haris Uddin**, Final Year Project 2026
