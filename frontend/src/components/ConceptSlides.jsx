import { useRef, useState } from 'react';

function formatTime(seconds) {
  if (seconds == null) return null;
  const s = Math.max(0, Math.round(seconds));
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}:${rem.toString().padStart(2, '0')}`;
}

export default function ConceptSlides({ slides, onSeek }) {
  const [index, setIndex] = useState(0);
  const dragStart = useRef(null);

  if (!slides || slides.length === 0) {
    return <p className="slides-empty">No concept slides could be generated for this video.</p>;
  }

  const clamp = (i) => Math.max(0, Math.min(slides.length - 1, i));
  const go = (delta) => setIndex((i) => clamp(i + delta));

  function handlePointerDown(e) {
    dragStart.current = e.clientX ?? e.touches?.[0]?.clientX;
  }
  function handlePointerUp(e) {
    if (dragStart.current == null) return;
    const endX = e.clientX ?? e.changedTouches?.[0]?.clientX;
    const delta = endX - dragStart.current;
    dragStart.current = null;
    if (Math.abs(delta) < 40) return;
    go(delta < 0 ? 1 : -1);
  }

  const slide = slides[index];
  const time = formatTime(slide.timestamp);

  return (
    <div className="concept-slides">
      <div
        className="slide-card"
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
        onTouchStart={handlePointerDown}
        onTouchEnd={handlePointerUp}
      >
        <div className="slide-index">
          {index + 1} / {slides.length}
        </div>
        <h3 className="slide-title">{slide.title}</h3>
        <ul className="slide-bullets">
          {slide.bullets.map((b) => (
            <li key={b}>{b}</li>
          ))}
        </ul>
        {time && (
          <button type="button" className="slide-jump" onClick={() => onSeek?.(slide.timestamp)}>
            ▶ Jump to {time}
          </button>
        )}
      </div>

      <div className="slide-nav">
        <button type="button" className="slide-arrow" onClick={() => go(-1)} disabled={index === 0} aria-label="Previous slide">
          ‹
        </button>
        <div className="slide-dots">
          {slides.map((s, i) => (
            <button
              key={s.id}
              type="button"
              className={`slide-dot ${i === index ? 'active' : ''}`}
              onClick={() => setIndex(i)}
              aria-label={`Go to slide ${i + 1}`}
            />
          ))}
        </div>
        <button
          type="button"
          className="slide-arrow"
          onClick={() => go(1)}
          disabled={index === slides.length - 1}
          aria-label="Next slide"
        >
          ›
        </button>
      </div>
    </div>
  );
}
