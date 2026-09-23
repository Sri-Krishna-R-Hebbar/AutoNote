import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';

const VideoPlayer = forwardRef(function VideoPlayer({ video, onTimeUpdate }, ref) {
  const videoElRef = useRef(null);

  useImperativeHandle(ref, () => ({
    seek(seconds) {
      if (video?.kind === 'upload' && videoElRef.current) {
        videoElRef.current.currentTime = seconds;
        videoElRef.current.play().catch(() => {});
      }
    },
  }));

  useEffect(() => {
    if (video?.kind !== 'upload') return undefined;
    const el = videoElRef.current;
    if (!el) return undefined;
    const handler = () => onTimeUpdate?.(el.currentTime);
    el.addEventListener('timeupdate', handler);
    return () => el.removeEventListener('timeupdate', handler);
  }, [video, onTimeUpdate]);

  if (video?.kind !== 'upload') {
    return (
      <div className="video-empty">
        <p>Preview isn't available for this source, but your notes are ready below.</p>
      </div>
    );
  }

  return (
    <div className="video-frame">
      {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
      <video ref={videoElRef} src={video.src} controls playsInline />
    </div>
  );
});

export default VideoPlayer;
