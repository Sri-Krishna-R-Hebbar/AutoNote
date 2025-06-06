import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
DATA_FILE = "../test_dataset.json"
OUTPUT_DIR = "processed_notes"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def generate_notes_with_gemini(transcription):
    """Sends transcription to Gemini API to generate structured notes."""
    prompt = f"""Please convert the following lecture/meeting transcription into well-structured, detailed notes. 
    Follow these guidelines:
    1. Create clear main topics and subtopics with proper hierarchy
    2. Use bullet points for key concepts and examples
    3. Highlight important definitions and formulas
    4. Include relevant examples and explanations
    5. Add section headers and subheaders
    6. Format mathematical equations clearly
    7. Use markdown formatting for better readability
    8. Include a summary at the end of each major section
    9. Add a table of contents at the beginning
    
    Transcription:
    {transcription}
    
    Please format the output in markdown with proper headings, bullet points, and sections."""

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", json=payload, headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        return result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    else:
        print(f"Error {response.status_code}: {response.text}")
        return ""

def list_available_models():
    """Lists available models from the Gemini API."""
    response = requests.get(f"https://generativelanguage.googleapis.com/v1/models?key={GEMINI_API_KEY}")
    if response.status_code == 200:
        models = response.json()
        print("Available models:", models)
    else:
        print(f"Error {response.status_code}: {response.text}")

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load dataset
with open(DATA_FILE, "r", encoding="utf-8") as f:
    dataset = json.load(f)

# Process each transcription
for entry in dataset:
    audio_path = entry.get("audio")
    transcription = entry.get("text", "").strip()
    
    if not transcription:
        print(f"Skipping {audio_path} (empty transcription)")
        continue
    
    # Extract video name
    video_folder = Path(audio_path).parent.name
    file_name = Path(audio_path).stem
    
    # Create output directory for video
    video_output_dir = os.path.join(OUTPUT_DIR, video_folder)
    os.makedirs(video_output_dir, exist_ok=True)
    
    # Generate notes using Gemini API
    structured_notes = generate_notes_with_gemini(transcription)
    
    # Save notes to markdown file
    note_path = os.path.join(video_output_dir, f"{file_name}.md")
    with open(note_path, "w", encoding="utf-8") as f:
        f.write(structured_notes)
    
    print(f"Saved notes for {audio_path} -> {note_path}")

print("✅ Notes generation complete using Gemini!")