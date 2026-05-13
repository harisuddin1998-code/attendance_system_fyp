import cv2
import os

DATASET_DIR = "dataset"
if not os.path.exists(DATASET_DIR):
    os.makedirs(DATASET_DIR)

print("--- Naya Student Enroll Karein ---")
student_id = input("Student ID batayen (e.g., 2024): ").strip()
student_name = input("Student ka Naam batayen (e.g., Bilal): ").strip()

if not student_id or not student_name:
    print("Naam ya ID khali nahi ho sakti! Program band ho raha hai.")
    exit()

print(f"\nBht Khoob! Ab camera on ho raha hai '{student_name}' ke liye...")
print("Camera ke samne straight dekh kar 'SPACE' bar dabayein fresh photo lenk k liye. (Cancel k liye 'q' dabayein)")

CAMERA_URL = "rtsp://admin:YCSNFJ@192.168.0.100:554/Streaming/Channels/101" # Apka EZVIZ RTSP IP connection
cap = cv2.VideoCapture(CAMERA_URL)

while True:
    ret, frame = cap.read()
    if not ret:
        break
        
    cv2.putText(frame, f"Enrolling: {student_name} | Press SPACE to capture", (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    cv2.imshow("Live Enrollment Manager", frame)
    
    key = cv2.waitKey(1) & 0xFF
    if key == 32: # SPACE bar
        filepath = os.path.join(DATASET_DIR, f"{student_id}_{student_name}.jpg")
        cv2.imwrite(filepath, frame)
        print(f"\nPhoto kamyabi se capture ho gaii: {filepath}!")
        break
    elif key == ord('q'):
        print("\nEnrollment user ne cancel kardi.")
        cap.release()
        cv2.destroyAllWindows()
        exit()

cap.release()
cv2.destroyAllWindows()

# Automatically run enrollment to process this directly to DB
print(f"Database mein {student_name} ka face AI k zariye extract ho raha hai. Please wait...")
os.system(f'"{os.sys.executable}" enroll_faces.py')

print(f"\n✓ Mubarak ho! {student_name} database me save hogaya hai. Tracker mein test karen!")
