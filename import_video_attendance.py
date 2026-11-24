"""Import a recorded classroom video: find every identifiable person, enroll them
under a random name, and record an attendance session for them.

Usage:
    python import_video_attendance.py path/to/video.mp4 [--classroom "Innovation Lab"]

How it works
  1. RetinaFace detects faces every few frames.
  2. Detections are linked into tracks by position (people mostly stay in place),
     then track fragments are merged by face-embedding similarity. Position is
     needed because small, distant faces can look alike to the embedding model.
  3. Each track with enough sightings becomes one student: a Facenet512 embedding
     (mean of all sightings), a face thumbnail and a random name.
  4. A classroom with the video as its camera, a session and attendance logs are
     written to attendance.db, using the same rules the live system uses.
Re-running is safe: people already imported keep their IDs and names.
"""
import argparse
import os
import random
import shutil
from datetime import datetime, timedelta

import cv2
import numpy as np

import app as core  # reuses the app's DB, detector, embedding and photo helpers

SAMPLE_EVERY = 5          # frames between detections
MIN_SIGHTINGS = 4         # drop tracks seen fewer times (noise / false positives)
LINK_DISTANCE = 1.2       # max centre jump between samples, in face-widths
MAX_GAP_FRAMES = 30       # a track can be missed for up to ~1 s and continue
MERGE_EMBED_DIST = 0.35   # merge non-overlapping fragments that look this alike
MERGE_NEAR_DIST = 0.50    # ... or that are close in space and look reasonably alike
ID_PREFIX = "V1-"

FIRST = ["Ayesha", "Zara", "Hira", "Maryam", "Sana", "Iqra", "Amna", "Laiba", "Noor", "Fatima",
         "Ali", "Hamza", "Usman", "Bilal", "Saad", "Omar", "Danish", "Rayan", "Emma", "Sofia",
         "Mia", "Lina", "Yusra", "Mahnoor", "Areeba", "Kinza", "Eman", "Rida", "Anaya", "Hania"]
LAST = ["Khan", "Ahmed", "Malik", "Qureshi", "Siddiqui", "Raza", "Hussain", "Sheikh", "Butt",
        "Chaudhry", "Iqbal", "Javed", "Shah", "Mirza", "Abbasi", "Farooq", "Nadeem", "Aslam"]


def unit(v):
    return v / (np.linalg.norm(v) + 1e-9)


