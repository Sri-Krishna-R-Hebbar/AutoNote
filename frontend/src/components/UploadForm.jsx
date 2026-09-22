import { useRef, useState } from 'react';

const ACCEPTED_EXTENSIONS = '.mp4,.mov,.mkv,.avi,.webm,.m4v,.wmv,.flv';

export default function UploadForm({ onSubmit }) {
  const [activeTab, setActiveTab] = useState('file');
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const fileInputRef = useRef(null);

  function handleFilePicked(list) {
    if (list && list.length) setFile(list[0]);
  }

  function handleSubmit(e) {
    e.preventDefault();
    const formData = new FormData();
    if (activeTab === 'file') {
      if (!file) {
        alert('Please choose a video file first.');
        return;
      }
      formData.append('video', file);
    } else {
      if (!youtubeUrl.trim()) {
        alert('Please paste a video URL first.');
        return;
      }
      formData.append('youtube_url', youtubeUrl.trim());
    }
    onSubmit(formData);
  }

  return (
    <div id="upload-section">
      <div className="tabs">
        <button
          type="button"
          className={`tab-btn ${activeTab === 'file' ? 'active' : ''}`}
          onClick={() => setActiveTab('file')}
        >
          Upload a file
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'url' ? 'active' : ''}`}
          onClick={() => setActiveTab('url')}
        >
          Paste a video link
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        {activeTab === 'file' ? (
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
        ) : (
          <div className="panel active">
            <input
              type="url"
              aria-label="Video URL"
              placeholder="https://www.youtube.com/watch?v=..."
              value={youtubeUrl}
              onChange={(e) => setYoutubeUrl(e.target.value)}
            />
            <p className="url-hint">Works with YouTube and most other public video links.</p>
          </div>
        )}

        <button type="submit" className="submit-btn">
          Generate my notes
        </button>
      </form>
    </div>
  );
}
