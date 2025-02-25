import json
import torch
import librosa
import soundfile as sf
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

# Load Wav2Vec2 model and processor
MODEL_NAME = "facebook/wav2vec2-large-960h"
device = "cuda" if torch.cuda.is_available() else "cpu"
processor = Wav2Vec2Processor.from_pretrained(MODEL_NAME)
model = Wav2Vec2ForCTC.from_pretrained(MODEL_NAME).to(device)

def transcribe_audio(audio_path):
    # Load and preprocess audio
    speech, sr = librosa.load(audio_path, sr=16000)
    input_values = processor(speech, return_tensors="pt", sampling_rate=16000).input_values.to(device)
    
    # Perform inference
    with torch.no_grad():
        logits = model(input_values).logits
    
    # Decode predicted tokens to text
    predicted_ids = torch.argmax(logits, dim=-1)
    transcription = processor.batch_decode(predicted_ids)[0]
    return transcription

# Load dataset
with open("dataset.json", "r", encoding="utf-8") as f:
    dataset = json.load(f)

# Transcribe each audio file
for entry in dataset:
    print(f"Transcribing: {entry['audio']}")
    entry["text"] = transcribe_audio(entry["audio"])

# Save updated dataset
with open("dataset.json", "w", encoding="utf-8") as f:
    json.dump(dataset, f, indent=4)

print("Transcription complete! Updated dataset saved.")
