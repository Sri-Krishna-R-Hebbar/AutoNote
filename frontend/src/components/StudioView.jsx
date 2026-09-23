import { useMemo, useRef, useState } from 'react';
import VideoPlayer from './VideoPlayer';
import NotesPanel from './NotesPanel';
import ConceptSlides from './ConceptSlides';
import OnScreenContent from './OnScreenContent';

function activeSectionFor(sections, currentTime) {
  let active = null;
  for (const s of sections) {
    if (s.timestamp == null) continue;
    if (s.timestamp <= currentTime + 0.25) {
      active = s;
    } else {
      break;
    }
  }
  return active?.id ?? null;
}

export default function StudioView({ notes, onReset }) {
  const {
    title,
    markdown,
    sections,
    concept_slides: slides,
    video,
    download_url: downloadUrl,
    sources,
    visual_notes: onScreenNotes,
  } = notes;
  const [tab, setTab] = useState('notes');
  const [currentTime, setCurrentTime] = useState(0);
  const playerRef = useRef(null);

  const activeSectionId = useMemo(() => activeSectionFor(sections, currentTime), [sections, currentTime]);
  const hasOnScreenTab = (onScreenNotes?.length ?? 0) > 0;

  function handleSeek(seconds) {
    playerRef.current?.seek(seconds);
  }

  return (
    <div className="studio">
      <div className="studio-header">
        <h2 className="studio-title">{title}</h2>
        <div className="studio-actions">
          <a className="download-btn small" href={downloadUrl}>
            Download PDF
          </a>
          <button type="button" className="again-link" onClick={onReset}>
            Process another video
          </button>
        </div>
      </div>

      {sources && (
        <div className="sources-strip">
          <span className={`source-badge ${sources.audio ? 'on' : 'off'}`}>
            🎙️ Audio transcript {sources.audio ? '✓' : '— not used'}
          </span>
          <span className={`source-badge ${sources.visual ? 'on' : 'off'}`}>
            🖼️ On-screen content (Qwen vision)
            {sources.visual ? ` ✓ ${onScreenNotes.length} frame(s)` : ' — not used'}
          </span>
        </div>
      )}

      <div className="studio-grid">
        <div className="studio-video-col">
          <VideoPlayer ref={playerRef} video={video} onTimeUpdate={setCurrentTime} />
        </div>

        <div className="studio-panel-col">
          <div className="tabs studio-tabs">
            <button type="button" className={`tab-btn ${tab === 'notes' ? 'active' : ''}`} onClick={() => setTab('notes')}>
              Notes
            </button>
            <button
              type="button"
              className={`tab-btn ${tab === 'slides' ? 'active' : ''}`}
              onClick={() => setTab('slides')}
            >
              Concept Slides
            </button>
            {hasOnScreenTab && (
              <button
                type="button"
                className={`tab-btn ${tab === 'onscreen' ? 'active' : ''}`}
                onClick={() => setTab('onscreen')}
              >
                On-Screen
              </button>
            )}
          </div>

          {tab === 'notes' && <NotesPanel markdown={markdown} activeSectionId={activeSectionId} />}
          {tab === 'slides' && <ConceptSlides slides={slides} onSeek={handleSeek} />}
          {tab === 'onscreen' && <OnScreenContent notes={onScreenNotes} onSeek={handleSeek} />}
        </div>
      </div>
    </div>
  );
}
