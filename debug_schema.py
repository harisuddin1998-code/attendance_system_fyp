import sqlite3
conn = sqlite3.connect('attendance.db')
cur = conn.cursor()
tables = ['cameras', 'class_sessions', 'attendance_logs', 'students', 'classrooms']
for tbl in tables:
    cur.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name=?', (tbl,))
    row = cur.fetchone()
    print(tbl + ':', row[0] if row else 'MISSING')
conn.close()
