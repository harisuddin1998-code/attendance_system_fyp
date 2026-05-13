import requests
import time

# Start a session first
print('Creating session...')
response = requests.post('http://127.0.0.1:5000/start_session', data={'camera_id': '1', 'classroom_id': '1'}, allow_redirects=False)
print(f'Session creation response: {response.status_code}')
print(f'Redirect location: {response.headers.get("Location", "None")}')

if response.status_code == 302:
    location = response.headers.get('Location')
    session_id = location.split('/')[-1]
    print(f'Session ID: {session_id}')

    # Test video feed
    print('Testing video feed...')
    try:
        response = requests.get(f'http://127.0.0.1:5000/video_feed/{session_id}', stream=True, timeout=10)
        print(f'Video feed status: {response.status_code}')
        print(f'Content type: {response.headers.get("content-type", "None")}')

        if response.status_code == 200:
            # Try to read some data
            data = b''
            for chunk in response.iter_content(chunk_size=1024):
                data += chunk
                if len(data) > 2048:  # Read first 2KB
                    break
            print(f'Data received: {len(data)} bytes')
            if len(data) > 0:
                print(f'First 100 bytes: {data[:100]}')
        else:
            print('Video feed failed')

    except Exception as e:
        print(f'Error accessing video feed: {e}')
else:
    print('Session creation failed')