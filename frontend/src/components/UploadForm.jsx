import { useRef, useState } from 'react';

const ACCEPTED_EXTENSIONS = '.mp4,.mov,.mkv,.avi,.webm,.m4v,.wmv,.flv';

export default function UploadForm({ onSubmit }) {
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  function handleFilePicked(list) {
    if (list && list.length) setFile(list[0]);
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (!file) {
      alert('Please choose a video file first.');
      return;
    }
    const formData = new FormData();
    formData.append('video', file);
    onSubmit(formData);
  }

  return (
    <div id="upload-section">
      <form onSubmit={handleSubmit}>
        <div className="panel active">
          <label
            className={`dropzone ${dragOver ? 'dragover' : ''}`}
            htmlFor="file-input"
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
              handleFilePicked(e.dataTransfer.files);
            }}
          >
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M12 16V4m0 0L7 9m5-5l5 5" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M4 16v3a2 2 0 002 2h12a2 2 0 002-2v-3" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <p className="main">Click to choose a video, or drag one here</p>
            <p className="hint">MP4, MOV, MKV, AVI, WEBM — up to 500MB</p>
            {file && <p className="file-name">Selected: {file.name}</p>}
          </label>
          <input
            ref={fileInputRef}
            id="file-input"
            type="file"
            accept={ACCEPTED_EXTENSIONS}
            onChange={(e) => handleFilePicked(e.target.files)}
          />
        </div>

        <button type="submit" className="submit-btn">
          Generate my notes
        </button>
      </form>

      <p className="youtube-hint">
        Have a YouTube link instead of a file? Download it first with a trusted tool like{' '}
        <a href="https://cobalt.tools" target="_blank" rel="noopener noreferrer">
          cobalt.tools
        </a>
        , then upload the downloaded video here.
      </p>
    </div>
  );
}
