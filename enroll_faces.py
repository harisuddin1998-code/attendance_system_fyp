import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"
import sqlite3
import cv2
import numpy as np
from deepface import DeepFace

# Configuration
DATASET_DIR = "dataset"
DB_PATH = "attendance.db"
# VGG-Face gives highly distinct embeddings
MODEL_NAME = "VGG-Face" 

def init_db():
    """Initializes the SQLite database and creates the students table if it doesn't exist."""
    print(f"Initializing database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            embedding BLOB NOT NULL
        )
    ''')
    conn.commit()
    return conn

def get_embedding(img_path):
    """Extracts a 128-d embedding from an image using DeepFace."""
    try:
        # DeepFace represent returns a list of dictionaries (one for each detected face)
        results = DeepFace.represent(img_path=img_path, model_name=MODEL_NAME, enforce_detection=True)
        if len(results) == 0:
            return None
        # Get the first face's embedding
        embedding = results[0]["embedding"]
        return embedding
    except ValueError as e:
        print(f"Face could not be detected in {img_path}. Error: {e}")
        return None
    except Exception as e:
        print(f"Error processing {img_path}: {e}")
        return None

def enroll_students(conn):
    """Reads images from DATASET_DIR and enrolls them into the database."""
    if not os.path.exists(DATASET_DIR):
        os.makedirs(DATASET_DIR)
        print(f"Created '{DATASET_DIR}' directory. Please place student images inside it.")
        return

    cursor = conn.cursor()
    
    # We expect files to be named like "StudentID_StudentName.jpg"
    # Example: "S231_Ali.jpg"
    files = [f for f in os.listdir(DATASET_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    if not files:
        print(f"No images found in '{DATASET_DIR}/'. Please add some images and run again.")
        return

    for filename in files:
        filepath = os.path.join(DATASET_DIR, filename)
        
        # Parse filename (e.g., S231_Ali.jpg -> "S231", "Ali")
        name_parts = os.path.splitext(filename)[0].split("_", 1)
        if len(name_parts) != 2:
            print(f"Skipping {filename}: filename format must be 'StudentID_StudentName.jpg'")
            continue
            
        student_id, student_name = name_parts
        
        print(f"Processing {student_name} (ID: {student_id})...")
        
        # Extract Embedding
        embedding_list = get_embedding(filepath)
        
        if embedding_list is None:
            print(f"Failed to extract embedding for {filename}.")
            continue
            
        # Optional validation
        if len(embedding_list) != 128:
            print(f"Warning: Expected 128-d embedding, got {len(embedding_list)}-d for {filename}. Using {MODEL_NAME}.")
        
        # Convert list to numpy float32 array, then to bytes for BLOB storage
        embedding_np = np.array(embedding_list, dtype='float32')
        embedding_blob = embedding_np.tobytes()
        
        try:
            cursor.execute('''
                INSERT INTO students (student_id, name, embedding)
                VALUES (?, ?, ?)
            ''', (student_id, student_name, embedding_blob))
            conn.commit()
            print(f"Successfully enrolled {student_name}.")
        except sqlite3.IntegrityError:
            print(f"Student ID {student_id} is already enrolled. Updating embedding...")
            cursor.execute('''
                UPDATE students
                SET name = ?, embedding = ?
                WHERE student_id = ?
            ''', (student_name, embedding_blob, student_id))
            conn.commit()
            print(f"Successfully updated {student_name}.")

if __name__ == "__main__":
    db_conn = init_db()
    
    print(f"--- Starting enrollment process ---")
    print(f"Expected image format: {DATASET_DIR}/StudentID_StudentName.jpg (e.g., dataset/S123_Ali.jpg)")
    print(f"-----------------------------------")
    
    enroll_students(db_conn)
    db_conn.close()
    
    print("Enrollment process finished.")
