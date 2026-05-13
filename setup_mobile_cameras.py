import sqlite3

conn = sqlite3.connect('attendance.db')
cursor = conn.cursor()

# Update cameras to use IP URLs for mobile webcams
cursor.execute('UPDATE cameras SET url = ?, camera_source = NULL WHERE id = ?', 
               ('http://192.168.0.106:4747/video', 1))
cursor.execute('UPDATE cameras SET url = ?, camera_source = NULL WHERE id = ?', 
               ('http://192.168.0.100:4747/video', 2))

# Update camera names and types
cursor.execute('UPDATE cameras SET name = ?, type = ? WHERE id = ?', 
               ('Gate Camera', 'attendance', 1))
cursor.execute('UPDATE cameras SET name = ?, type = ? WHERE id = ?', 
               ('Class Camera', 'tracking', 2))

# Update camera locations
cursor.execute('UPDATE cameras SET location = ? WHERE id = ?', 
               ('Gate Entrance', 1))
cursor.execute('UPDATE cameras SET location = ? WHERE id = ?', 
               ('Classroom', 2))

conn.commit()

# Verify
cursor.execute('SELECT id, name, type, location, url FROM cameras')
cameras = cursor.fetchall()
print('Updated Mobile Camera Setup:')
for cam in cameras:
    print(f'ID: {cam[0]}, Name: {cam[1]}, Type: {cam[2]}, Location: {cam[3]}, URL: {cam[4]}')

conn.close()