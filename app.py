from flask import Flask, render_template, request, jsonify, send_file
from database import Database
from facial_recognition import FaceRecognitionSystem
from camera import IPCameraSystem
import sqlite3
from datetime import datetime, timedelta
import csv
import io

app = Flask(__name__)
db = Database()
face_system = FaceRecognitionSystem()
camera_system = IPCameraSystem()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    """Main dashboard"""
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()

    # Get today's attendance stats
    cursor.execute('''
        SELECT COUNT(*) as total, 
               SUM(CASE WHEN time_in IS NOT NULL THEN 1 ELSE 0 END) as present
        FROM attendance 
        WHERE date = date('now')
    ''')
    stats = cursor.fetchone()

    # Get recent attendance
    cursor.execute('''
        SELECT a.employee_id, s.name, a.time_in, a.time_out, a.late_minutes
        FROM attendance a
        JOIN staff s ON a.employee_id = s.employee_id
        WHERE a.date = date('now')
        ORDER BY a.time_in DESC
        LIMIT 10
    ''')
    recent_attendance = cursor.fetchall()

    conn.close()

    return render_template('dashboard.html',
                           total_employees=stats[0],
                           present_today=stats[1],
                           recent_attendance=recent_attendance)


@app.route('/staff')
def staff_management():
    """Staff management page"""
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM staff')
    staff_members = cursor.fetchall()
    conn.close()

    return render_template('staff.html', staff_members=staff_members)


@app.route('/api/staff', methods=['POST'])
def add_staff():
    """Add new staff member"""
    data = request.json
    try:
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO staff (employee_id, name, department, position, salary, shift_start, shift_end)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (data['employee_id'], data['name'], data['department'],
              data['position'], data['salary'], data['shift_start'], data['shift_end']))
        conn.commit()
        conn.close()

        db.log_event('INFO', 'Staff', f'Added staff member: {data["employee_id"]}')
        return jsonify({'success': True, 'message': 'Staff member added successfully'})
    except Exception as e:
        db.log_event('ERROR', 'Staff', f'Error adding staff: {str(e)}')
        return jsonify({'success': False, 'message': str(e)})


@app.route('/attendance')
def attendance_view():
    """Attendance records page"""
    date_filter = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))

    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.*, s.name, s.department
        FROM attendance a
        JOIN staff s ON a.employee_id = s.employee_id
        WHERE a.date = ?
        ORDER BY a.time_in DESC
    ''', (date_filter,))
    attendance_records = cursor.fetchall()
    conn.close()

    return render_template('attendance.html',
                           attendance_records=attendance_records,
                           selected_date=date_filter)


@app.route('/payroll')
def payroll_management():
    """Payroll management page"""
    month_year = request.args.get('month_year', datetime.now().strftime('%Y-%m'))

    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.*, s.name
        FROM payroll p
        JOIN staff s ON p.employee_id = s.employee_id
        WHERE p.month_year = ?
        ORDER BY s.name
    ''', (month_year,))
    payroll_records = cursor.fetchall()
    conn.close()

    return render_template('payroll.html',
                           payroll_records=payroll_records,
                           selected_month=month_year)


@app.route('/api/generate_payroll', methods=['POST'])
def generate_payroll():
    """Generate payroll for all employees for given month"""
    data = request.json
    month_year = data.get('month_year', datetime.now().strftime('%Y-%m'))

    try:
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()

        # Get all staff
        cursor.execute('SELECT employee_id, salary FROM staff')
        staff_members = cursor.fetchall()

        for employee_id, salary in staff_members:
            # Calculate attendance metrics for the month
            cursor.execute('''
                SELECT SUM(late_minutes), SUM(overtime_minutes)
                FROM attendance 
                WHERE employee_id = ? AND strftime('%Y-%m', date) = ?
            ''', (employee_id, month_year))
            result = cursor.fetchone()

            late_minutes = result[0] or 0
            overtime_minutes = result[1] or 0

            # Calculate deductions and bonuses
            hourly_rate = salary / (22 * 8)  # Assuming 22 working days, 8 hours per day
            late_deductions = (late_minutes / 60) * hourly_rate
            overtime_bonus = (overtime_minutes / 60) * hourly_rate * 1.5  # 1.5x for overtime

            net_salary = salary - late_deductions + overtime_bonus

            # Insert or update payroll record
            cursor.execute('''
                INSERT OR REPLACE INTO payroll 
                (employee_id, month_year, basic_salary, late_deductions, overtime_bonus, net_salary)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (employee_id, month_year, salary, late_deductions, overtime_bonus, net_salary))

        conn.commit()
        conn.close()

        db.log_event('INFO', 'Payroll', f'Payroll generated for {month_year}')
        return jsonify({'success': True, 'message': 'Payroll generated successfully'})

    except Exception as e:
        db.log_event('ERROR', 'Payroll', f'Error generating payroll: {str(e)}')
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/upload_face', methods=['POST'])
def upload_face_image():
    """Upload face image for employee"""
    if 'file' not in request.files or 'employee_id' not in request.form:
        return jsonify({'success': False, 'message': 'Missing file or employee ID'})

    file = request.files['file']
    employee_id = request.form['employee_id']

    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})

    # Save uploaded file temporarily
    temp_path = f'temp_{employee_id}.jpg'
    file.save(temp_path)

    # Add face to recognition system
    success = face_system.add_employee_face(temp_path, employee_id)

    # Clean up temp file
    import os
    os.remove(temp_path)

    if success:
        return jsonify({'success': True, 'message': 'Face added successfully'})
    else:
        return jsonify({'success': False, 'message': 'Failed to process face image'})


@app.route('/logs')
def system_logs():
    """System logs page"""
    level_filter = request.args.get('level', '')

    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()

    if level_filter:
        cursor.execute('''
            SELECT * FROM system_logs 
            WHERE level = ? 
            ORDER BY timestamp DESC 
            LIMIT 100
        ''', (level_filter,))
    else:
        cursor.execute('''
            SELECT * FROM system_logs 
            ORDER BY timestamp DESC 
            LIMIT 100
        ''')

    logs = cursor.fetchall()
    conn.close()

    return render_template('logs.html', logs=logs, selected_level=level_filter)


if __name__ == '__main__':
    # Start camera system
    camera_system.start_capture()

    # Start Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)