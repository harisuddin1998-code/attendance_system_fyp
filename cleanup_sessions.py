import sqlite3

conn = sqlite3.connect('attendance.db')
cursor = conn.cursor()

# Check ongoing sessions
cursor.execute('SELECT cs.id, cs.camera_id, c.name, c.url FROM class_sessions cs JOIN cameras c ON cs.camera_id = c.id WHERE cs.status = "Ongoing"')
sessions = cursor.fetchall()
print('Ongoing sessions:')
for sess in sessions:
    print(f'Session {sess[0]}: Camera {sess[1]} ({sess[2]}) - URL: {sess[3]}')

# End all ongoing sessions to start fresh
cursor.execute('UPDATE class_sessions SET status = "Ended", end_time = datetime("now") WHERE status = "Ongoing"')
conn.commit()
print(f'Ended {cursor.rowcount} ongoing sessions')

conn.close()