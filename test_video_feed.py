"""Smoke test: start a session through the API and read a few bytes of its video feed.

Run with the server already running (python app.py). Usage:
    python test_video_feed.py [classroom_id]
"""
import sys

import requests

BASE = "http://127.0.0.1:5000"
classroom_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1

print("Creating session...")
r = requests.post(f"{BASE}/api/sessions", json={"classroom_id": classroom_id})
print(f"Session creation response: {r.status_code} {r.json()}")
if r.status_code != 201:
    sys.exit(1)
session_id = r.json()["id"]

detail = requests.get(f"{BASE}/api/sessions/{session_id}").json()
camera = detail["cameras"][0]
print(f"Testing video feed for camera {camera['id']} ({camera['name']})...")
try:
    feed = requests.get(f"{BASE}/video_feed/{session_id}/{camera['id']}", stream=True, timeout=15)
    print(f"Video feed status: {feed.status_code}, content type: {feed.headers.get('content-type')}")
    data = b""
    for chunk in feed.iter_content(chunk_size=1024):
        data += chunk
        if len(data) > 2048:
            break
    print(f"Data received: {len(data)} bytes")
finally:
    requests.post(f"{BASE}/api/sessions/{session_id}/end")
    print(f"Session {session_id} ended.")
