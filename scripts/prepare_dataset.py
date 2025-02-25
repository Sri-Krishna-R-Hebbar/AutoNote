import os
import json
from tqdm import tqdm

# Path to preprocessed audio
data_dir = "processed_audio"
dataset_output = "dataset.json"

def create_dataset():
    dataset = []
    # Loop through video folders
    for video in os.listdir(data_dir):
        video_path = os.path.join(data_dir, video)
        
        if os.path.isdir(video_path):
            for file in sorted(os.listdir(video_path)):
                if file.endswith(".wav"):
                    file_path = os.path.join(video_path, file)
                    
                    # Placeholder transcription (to be replaced with Whisper-generated text)
                    transcription = ""
                    
                    dataset.append({
                        "audio": file_path,
                        "text": transcription
                    })
    
    # Save dataset file
    with open(dataset_output, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=4)
    
    print(f"Dataset saved at {dataset_output}")

if __name__ == "__main__":
    create_dataset()
