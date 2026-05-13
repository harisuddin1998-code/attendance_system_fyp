import sqlite3

conn = sqlite3.connect('attendance.db')
cursor = conn.cursor()

# Add camera_source column if it doesn't exist
try:
    cursor.execute('ALTER TABLE cameras ADD COLUMN camera_source TEXT DEFAULT "0"')
    print('Added camera_source column')
except sqlite3.OperationalError as e:
    print(f'camera_source column may already exist: {e}')

# Update camera sources
cursor.execute('UPDATE cameras SET camera_source = "0" WHERE id = 1')  # Classroom CCTV - camera 0
cursor.execute('UPDATE cameras SET camera_source = "1" WHERE id = 2')  # Gate HD Camera - camera 1

conn.commit()

# Verify the updates
cursor.execute('SELECT id, name, camera_source FROM cameras')
cameras = cursor.fetchall()
print('Updated cameras:')
for cam in cameras:
    print(f'ID: {cam[0]}, Name: {cam[1]}, Source: {cam[2]}')

conn.close()