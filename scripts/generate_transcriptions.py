import json
import torch
import librosa
import soundfile as sf
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor, WhisperForConditionalGeneration, WhisperProcessor

# Load Wav2Vec2 model and processor
MODEL_NAME = "openai/whisper-large-v2"
device = "cuda" if torch.cuda.is_available() else "cpu"

if "whisper" in MODEL_NAME:
    processor = WhisperProcessor.from_pretrained(MODEL_NAME)
    model = WhisperForConditionalGeneration.from_pretrained(MODEL_NAME).to(device)
else:
    processor = Wav2Vec2Processor.from_pretrained(MODEL_NAME)
    model = Wav2Vec2ForCTC.from_pretrained(MODEL_NAME).to(device)


def transcribe_audio(audio_data): # Change the input parameter to expect data
    """Transcribes audio data using the selected model."""

    # Load and preprocess audio

    speech = audio_data # Already loaded
    sr = 16000  # Sample rate (librosa used this when it loaded the file)


    # Process audio based on model type
    if "whisper" in MODEL_NAME:
        input_features = processor(speech, return_tensors="pt", sampling_rate=16000).input_features.to(device)
        predicted_ids = model.generate(input_features)
        transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]
    else:
        # wav2vec2 needs to process the raw audio data
        input_values = processor(speech, return_tensors="pt", sampling_rate=16000).input_values.to(device)

        with torch.no_grad():
            logits = model(input_values).logits
        predicted_ids = torch.argmax(logits, dim=-1)
        transcription = processor.batch_decode(predicted_ids)[0]

    return transcription

def transcribe_long_audio(audio_path, chunk_duration=30):
    speech, sr = librosa.load(audio_path, sr=16000)
    total_duration = librosa.get_duration(y=speech, sr=sr)
    num_chunks = int(total_duration / chunk_duration) + 1
    full_transcription = ""
    for i in range(num_chunks):
        start_time = i * chunk_duration
        end_time = min((i + 1) * chunk_duration, total_duration)

        chunk = speech[int(start_time * sr):int(end_time * sr)]

        transcription = transcribe_audio(chunk)  # Assuming transcribe_audio is modified to accept audio data
        full_transcription += transcription + " "

    return full_transcription

# Load dataset
with open("dataset.json", "r", encoding="utf-8") as f:
    dataset = json.load(f)

# Transcribe each audio file
for entry in dataset:
    print(f"Transcribing: {entry['audio']}")
    entry["text"] = transcribe_long_audio(entry["audio"])

with open("dataset.json", "w", encoding="utf-8") as f:
    json.dump(dataset, f, indent=4)

print("Transcription complete! Updated dataset saved.")
