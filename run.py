from app import app, camera_system
import threading


def start_system():
    # Initialize and start camera system in separate thread
    camera_thread = threading.Thread(target=camera_system.start_capture)
    camera_thread.daemon = True
    camera_thread.start()

    # Start Flask application
    app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=True)


if __name__ == '__main__':
    start_system()