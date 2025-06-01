import os
import sys
import subprocess
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_command(command):
    """Run a shell command and return its output."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        raise Exception(f"Command failed: {stderr.decode()}")
    return stdout.decode()

def process_video(video_path, job_id):
    """Process the video through the entire pipeline."""
    try:
        # 1. Convert MP4 to WAV
        wav_path = f"uploads/{job_id}_audio.wav"
        run_command(['python', 'scripts/mp4 to wav.py', video_path, wav_path])

        # 2. Preprocess audio
        run_command(['python', 'scripts/preprocess_audio.py', wav_path])

        # 3. Prepare dataset
        run_command(['python', 'scripts/prepare_dataset.py'])

        # 4. Generate transcriptions
        run_command(['python', 'scripts/generate_transcriptions.py'])

        # 5. Generate notes with Gemini
        run_command(['python', 'scripts/generate_notes_gemini.py'])

        # 6. Process video frames and OCR
        run_command(['python', 'scripts/video_to_notes.py', video_path])

        # 7. Combine and convert to PDF
        run_command(['python', 'scripts/combine_to_pdf.py'])

        # Move final PDF to processed_notes directory
        os.rename('processed_notes/combined_notes.pdf', f'processed_notes/{job_id}_notes.pdf')

        # Cleanup temporary files
        cleanup_files(job_id)

    except Exception as e:
        print(f"Error processing video: {str(e)}")
        cleanup_files(job_id)
        raise

def cleanup_files(job_id):
    """Clean up temporary files."""
    try:
        os.remove(f"uploads/{job_id}_audio.wav")
        os.remove(f"uploads/{job_id}_video.mp4")
    except:
        pass

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python process_video.py <video_path> <job_id>")
        sys.exit(1)

    video_path = sys.argv[1]
    job_id = sys.argv[2]
    process_video(video_path, job_id) 