# facial_recognition.py
import face_recognition
import cv2
import numpy as np
import pickle
import sqlite3
from database import Database
import os


class FaceRecognitionSystem:
    def __init__(self):
        self.db = Database()
        self.known_face_encodings = []
        self.known_face_ids = []
        self.load_known_faces()

    def load_known_faces(self):
        """Load face encodings from database"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT employee_id, face_embedding FROM staff WHERE face_embedding IS NOT NULL')

        for row in cursor.fetchall():
            employee_id, embedding_blob = row
            embedding = pickle.loads(embedding_blob)
            self.known_face_encodings.append(embedding)
            self.known_face_ids.append(employee_id)

        conn.close()
        self.db.log_event('INFO', 'FaceRecognition', f'Loaded {len(self.known_face_ids)} known faces')

    def add_employee_face(self, image_path, employee_id):
        """Add new employee face to system"""
        try:
            image = face_recognition.load_image_file(image_path)
            face_encodings = face_recognition.face_encodings(image)

            if len(face_encodings) == 0:
                self.db.log_event('ERROR', 'FaceRecognition', f'No face found in {image_path}')
                return False

            face_encoding = face_encodings[0]
            embedding_blob = pickle.dumps(face_encoding)

            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE staff SET face_embedding = ? WHERE employee_id = ?',
                (embedding_blob, employee_id)
            )
            conn.commit()
            conn.close()

            # Reload known faces
            self.load_known_faces()
            self.db.log_event('INFO', 'FaceRecognition', f'Added face for employee {employee_id}')
            return True

        except Exception as e:
            self.db.log_event('ERROR', 'FaceRecognition', f'Error adding face: {str(e)}')
            return False

    def recognize_face(self, frame):
        """Recognize face from camera frame"""
        try:
            # Resize frame for faster processing
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            # Find all faces in current frame
            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

            recognized_employees = []

            for face_encoding, face_location in zip(face_encodings, face_locations):
                # Compare with known faces
                matches = face_recognition.compare_faces(self.known_face_encodings, face_encoding)
                face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)

                best_match_index = np.argmin(face_distances) if len(face_distances) > 0 else -1

                if best_match_index != -1 and matches[best_match_index]:
                    employee_id = self.known_face_ids[best_match_index]
                    recognized_employees.append(employee_id)

                    # Scale face location back to original size
                    top, right, bottom, left = face_location
                    top *= 4;
                    right *= 4;
                    bottom *= 4;
                    left *= 4

                    # Draw bounding box
                    cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                    cv2.putText(frame, employee_id, (left, top - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            return frame, recognized_employees

        except Exception as e:
            self.db.log_event('ERROR', 'FaceRecognition', f'Recognition error: {str(e)}')
            return frame, []