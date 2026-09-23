import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';

const VideoPlayer = forwardRef(function VideoPlayer({ video, onTimeUpdate }, ref) {
  // Both <video> and <audio> are HTMLMediaElement, so the same ref/handlers
  // work for either - only which tag gets rendered differs below.
  const mediaElRef = useRef(null);
  const playable = video?.kind === 'video' || video?.kind === 'audio';

  useImperativeHandle(ref, () => ({
    seek(seconds) {
      if (playable && mediaElRef.current) {
        mediaElRef.current.currentTime = seconds;
        mediaElRef.current.play().catch(() => {});
      }
    },
  }));

  useEffect(() => {
    if (!playable) return undefined;
    const el = mediaElRef.current;
    if (!el) return undefined;
    const handler = () => onTimeUpdate?.(el.currentTime);
    el.addEventListener('timeupdate', handler);
    return () => el.removeEventListener('timeupdate', handler);
  }, [playable, onTimeUpdate]);

  if (!playable) {
    return (
      <div className="video-empty">
        <p>Preview isn't available for this source, but your notes are ready below.</p>
      </div>
    );
  }

  if (video.kind === 'audio') {
    return (
      <div className="video-frame audio-frame">
        {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
        <audio ref={mediaElRef} src={video.src} controls />
        <p className="audio-frame-hint">Audio only - no video was uploaded for this one.</p>
      </div>
    );
  }

  return (
    <div className="video-frame">
      {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
      <video ref={mediaElRef} src={video.src} controls playsInline />
    </div>
  );
});

export default VideoPlayer;