def detect_all(video_path):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    detections, idx = [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % SAMPLE_EVERY == 0:
            for (x, y, w, h, conf) in core.detect_faces(frame):
                crop = frame[max(y, 0):y + h, max(x, 0):x + w].copy()
                if crop.size == 0:
                    continue
                detections.append({
                    'frame': idx, 't': idx / fps, 'box': (x, y, w, h), 'conf': conf,
                    'center': (x + w / 2, y + h / 2), 'size': max(w, h),
                    'emb': unit(core.embed_face(crop)), 'crop': core.padded_crop(frame, (x, y, w, h)),
                })
            print(f"  frame {idx:4d}/{total}  faces so far: {len(detections)}", end="\r", flush=True)
        idx += 1
    cap.release()
    print()
    return detections, total / fps


def link_tracks(detections):
    tracks = []
    for frame in sorted({d['frame'] for d in detections}):
        dets = [d for d in detections if d['frame'] == frame]
        live = [t for t in tracks if frame - t['last_frame'] <= MAX_GAP_FRAMES]
        pairs = []
        for di, d in enumerate(dets):
            for ti, t in enumerate(live):
                last = t['members'][-1]
                dist = np.hypot(d['center'][0] - last['center'][0], d['center'][1] - last['center'][1])
                if dist <= LINK_DISTANCE * max(d['size'], last['size']):
                    pairs.append((dist, di, ti))
        used_d, used_t = set(), set()
        for dist, di, ti in sorted(pairs):
            if di in used_d or ti in used_t:
                continue
            used_d.add(di)
            used_t.add(ti)
            live[ti]['members'].append(dets[di])
            live[ti]['last_frame'] = frame
        for di, d in enumerate(dets):
            if di not in used_d:
                tracks.append({'members': [d], 'last_frame': frame})
    return [t['members'] for t in tracks]


def merge_fragments(tracks):
    def centroid(m):
        return unit(np.mean([d['emb'] for d in m], axis=0))

    def frames(m):
        return {d['frame'] for d in m}

    def mean_pos(m):
        return np.mean([d['center'] for d in m], axis=0), np.mean([d['size'] for d in m])

    merged = True
    while merged:
        merged = False
        best = None
        for i in range(len(tracks)):
            for j in range(i + 1, len(tracks)):
                if frames(tracks[i]) & frames(tracks[j]):
                    continue  # seen at the same time -> different people
                d_emb = 1 - float(centroid(tracks[i]) @ centroid(tracks[j]))
                (pi, si), (pj, sj) = mean_pos(tracks[i]), mean_pos(tracks[j])
                near = np.linalg.norm(pi - pj) <= 2.5 * max(si, sj)
                if d_emb < MERGE_EMBED_DIST or (near and d_emb < MERGE_NEAR_DIST):
                    if best is None or d_emb < best[0]:
                        best = (d_emb, i, j)
        if best:
            _, i, j = best
            tracks[i] = sorted(tracks[i] + tracks[j], key=lambda d: d['frame'])
            del tracks[j]
            merged = True
    return tracks


def get_or_create(conn, table, name):
    row = conn.execute(f"SELECT id FROM {table} WHERE name=?", (name,)).fetchone()
    if row:
        return row['id']
    return conn.execute(f"INSERT INTO {table} (name) VALUES (?)", (name,)).lastrowid


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('video')
    parser.add_argument('--classroom', default='Innovation Lab')
    parser.add_argument('--subject', default='Computer Science')
    parser.add_argument('--teacher', default='Prof. Ahmed')
    args = parser.parse_args()

    if not os.path.isfile(args.video):
        raise SystemExit(f"Video not found: {args.video}")

    # Keep a copy inside the project so the classroom camera keeps working
    videos_dir = os.path.join(core.BASE_DIR, 'data', 'videos')
    os.makedirs(videos_dir, exist_ok=True)
    video_path = os.path.join(videos_dir, os.path.basename(args.video))
    if os.path.abspath(args.video) != os.path.abspath(video_path):
        shutil.copyfile(args.video, video_path)

    print(f"1/4  Detecting faces in {os.path.basename(video_path)} ...")
    detections, duration = detect_all(video_path)
    print(f"     {len(detections)} face sightings in {duration:.1f}s of video")

    print("2/4  Linking sightings into people ...")
    tracks = merge_fragments(link_tracks(detections))
    people = sorted([t for t in tracks if len(t) >= MIN_SIGHTINGS], key=lambda t: t[0]['frame'])
    print(f"     {len(people)} identifiable people ({len(tracks) - len(people)} short fragments ignored)")
    if not people:
        raise SystemExit("No identifiable faces found.")

    print("3/4  Enrolling people ...")
    conn = core.get_db()
    used_names = {r['name'] for r in conn.execute("SELECT name FROM students").fetchall()}
    name_pool = [f"{f} {l}" for f in FIRST for l in LAST if f"{f} {l}" not in used_names]
    random.shuffle(name_pool)

    subject_id = get_or_create(conn, 'subjects', args.subject)
    teacher_id = get_or_create(conn, 'teachers', args.teacher)

    enrolled = []
    for n, members in enumerate(people, start=1):
        student_id = f"{ID_PREFIX}{n:03d}"
        embedding = unit(np.mean([d['emb'] for d in members], axis=0)).astype('float32')
        best = max(members, key=lambda d: d['size'] * d['conf'])
        photo = core.save_face_photo('s', student_id, best['crop'])
        existing = conn.execute("SELECT name FROM students WHERE student_id=?", (student_id,)).fetchone()
        name = existing['name'] if existing else name_pool.pop()
        if existing:
            conn.execute("UPDATE students SET embedding=?, photo=? WHERE student_id=?",
                         (embedding.tobytes(), photo, student_id))
        else:
            conn.execute("INSERT INTO students (student_id, name, embedding, photo) VALUES (?, ?, ?, ?)",
                         (student_id, name, embedding.tobytes(), photo))
        conn.execute("INSERT OR IGNORE INTO student_subjects (student_id, subject_id) VALUES (?, ?)",
                     (student_id, subject_id))
        enrolled.append((student_id, name, members))
        print(f"     {student_id}  {name:<20} seen {len(members):3d}x  "
              f"{members[0]['t']:.1f}s -> {members[-1]['t']:.1f}s")

    print("4/4  Recording attendance ...")
    room = conn.execute("SELECT id FROM classrooms WHERE name=?", (args.classroom,)).fetchone()
    if room:
        classroom_id = room['id']
    else:
        classroom_id = conn.execute("INSERT INTO classrooms (name) VALUES (?)", (args.classroom,)).lastrowid
    cam = conn.execute("SELECT id FROM cameras WHERE classroom_id=? AND url=?", (classroom_id, video_path)).fetchone()
    if cam:
        camera_id = cam['id']
    else:
        camera_id = conn.execute(
            "INSERT INTO cameras (name, type, location, url, status, classroom_id, position) "
            "VALUES (?, 'tracking', ?, ?, 'active', ?, 'cctv1')",
            (f"{args.classroom} - CCTV 1", args.classroom, video_path, classroom_id)).lastrowid

    end_dt = datetime.now().replace(microsecond=0)
    start_dt = end_dt - timedelta(seconds=round(duration))
    fmt = "%Y-%m-%d %H:%M:%S"
    session_id = conn.execute(
        "INSERT INTO class_sessions (classroom_id, camera_id, subject_id, teacher_id, start_time, end_time, status) "
        "VALUES (?, ?, ?, ?, ?, ?, 'Ended')",
        (classroom_id, camera_id, subject_id, teacher_id, start_dt.strftime(fmt), end_dt.strftime(fmt))).lastrowid

    for student_id, name, members in enrolled:
        first = start_dt + timedelta(seconds=members[0]['t'])
        last = start_dt + timedelta(seconds=members[-1]['t'])
        status = core.classify_attendance(start_dt, end_dt, first, last)
        conn.execute(
            "INSERT INTO attendance_logs (session_id, student_id, first_seen, last_seen, total_duration_seconds, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, student_id, first.strftime("%H:%M:%S"), last.strftime("%H:%M:%S"),
             int((last - first).total_seconds()), status))
    conn.commit()
    conn.close()
    print(f"\nDone. Session #{session_id} in '{args.classroom}': {len(enrolled)} students marked.")
    print(f"Open http://127.0.0.1:5000/sessions/{session_id} to see the report.")


if __name__ == '__main__':
    main()
