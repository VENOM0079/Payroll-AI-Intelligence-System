
import sqlite3
import cv2
import threading
import time
from facial_recognition import FaceRecognitionSystem
from database import Database
from datetime import datetime


class IPCameraSystem:
    def __init__(self, camera_url=0):  # 0 for default camera, or RTSP URL for IP camera
        self.capture_thread = None
        self.camera_url = camera_url
        self.face_system = FaceRecognitionSystem()
        self.db = Database()
        self.is_running = False
        self.current_frame = None

    def start_capture(self):
        """Start camera capture in separate thread"""
        self.is_running = True
        self.capture_thread = threading.Thread(target=self._capture_loop)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        self.db.log_event('INFO', 'Camera', 'Camera capture started')

    def stop_capture(self):
        """Stop camera capture"""
        self.is_running = False
        self.db.log_event('INFO', 'Camera', 'Camera capture stopped')

    def _capture_loop(self):
        """Main capture loop"""
        cap = cv2.VideoCapture(self.camera_url)

        while self.is_running:
            ret, frame = cap.read()
            if ret:
                # Process frame for face recognition
                processed_frame, recognized_employees = self.face_system.recognize_face(frame)
                self.current_frame = processed_frame

                # Record attendance for recognized employees
                for employee_id in recognized_employees:
                    self.record_attendance(employee_id)

                # Display frame (optional)
                cv2.imshow('Payroll System - Face Recognition', processed_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            time.sleep(1)  # Process 1 frame per second

        cap.release()
        cv2.destroyAllWindows()

    def record_attendance(self, employee_id):
        """Record employee attendance"""
        try:
            current_time = datetime.now()
            today = current_time.date()

            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()

            # Check if already recorded today
            cursor.execute(
                'SELECT id, time_in, time_out FROM attendance WHERE employee_id = ? AND date = ?',
                (employee_id, today)
            )
            record = cursor.fetchone()

            if not record:
                # First entry today - record time_in
                cursor.execute(
                    'INSERT INTO attendance (employee_id, date, time_in) VALUES (?, ?, ?)',
                    (employee_id, today, current_time)
                )
                self.db.log_event('INFO', 'Attendance', f'Time in recorded for {employee_id}')

                # Calculate late minutes
                self._calculate_late_minutes(employee_id, current_time)

            elif record[1] and not record[2]:
                # Time in recorded but no time out - record time_out
                cursor.execute(
                    'UPDATE attendance SET time_out = ? WHERE id = ?',
                    (current_time, record[0])
                )
                self.db.log_event('INFO', 'Attendance', f'Time out recorded for {employee_id}')

            conn.commit()
            conn.close()

        except Exception as e:
            self.db.log_event('ERROR', 'Attendance', f'Error recording attendance: {str(e)}')

    def _calculate_late_minutes(self, employee_id, time_in):
        """Calculate late minutes based on shift timing"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()

        cursor.execute(
            'SELECT shift_start FROM staff WHERE employee_id = ?',
            (employee_id,)
        )
        result = cursor.fetchone()

        if result:
            shift_start_str = result[0]
            shift_start = datetime.strptime(shift_start_str, '%H:%M:%S').time()
            time_in_time = time_in.time()

            if time_in_time > shift_start:
                late_minutes = (datetime.combine(time_in.date(), time_in_time) -
                                datetime.combine(time_in.date(), shift_start)).seconds // 60

                cursor.execute(
                    'UPDATE attendance SET late_minutes = ? WHERE employee_id = ? AND date = ?',
                    (late_minutes, employee_id, time_in.date())
                )

                self.db.log_event('INFO', 'Attendance',
                                  f'Late minutes calculated: {late_minutes} for {employee_id}')

        conn.commit()
        conn.close()