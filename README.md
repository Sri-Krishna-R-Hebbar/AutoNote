# AutoNote 📝🎥  
Automatically convert lecture or meeting videos into clean, readable notes!

This project takes a `.mp4` video file and outputs summarized notes in a PDF using transcription and Gemini. It’s perfect for students or professionals who want quick notes from videos.

---

## 🔧 Setup

1. **Clone the repository**  
   ```bash
   git clone https://github.com/Sri-Krishna-R-Hebbar/AutoNote.git
   cd AutoNote
   ```

2. **Install dependencies**  
   Make sure you have Python 3.8+ installed, then run:  
   ```bash
   pip install -r requirements.txt
   ```

3. **Add your Gemini API key**  
   Save your Gemini API key in a `.env` file or place it directly where needed:  
   ```
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

---

## 📁 Folder Structure

Before running the scripts, **place your input video** at:  
```
data/video1/sample_video.mp4
```

All outputs including intermediate files and the final notes will be saved automatically.

---

## ▶️ How to Use

Just follow these 7 steps in order:

### 1. `mp4_to_wav.py`  
🎞️ ➡️ 🔊  
Converts the video file into an audio file (`.wav`).  
```bash
python '.\scripts\mp4 to wav.py'
```

### 2. `preprocess_audio.py`  
🔊 ✂️  
Splits the `.wav` file into smaller chunks for easier processing.  
```bash
python '.\scripts\preprocess_audio.py'
```

### 3. `prepare_dataset.py`  
📁 Organizes the audio chunks into a dataset format.  
```bash
python '.\scripts\prepare_dataset.py'
```

### 4. `generate_transcriptions.py`  
🗣️💬  
Uses a speech-to-text model (like Whisper) to transcribe each audio chunk.  
```bash
python '.\scripts\generate_transcriptions.py'
```

### 5. `generate_notes_gemini.py`  
💬➡️📝  
Sends the transcriptions to Gemini and gets clean, summarized notes for each.  
```bash
python '.\scripts\generate_notes_gemini.py'
```

### 6. `video_to_notes.py`  
🔁 All-in-One Script  
Runs all the above steps in one go.  
```bash
python '.\scripts\video_to_notes.py'
```

### 7. `combine_to_pdf.py`  
📝➡️📄  
Combines the generated notes into a single neat PDF.  
```bash
python '.\scripts\combine_to_pdf.py'
```

---

## 📂 Output

The final summarized notes will be available at:  
```
processed_notes/final_notes.pdf
```

---

## 📌 Notes
- Make sure the input video is clear and has good audio quality.
- Works best with lectures, presentations, and spoken content.
- You can customize how the notes are summarized by tweaking the prompts in `generate_notes_gemini.py`.
