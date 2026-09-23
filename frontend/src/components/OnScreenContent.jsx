function formatTime(seconds) {
  const s = Math.max(0, Math.round(seconds));
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}:${rem.toString().padStart(2, '0')}`;
}

export default function OnScreenContent({ notes, onSeek }) {
  if (!notes || notes.length === 0) {
    return <p className="slides-empty">No on-screen text or writing was detected in this video.</p>;
  }

  return (
    <div className="onscreen-list">
      {notes.map((note, i) => (
        // eslint-disable-next-line react/no-array-index-key
        <div key={i} className="onscreen-item">
          <button type="button" className="onscreen-time" onClick={() => onSeek?.(note.start)}>
            {formatTime(note.start)}
          </button>
          <p className="onscreen-text">{note.text}</p>
        </div>
      ))}
    </div>
  );
}
