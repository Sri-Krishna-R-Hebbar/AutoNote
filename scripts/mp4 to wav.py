import os
import math
from moviepy.editor import VideoFileClip
from pydub import AudioSegment

def extract_audio_segments(video_path):
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    output_folder = os.path.join("data/audio", video_name)  # Updated output path
    os.makedirs(output_folder, exist_ok=True)
    
    # Load the video and extract audio
    video = VideoFileClip(video_path)
    audio = video.audio
    audio_path = os.path.join(output_folder, f"{video_name}.wav")
    audio.write_audiofile(audio_path, codec='pcm_s16le')  # Save full audio file
    
    print(f"Saved full audio: {audio_path}")  # Updated print statement
    
    print("Audio extraction completed.")

# Example usage
extract_audio_segments("data/videos/video1/output.mp4") 
