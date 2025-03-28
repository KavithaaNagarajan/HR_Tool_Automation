import os
import subprocess
import time
import requests
import logging
import psutil
from flask import Flask, request, jsonify, render_template_string
import spacy

# Reduce Flask logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

# Define file storage paths
UPLOAD_FOLDER = "uploads"
JD_UPLOAD_FOLDER = "jd_uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(JD_UPLOAD_FOLDER, exist_ok=True)

# Python & Streamlit Paths
PYTHON_PATH = r"C:\Users\inc3061\OneDrive - Texila American University\Documents\Resumepath\Scripts\python.exe"
SCRIPT_PATH = r"C:\Users\inc3061\OneDrive - Texila American University\Documents\Resumepath\Data_Flask_Task\New_Parser\Functions\script.py"
STREAMLIT_PORT = 8503
FLASK_PORT = 5000

# Function to check if Streamlit is running
def is_streamlit_running():
    """Check if Streamlit is already running on the given port."""
    for conn in psutil.net_connections(kind="inet"):
        if conn.laddr.port == STREAMLIT_PORT:
            return True
    return False

# Function to start Streamlit
def start_streamlit():
    """Start Streamlit if not already running."""
    if is_streamlit_running():
        return

    if not os.path.exists(SCRIPT_PATH):
        print(f"Error: Streamlit script not found at {SCRIPT_PATH}")
        return

    print(f"Starting Streamlit on port {STREAMLIT_PORT}...")
    process = subprocess.Popen(
        [PYTHON_PATH, "-m", "streamlit", "run", SCRIPT_PATH,
         "--server.port", str(STREAMLIT_PORT),
         "--server.headless", "true",
         "--server.enableCORS", "false",
         "--server.enableXsrfProtection", "false"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    for _ in range(10):
        try:
            response = requests.get(f"http://localhost:{STREAMLIT_PORT}")
            if response.status_code == 200:
                print(f"Streamlit started at: http://127.0.0.1:{STREAMLIT_PORT}")
                return
        except requests.exceptions.ConnectionError:
            time.sleep(1)

    print("Error: Streamlit did not start properly!")
    process.kill()  # Kill Streamlit process if it failed to start

# Flask Route to Embed Streamlit
@app.route("/")
def home():
    """Embed Streamlit app inside Flask using an iframe."""
    start_streamlit()
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ text-align: center; font-family: Arial, sans-serif; }}
            iframe {{ width: 100%; height: 90vh; border: none; }}
        </style>
    </head>
    <body>
    
        <iframe src="http://localhost:{STREAMLIT_PORT}/?embed=true"></iframe>
    </body>
    </html>
    """
    return render_template_string(html)

# File Upload API (Resume)
@app.route('/upload_resume', methods=['POST'])
def upload_resume():
    """Handles resume uploads."""
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    safe_filename = sanitize_filename(file.filename)
    if not safe_filename:
        return jsonify({"error": "Invalid filename"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, safe_filename)

    try:
        file.save(file_path)
        print(f"Saved resume: {file_path}")
        return jsonify({"message": "Resume uploaded successfully"}), 200
    except OSError as e:
        print(f"Error saving file: {e}")
        return jsonify({"error": "Failed to save file"}), 500

# File Upload API (Job Descriptions)
@app.route('/upload_jd', methods=['POST'])
def upload_jd():
    """Handles JD uploads."""
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    safe_filename = sanitize_filename(file.filename)
    if not safe_filename:
        return jsonify({"error": "Invalid filename"}), 400

    file_path = os.path.join(JD_UPLOAD_FOLDER, safe_filename)

    try:
        file.save(file_path)
        print(f"Saved job description: {file_path}")
        return jsonify({"message": "Job description uploaded successfully"}), 200
    except OSError as e:
        print(f"Error saving file: {e}")
        return jsonify({"error": "Failed to save file"}), 500

def sanitize_filename(filename):
    """Remove invalid characters from filenames and return a safe filename."""
    import re
    filename = filename.strip()
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)  # Remove invalid characters
    return filename if filename else None

# Run Flask Server
if __name__ == "__main__":
    print(f"Flask Server Running at: http://127.0.0.1:{FLASK_PORT}")
    try:
        app.run(host="0.0.0.0", port=FLASK_PORT, debug=True)
    except Exception as e:
        print(f"Flask Server Error: {e}")
