from flask import Flask, render_template, request, send_file, jsonify
import os
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import subprocess
import uuid
import time

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'mp4'}

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('processed_notes', exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        # Generate unique ID for this processing job
        job_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{filename}")
        file.save(video_path)
        
        # Start processing in background
        try:
            # Run the processing pipeline
            subprocess.Popen(['python', 'process_video.py', video_path, job_id])
            return jsonify({
                'message': 'Video uploaded successfully',
                'job_id': job_id
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/status/<job_id>')
def get_status(job_id):
    # Check if PDF exists
    pdf_path = os.path.join('processed_notes', f'{job_id}_notes.pdf')
    if os.path.exists(pdf_path):
        return jsonify({
            'status': 'completed',
            'download_url': f'/download/{job_id}'
        })
    return jsonify({'status': 'processing'})

@app.route('/download/<job_id>')
def download_file(job_id):
    pdf_path = os.path.join('processed_notes', f'{job_id}_notes.pdf')
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    app.run(debug=True) 