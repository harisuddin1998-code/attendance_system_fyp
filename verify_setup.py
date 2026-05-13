import sqlite3
conn = sqlite3.connect('attendance.db')
cursor = conn.cursor()

# End all ongoing sessions
cursor.execute('UPDATE class_sessions SET status = "Ended", end_time = datetime("now") WHERE status = "Ongoing"')
conn.commit()
ended = cursor.rowcount

# Verify camera setup
cursor.execute('SELECT id, name, type, url FROM cameras')
cameras = cursor.fetchall()

print(f'Ended {ended} sessions')
print('Camera setup:')
for cam in cameras:
    print(f'  Camera {cam[0]}: {cam[1]} ({cam[2]})')
    print(f'    URL: {cam[3]}')

conn.close()