import { useState } from 'react';

const VIDEO_EXTENSIONS = '.mp4,.mov,.mkv,.avi,.webm,.m4v,.wmv,.flv';
const AUDIO_EXTENSIONS = '.mp3,.wav,.m4a,.aac,.ogg,.flac,.wma,.opus';

function Dropzone({ id, accept, label, hint, file, onPick }) {
  const [dragOver, setDragOver] = useState(false);

  function pick(list) {
    if (list && list.length) onPick(list[0]);
  }

  return (
    <div className="dropzone-field">
      <label
        className={`dropzone ${dragOver ? 'dragover' : ''}`}
        htmlFor={id}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          setDragOver(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          pick(e.dataTransfer.files);
        }}
      >
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M12 16V4m0 0L7 9m5-5l5 5" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M4 16v3a2 2 0 002 2h12a2 2 0 002-2v-3" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <p className="main">{label}</p>
        <p className="hint">{hint}</p>
        {file && <p className="file-name">Selected: {file.name}</p>}
      </label>
      <input id={id} type="file" accept={accept} onChange={(e) => pick(e.target.files)} />
    </div>
  );
}

export default function UploadForm({ onSubmit }) {
  const [videoFile, setVideoFile] = useState(null);
  const [audioFile, setAudioFile] = useState(null);

  function handleSubmit(e) {
    e.preventDefault();
    if (!videoFile && !audioFile) {
      alert('Please choose a video file, an audio file, or both.');
      return;
    }
    const formData = new FormData();
    if (videoFile) formData.append('video', videoFile);
    if (audioFile) formData.append('audio', audioFile);
    onSubmit(formData);
  }

  return (
    <div id="upload-section">
      <form onSubmit={handleSubmit}>
        <div className="dual-dropzones">
          <Dropzone
            id="video-input"
            accept={VIDEO_EXTENSIONS}
            label="Video file"
            hint="MP4, MOV, MKV, AVI, WEBM — up to 500MB. Used for both the audio transcript and on-screen content (slides, whiteboard, handwriting)."
            file={videoFile}
            onPick={setVideoFile}
          />
          <Dropzone
            id="audio-input"
            accept={AUDIO_EXTENSIONS}
            label="Audio file (optional)"
            hint="MP3, WAV, M4A, AAC and more. Only needed if your video has no sound (e.g. a video-only download) and you have the audio separately."
            file={audioFile}
            onPick={setAudioFile}
          />
        </div>

        <p className="upload-hint">
          Upload a video, an audio file, or both. If both are given, AutoNote reads the audio
          transcript <em>and</em> the video's on-screen content and combines them — handy since
          presenters often write things down without ever saying them out loud.
        </p>

        <button type="submit" className="submit-btn">
          Generate my notes
        </button>
      </form>

      <p className="youtube-hint">
        Have a YouTube link instead of a file? Download it first with a trusted tool like{' '}
        <a
          href="https://www.ytultra.com/en/youtube-video-downloader/"
          target="_blank"
          rel="noopener noreferrer"
        >
          YTUltra
        </a>
        , then upload the downloaded video here (pick a version with audio included).
      </p>
    </div>
  );
}
