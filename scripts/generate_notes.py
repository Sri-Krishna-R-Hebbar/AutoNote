import os
import json
import re
from pathlib import Path

# Input and output paths
data_file = "dataset.json"
output_dir = "processed_notes"

# Ensure output directory existsimport os
import json
import re
from pathlib import Path

# Input and output paths
data_file = "dataset.json"
output_dir = "processed_notes"

# Ensure output directory exists
os.makedirs(output_dir, exist_ok=True)

def format_transcription(text):
    """Formats transcription into structured notes with headings, bullet points, and paragraphs."""
    
    # Split into sentences
    sentences = re.split(r'(?<=\.)\s+', text)
    
    # Create structured notes
    formatted_text = "# Summary of the Video\n\n"
    formatted_text += "## Key Points\n\n"
    
    for i, sentence in enumerate(sentences, start=1):
        formatted_text += f"- {sentence}\n"
    
    formatted_text += "\n## Detailed Explanation\n\n"
    formatted_text += "\n".join(sentences)
    
    return formatted_text

# Load dataset
with open(data_file, "r", encoding="utf-8") as f:
    dataset = json.load(f)

# Process each entry
for entry in dataset:
    audio_path = entry["audio"]
    transcription = entry["text"].strip()
    
    # Skip empty transcriptions
    if not transcription:
        print(f"Skipping {audio_path} (empty transcription)")
        continue
    
    # Extract video name
    video_folder = Path(audio_path).parent.name
    file_name = Path(audio_path).stem
    
    # Create output directory for video
    video_output_dir = os.path.join(output_dir, video_folder)
    os.makedirs(video_output_dir, exist_ok=True)
    
    # Format notes
    formatted_notes = format_transcription(transcription)
    
    # Save to markdown file
    note_path = os.path.join(video_output_dir, f"{file_name}.md")
    with open(note_path, "w", encoding="utf-8") as f:
        f.write(formatted_notes)
    
    print(f"Saved notes for {audio_path} -> {note_path}")

print("✅ Notes generation complete! Skipped empty transcriptions.")

os.makedirs(output_dir, exist_ok=True)

def format_transcription(text):
    """Formats transcription into structured notes with headings, bullet points, and paragraphs."""
    
    # Split into sentences
    sentences = re.split(r'(?<=\.)\s+', text)
    
    # Create structured notes
    formatted_text = "# Summary of the Video\n\n"
    formatted_text += "## Key Points\n\n"
    
    for i, sentence in enumerate(sentences, start=1):
        formatted_text += f"- {sentence}\n"
    
    formatted_text += "\n## Detailed Explanation\n\n"
    formatted_text += "\n".join(sentences)
    
    return formatted_text

# Load dataset
with open(data_file, "r", encoding="utf-8") as f:
    dataset = json.load(f)

# Process each entry
for entry in dataset:
    audio_path = entry["audio"]
    transcription = entry["text"].strip()
    
    # Skip empty transcriptions
    if not transcription:
        print(f"Skipping {audio_path} (empty transcription)")
        continue
    
    # Extract video name
    video_folder = Path(audio_path).parent.name
    file_name = Path(audio_path).stem
    
    # Create output directory for video
    video_output_dir = os.path.join(output_dir, video_folder)
    os.makedirs(video_output_dir, exist_ok=True)
    
    # Format notes
    formatted_notes = format_transcription(transcription)
    
    # Save to markdown file
    note_path = os.path.join(video_output_dir, f"{file_name}.md")
    with open(note_path, "w", encoding="utf-8") as f:
        f.write(formatted_notes)
    
    print(f"Saved notes for {audio_path} -> {note_path}")

print("✅ Notes generation complete! Skipped empty transcriptions.")
