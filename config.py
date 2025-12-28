import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    DATABASE_PATH = 'payroll.db'
    CAMERA_URL = 0  # 0 for default camera, or 'rtsp://username:password@ip:port/stream'

    # HR Policies
    WORKING_HOURS_PER_DAY = 8
    WORKING_DAYS_PER_MONTH = 22
    OVERTIME_RATE = 1.5  # 1.5x normal rate
    LATE_DEDUCTION_RATE = 1.0  # 1x hourly rate per hour late