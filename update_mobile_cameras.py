import sqlite3

# Update existing cameras to use IP camera URLs
conn = sqlite3.connect('attendance.db')
cursor = conn.cursor()

# Update cameras with example URLs for mobile webcams
cursor.execute('UPDATE cameras SET url = ?, name = ? WHERE id = ?',
               ('http://192.168.1.100:4747/video', 'Mobile Camera 1', 1))
cursor.execute('UPDATE cameras SET url = ?, name = ? WHERE id = ?',
               ('http://192.168.1.101:4747/video', 'Mobile Camera 2', 2))

conn.commit()

# Verify the updates
cursor.execute('SELECT * FROM cameras')
cameras = cursor.fetchall()
print('Updated cameras:')
for cam in cameras:
    print(f'ID: {cam[0]}, Name: {cam[1]}, Type: {cam[2]}, Location: {cam[3]}, URL: {cam[4]}, Source: {cam[5]}')

conn.close()