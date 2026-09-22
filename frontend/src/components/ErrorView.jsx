export default function ErrorView({ message, onRetry }) {
  return (
    <div className="error-block">
      <div className="error-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path
            d="M12 9v4m0 4h.01M10.29 3.86l-8.18 14A2 2 0 004.24 21h15.52a2 2 0 001.73-3.14l-8.18-14a2 2 0 00-3.46 0z"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
      <div className="error-msg">{message || 'Something went wrong.'}</div>
      <button type="button" className="again-link" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}
