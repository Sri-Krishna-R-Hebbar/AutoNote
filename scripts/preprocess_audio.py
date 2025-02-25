import os
import librosa
import soundfile as sf
from pydub import AudioSegment

def convert_to_wav(input_path, output_path):
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_frame_rate(16000).set_channels(1)  # Convert to 16kHz Mono
    audio.export(output_path, format="wav")
    
def normalize_audio(input_path, output_path):
    y, sr = librosa.load(input_path, sr=16000)
    y_normalized = librosa.util.normalize(y)
    sf.write(output_path, y_normalized, sr)
    
def preprocess_audio_folder(input_folder, output_folder, video_name):
    video_output_folder = os.path.join(output_folder, video_name)
    if not os.path.exists(video_output_folder):
        os.makedirs(video_output_folder)
    
    # Look specifically in the audio subfolder
    if os.path.exists(input_folder):
        for file in os.listdir(input_folder):
            input_path = os.path.join(input_folder, file)
            output_path = os.path.join(video_output_folder, file.split('.')[0] + ".wav")
            
            try:
                convert_to_wav(input_path, output_path)
                normalize_audio(output_path, output_path)
                print(f"Processed: {file} -> {output_path}")
            except Exception as e:
                print(f"Error processing {file}: {e}")

# Loop through all video folders
data_folder = "data/audio"  # Updated to point directly to the audio folder
processed_folder = "processed_audio"  # Base output folder

# Ensure processed_audio folder exists
if not os.path.exists(processed_folder):
    os.makedirs(processed_folder)

for video_folder in os.listdir(data_folder):
    input_folder = os.path.join(data_folder, video_folder)
    
    if os.path.isdir(input_folder):
        print(f"Processing {video_folder}...")
        preprocess_audio_folder(input_folder, processed_folder, video_folder)
    else:
        print(f"Skipping {video_folder}, not a directory.")