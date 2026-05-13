import sqlite3
import os

conn = sqlite3.connect('attendance.db')
cursor = conn.cursor()

# Delete records
cursor.execute("DELETE FROM attendance_logs")
cursor.execute("DELETE FROM teacher_attendance_logs")
cursor.execute("DELETE FROM class_sessions")
cursor.execute("DELETE FROM cameras")
cursor.execute("DELETE FROM classrooms")

# Reset sequence
try:
    cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('classrooms', 'cameras', 'class_sessions')")
except sqlite3.OperationalError:
    pass

# Create our single Master Class
cursor.execute("INSERT INTO classrooms (id, name) VALUES (1, 'Main Classroom')")

# Insert Camera attached to it
url = "rtsp://admin:YCSNFJ@192.168.0.100:554/Streaming/Channels/101"
cursor.execute("""
    INSERT INTO cameras (name, type, location, url, camera_source, status, classroom_id, position) 
    VALUES ('EZVIZ Main CCTV', 'tracking', 'Front Wall', ?, ?, 'active', 1, 'cctv1')
""", (url, url))

conn.commit()
conn.close()
print("Database cleanly reset: 1 Classroom, 1 Active Camera!")
