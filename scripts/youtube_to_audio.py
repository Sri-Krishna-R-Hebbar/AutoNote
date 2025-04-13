import yt_dlp
import os

def download_youtube_audio_as_wav(url, output_path='youtube_audio_files', filename='audio'):
    try:
        # Create folder if it doesn't exist
        os.makedirs(output_path, exist_ok=True)

        wav_path = os.path.join(output_path, filename + '.wav')

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(output_path, filename + '.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        print(f"✅ Done! Audio saved at: {wav_path}")

    except Exception as e:
        print(f"❌ Error: {e}")

# Example usage
download_youtube_audio_as_wav("https://www.youtube.com/watch?v=q8oj7A38IeU", filename="my_audio")
