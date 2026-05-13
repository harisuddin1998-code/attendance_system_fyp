import sqlite3

# Update camera 2 with the provided URL
conn = sqlite3.connect('attendance.db')
cursor = conn.cursor()

# Update second camera with user's URL
cursor.execute('UPDATE cameras SET url = ? WHERE id = ?', ('http://192.168.0.100:4747/video', 2))

conn.commit()

# Verify the updates
cursor.execute('SELECT * FROM cameras')
cameras = cursor.fetchall()
print('Updated cameras:')
for cam in cameras:
    print(f'ID: {cam[0]}, Name: {cam[1]}, Type: {cam[2]}, Location: {cam[3]}, URL: {cam[4]}, Source: {cam[5]}')

conn.close()