import os
import librosa
import torch
import torchaudio
from datasets import load_dataset, DatasetDict, Audio

# Define dataset loading function
def load_audio_dataset(data_folder):
    audio_files = []
    for video_folder in os.listdir(data_folder):
        video_path = os.path.join(data_folder, video_folder)
        if os.path.isdir(video_path):
            for file in os.listdir(video_path):
                if file.endswith(".wav"):
                    audio_files.append({"path": os.path.join(video_path, file)})
    return audio_files

# Convert file list into Hugging Face Dataset
def create_hf_dataset(audio_files):
    dataset = DatasetDict({
        "train": load_dataset("audio", data_files=[file["path"] for file in audio_files], split="train")
    })
    return dataset

# Load dataset
data_folder = "processed_audio"
audio_files = load_audio_dataset(data_folder)
asr_dataset = create_hf_dataset(audio_files)

# Apply audio transformation
asr_dataset = asr_dataset.cast_column("audio", Audio(sampling_rate=16000))

# Check dataset
print(asr_dataset)
