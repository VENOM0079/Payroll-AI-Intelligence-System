import sqlite3
from datetime import datetime
import os


class Database:
    def __init__(self, db_path='payroll.db'):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Staff table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staff (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                department TEXT NOT NULL,
                position TEXT NOT NULL,
                salary REAL NOT NULL,
                shift_start TIME NOT NULL,
                shift_end TIME NOT NULL,
                face_embedding BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Attendance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT NOT NULL,
                date DATE NOT NULL,
                time_in TIMESTAMP,
                time_out TIMESTAMP,
                late_minutes INTEGER DEFAULT 0,
                overtime_minutes INTEGER DEFAULT 0,
                status TEXT DEFAULT 'Present',
                FOREIGN KEY (employee_id) REFERENCES staff (employee_id)
            )
        ''')

        # Payroll table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payroll (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT NOT NULL,
                month_year TEXT NOT NULL,
                basic_salary REAL NOT NULL,
                late_deductions REAL DEFAULT 0,
                overtime_bonus REAL DEFAULT 0,
                net_salary REAL NOT NULL,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employee_id) REFERENCES staff (employee_id)
            )
        ''')

        # System logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                level TEXT NOT NULL,
                module TEXT NOT NULL,
                message TEXT NOT NULL
            )
        ''')

        conn.commit()
        conn.close()

    def log_event(self, level, module, message):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO system_logs (level, module, message) VALUES (?, ?, ?)',
            (level, module, message)
        )
        conn.commit()
        conn.close()