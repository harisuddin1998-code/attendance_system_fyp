# 🎓 AI-Powered Classroom Attendance System

A real-time face recognition based attendance management system built with **Flask**, **DeepFace**, and **OpenCV**.

---

## 📁 Project Structure

```
attendance_system_fyp/
│
├── app.py                     # Main Flask application
├── attendance_tracker.py      # Attendance tracking logic
├── enroll_faces.py            # Face enrollment utilities
├── capture_and_enroll.py      # Camera capture & enrollment
├── requirements.txt           # Python dependencies
├── .gitignore                 # Git ignore rules
│
├── templates/                 # HTML Templates
│   ├── dashboard.html
│   ├── live.html
│   ├── report.html
│   ├── students.html
│   ├── subjects.html
│   ├── teachers.html
│   └── teacher_dashboard.html
│
├── static/                    # Static Assets
│   └── css/
│       └── style.css
│
├── dataset/                   # Student face images for recognition
│
└── docs/                      # Documentation (optional)
    ├── implementation_plan.md
    └── white_paper.md
```

---

## 🚀 Setup Guide (After Cloning)

### Prerequisites
- Python **3.10** or **3.11** (recommended)
- pip (Python package manager)
- Git

### Step 1: Clone the Repository
```bash
git clone https://github.com/harisuddin1998-code/attendance_system_fyp.git
cd attendance_system_fyp
```

### Step 2: Create a Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Initialize the Database
```bash
python reset_db.py
```

### Step 5: Run the Application
```bash
python app.py
```
The app will start at **http://127.0.0.1:5000**

---

## 📦 Key Dependencies

| Package | Purpose |
|---------|---------|
| Flask | Web framework |
| DeepFace | Face recognition engine |
| OpenCV | Camera & image processing |
| TensorFlow | Deep learning backend |
| NumPy | Numerical computing |
| Pillow | Image handling |
| deep-sort-realtime | Multi-object tracking |

---

## ⚙️ Features

- ✅ Real-time face recognition attendance
- ✅ Student registration with live camera
- ✅ Teacher & subject management
- ✅ Attendance reports & analytics
- ✅ Multi-camera support
- ✅ Dashboard with live preview

---

## 📝 Notes

- The `dataset/` folder contains enrolled student face images
- DeepFace models will be **automatically downloaded** on first run (~500MB)
- The SQLite database (`attendance.db`) is created automatically by `reset_db.py`

---

## 👨‍💻 Author

**Haris Uddin** — Final Year Project 2026
