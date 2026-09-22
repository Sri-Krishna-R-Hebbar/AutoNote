export default function ResultView({ downloadUrl, title, onReset }) {
  return (
    <div className="result-block">
      <div className="check-circle">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <div className="result-title">Your notes are ready!</div>
      <div className="result-sub">
        {title ? `Notes for "${title}" are ready.` : 'A beautifully formatted PDF is waiting for you.'}
      </div>
      <a className="download-btn" href={downloadUrl}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 16V4m0 12l-4-4m4 4l4-4M4 20h16" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Download PDF Notes
      </a>
      <button type="button" className="again-link" onClick={onReset}>
        Process another video
      </button>
    </div>
  );
}
