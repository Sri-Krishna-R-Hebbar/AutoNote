import sys
from moviepy.editor import VideoFileClip

def extract_audio_segments(video_path, wav_path):
    video = VideoFileClip(video_path)
    audio = video.audio
    audio.write_audiofile(wav_path)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python mp4 to wav.py <input_video_path> <output_wav_path>")
        sys.exit(1)
    video_path = sys.argv[1]
    wav_path = sys.argv[2]
    extract_audio_segments(video_path, wav_path)