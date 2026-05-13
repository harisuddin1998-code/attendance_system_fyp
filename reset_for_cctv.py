import sqlite3

conn = sqlite3.connect('attendance.db')
cursor = conn.cursor()

# End all ongoing sessions
cursor.execute('UPDATE class_sessions SET status = "Ended", end_time = datetime("now") WHERE status = "Ongoing"')
conn.commit()
print(f'Ended {cursor.rowcount} ongoing sessions')

# Reset cameras to use local indices for CCTV cameras
cursor.execute('UPDATE cameras SET url = NULL, camera_source = "0" WHERE id = 1')
cursor.execute('UPDATE cameras SET url = NULL, camera_source = "1" WHERE id = 2')
cursor.execute('UPDATE cameras SET name = "CCTV Camera 1" WHERE id = 1')
cursor.execute('UPDATE cameras SET name = "CCTV Camera 2" WHERE id = 2')

conn.commit()

# Verify changes
cursor.execute('SELECT id, name, camera_source, url FROM cameras')
cameras = cursor.fetchall()
print('Updated cameras for CCTV:')
for cam in cameras:
    print(f'ID: {cam[0]}, Name: {cam[1]}, Source: {cam[2]}, URL: {cam[3]}')

conn.close()