import cv2
import requests
import socket

def get_local_ip():
    """Get local IP address"""
    try:
        # Create a socket to get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "192.168.1.100"  # fallback

def test_mobile_camera(url):
    """Test if mobile camera URL is accessible"""
    try:
        # Try to open with OpenCV
        cap = cv2.VideoCapture(url)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                print(f"✅ Camera accessible at {url}")
                print(f"   Frame size: {frame.shape}")
                cap.release()
                return True
            else:
                print(f"❌ Camera opened but no frame received: {url}")
        else:
            print(f"❌ Cannot open camera: {url}")

        cap.release()
        return False
    except Exception as e:
        print(f"❌ Error testing camera {url}: {e}")
        return False

def find_mobile_cameras():
    """Help user find their mobile camera IPs"""
    local_ip = get_local_ip()
    print(f"Your local IP: {local_ip}")
    print("\n🔍 Testing common mobile camera URLs...")

    # Common IP ranges and ports for mobile cameras
    base_ip = ".".join(local_ip.split(".")[:-1])  # Get network prefix

    test_urls = [
        f"http://{base_ip}.100:4747/video",  # DroidCam default
        f"http://{base_ip}.101:4747/video",
        f"http://{base_ip}.102:4747/video",
        f"http://{base_ip}.100:8080/video",  # IP Webcam default
        f"http://{base_ip}.101:8080/video",
        f"http://{base_ip}.102:8080/video",
    ]

    working_urls = []
    for url in test_urls:
        if test_mobile_camera(url):
            working_urls.append(url)

    print(f"\n📱 Found {len(working_urls)} working camera(s)")
    for i, url in enumerate(working_urls, 1):
        print(f"   Camera {i}: {url}")

    if not working_urls:
        print("\n❌ No cameras found. Please check:")
        print("   1. Both phones have camera apps running (DroidCam/IP Webcam)")
        print("   2. Phones are on the same WiFi network")
        print("   3. Firewall allows camera connections")
        print("   4. Try manual IP entry if auto-detection fails")

    return working_urls

if __name__ == "__main__":
    print("🔍 Mobile Camera Detection Tool")
    print("=" * 40)
    find_mobile_cameras()