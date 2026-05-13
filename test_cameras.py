import cv2
import time

def test_camera_stream(camera_index):
    print(f"Testing camera {camera_index}...")
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print(f"Cannot open camera {camera_index}")
        return

    print(f"Camera {camera_index} opened successfully")

    frame_count = 0
    start_time = time.time()

    while frame_count < 10:  # Test 10 frames
        ret, frame = cap.read()
        if ret:
            frame_count += 1
            print(f"Camera {camera_index}: Frame {frame_count} - Shape: {frame.shape}")
        else:
            print(f"Camera {camera_index}: Failed to read frame")
            break

        time.sleep(0.1)  # Small delay

    cap.release()
    elapsed = time.time() - start_time
    print(".2f")

# Test both cameras
test_camera_stream(0)
test_camera_stream(1)